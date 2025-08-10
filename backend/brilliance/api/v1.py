from __future__ import annotations

import asyncio
import os
import ipaddress
import time
from threading import Lock
from typing import Dict, Tuple

from flask import Flask, jsonify, request, redirect
from flask_cors import CORS

from brilliance.agents.workflows import orchestrate_research


# In-memory per-process quota store: ip -> (count, reset_epoch_seconds)
_quota_lock = Lock()
_quota_store: Dict[str, Tuple[int, float]] = {}

# Depth to per-source result caps used by the frontend defaults
DEPTH_LIMITS = {"low": 3, "med": 5, "high": 10}


def _parse_allowed_origins() -> list[str]:
    # Prefer FRONTEND_URL env (comma-separated), else CORS_ORIGINS, else '*'
    raw = os.getenv("FRONTEND_URL") or os.getenv("CORS_ORIGINS") or "*"
    if raw.strip() == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


def _get_client_ip() -> str:
    # Trust left-most X-Forwarded-For if present (Heroku/Proxies)
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _is_bypassed(ip: str) -> bool:
    """Return True if the given client IP should bypass quotas and depth limits.

    Supports:
    - Loopback addresses (127.0.0.1, ::1) always bypass
    - Exact IPs via BYPASS_IPS (comma-separated)
    - CIDR subnets via BYPASS_NETS (comma-separated), e.g. 192.168.0.0/16
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
    except Exception:
        return False

    # Always allow loopback in dev
    if ip_obj.is_loopback:
        return True

    # Exact IP matches
    raw_ips = os.getenv("BYPASS_IPS", "")
    if raw_ips:
        whitelist = {i.strip() for i in raw_ips.split(",") if i.strip()}
        if ip in whitelist:
            return True

    # CIDR network matches
    raw_nets = os.getenv("BYPASS_NETS", "")
    if raw_nets:
        for net in (n.strip() for n in raw_nets.split(",")):
            if not net:
                continue
            try:
                if ip_obj in ipaddress.ip_network(net, strict=False):
                    return True
            except Exception:
                # Ignore malformed entries
                continue

    return False


def _check_and_increment_quota(ip: str) -> Tuple[bool, int, int]:
    """
    Returns (allowed, remaining, reset_in_seconds)
    """
    free_limit = int(os.getenv("FREE_MESSAGES_PER_IP", "0") or 0)
    window_seconds = int(os.getenv("FREE_QUOTA_WINDOW_SECONDS", "86400") or 86400)

    # If limit is 0, unlimited
    if free_limit <= 0:
        return True, -1, window_seconds

    now = time.time()
    with _quota_lock:
        count, reset_at = _quota_store.get(ip, (0, now + window_seconds))
        # Reset window if expired
        if now >= reset_at:
            count, reset_at = 0, now + window_seconds
        if count < free_limit:
            count += 1
            _quota_store[ip] = (count, reset_at)
            remaining = max(0, free_limit - count)
            return True, remaining, int(reset_at - now)
        else:
            remaining = 0
            return False, remaining, int(reset_at - now)


def create_app() -> Flask:
    app = Flask(__name__)
    origins = _parse_allowed_origins()
    CORS(
        app,
        resources={
            r"/*": {
                "origins": origins,
                "allow_headers": ["Content-Type", "X-User-Api-Key"],
                "expose_headers": ["Content-Type"],
            }
        },
    )

    @app.get("/health")
    def health() -> tuple[dict, int]:
        return {"status": "ok"}, 200

    # Enforce HTTPS and add security headers
    @app.before_request
    def _enforce_https():
        if os.getenv("ENFORCE_HTTPS") == "1":
            # Respect Heroku/X-Forwarded-Proto
            if request.headers.get("X-Forwarded-Proto", request.scheme) != "https":
                url = request.url.replace("http://", "https://", 1)
                return redirect(url, code=301)

    @app.after_request
    def _security_headers(resp):
        # HSTS (only meaningful over HTTPS)
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")
        # No MIME sniffing
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        # Referrer policy
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        # Minimal permissions policy
        resp.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        # CSP tuned for our app and APIs
        csp = (
            "default-src 'self'; "
            "connect-src 'self' https://api.openai.com https://*.openalex.org https://export.arxiv.org https://eutils.ncbi.nlm.nih.gov; "
            "img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
            "base-uri 'none'; frame-ancestors 'none'"
        )
        resp.headers.setdefault("Content-Security-Policy", csp)
        # No-store for responses with potential sensitive content
        resp.headers.setdefault("Cache-Control", "no-store")
        # Try to hide server banner
        resp.headers.pop("Server", None)
        return resp

    @app.get("/limits")
    def limits() -> tuple[dict, int]:
        client_ip = _get_client_ip()
        user_api_key = request.headers.get("X-User-Api-Key")
        is_allowed_high = bool(user_api_key) or _is_bypassed(client_ip)
        allowed_depths = ["low", "med"] + (["high"] if is_allowed_high else [])
        return {
            "allowed_depths": allowed_depths,
            "per_source_caps": DEPTH_LIMITS,
            "require_api_key": os.getenv("REQUIRE_API_KEY") == "1",
        }, 200

    @app.post("/research")
    def research() -> tuple[dict, int]:
        payload = request.get_json(silent=True) or {}
        query = (payload.get("query") or "").strip()
        max_results_raw = payload.get("max_results", 3)
        model = (payload.get("model") or "").strip() or None
        try:
            max_results = int(max_results_raw)
        except Exception:
            max_results = 3

        if not query:
            return {"error": "Missing 'query'"}, 400

        client_ip = _get_client_ip()

        # Require API key for all research in production-like mode
        user_api_key = request.headers.get("X-User-Api-Key")
        if os.getenv("REQUIRE_API_KEY") == "1" and not user_api_key:
            return {"message": "API key required"}, 402

        # If not strictly required, still apply free quota unless bypassed or key provided
        if not user_api_key and not _is_bypassed(client_ip) and os.getenv("REQUIRE_API_KEY") != "1":
            allowed, remaining, reset_in = _check_and_increment_quota(client_ip)
            if not allowed:
                return (
                    {
                        "message": "Free limit reached. Add an API key to continue.",
                        "remaining": remaining,
                        "reset_in": reset_in,
                    },
                    402,
                )

        # Optional hard requirement handled above

        # Do NOT set user API key in process environment

        # Enforce depth: "high" (> med cap) requires API key or bypassed IP
        is_allowed_high = bool(user_api_key) or _is_bypassed(client_ip)
        med_cap = DEPTH_LIMITS.get("med", 5)
        if max_results > med_cap and not is_allowed_high:
            return {
                "message": "High depth requires an API key or whitelisted IP.",
                "allowed_up_to": med_cap,
            }, 402

        try:
            results = asyncio.run(
                orchestrate_research(
                    user_query=query,
                    max_results=max_results,
                    model=model,
                    user_api_key=user_api_key,
                )
            )
            return jsonify(results), 200
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    return app


app = create_app()


