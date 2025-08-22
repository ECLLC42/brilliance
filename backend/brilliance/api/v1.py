from __future__ import annotations

import asyncio
import os
import ipaddress
import time
from threading import Lock
from typing import Dict, Tuple

from flask import Flask, jsonify, request, redirect
from flask_cors import CORS

from brilliance.agents.workflows import orchestrate_research, orchestrate_research_task


# In-memory per-process quota store: ip -> (count, reset_epoch_seconds)
_quota_lock = Lock()
_quota_store: Dict[str, Tuple[int, float]] = {}

# Per-IP, per-model quota store: key -> (count, reset_epoch_seconds)
_model_quota_store: Dict[str, Tuple[int, float]] = {}

# Depth to per-source result caps used by the frontend defaults
DEPTH_LIMITS = {"low": 3, "med": 5, "high": 12}


def _parse_allowed_origins() -> list[str]:
    # Prefer FRONTEND_URL env (comma-separated), else CORS_ORIGINS, else '*'
    raw = os.getenv("FRONTEND_URL") or os.getenv("CORS_ORIGINS") or "*"
    raw = (raw or "").strip()
    if raw == "*":
        return ["*"]
    # Heroku users sometimes set values like '@https://example.com' when using file-style config; strip leading '@'
    if raw.startswith("@"):
        raw = raw[1:].strip()
    origins: list[str] = []
    for origin in raw.split(","):
        trimmed = origin.strip()
        if not trimmed:
            continue
        if trimmed.startswith("@"):
            trimmed = trimmed[1:].strip()
        origins.append(trimmed)
    return origins


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


def _check_and_increment_model_quota(ip: str, model: str | None) -> Tuple[bool, int, int]:
    """
    Model-specific quota: enforce per-IP limits only for selected models.

    Defaults (override via env):
    - gpt-5: 3 per window (QUOTA_GPT5_PER_IP)
    - gpt-5-mini: 10 per window (QUOTA_GPT5_MINI_PER_IP)
    Other models are unlimited.

    Returns (allowed, remaining, reset_in_seconds)
    """
    window_seconds = int(os.getenv("FREE_QUOTA_WINDOW_SECONDS", "86400") or 86400)
    model_clean = (model or "").strip()

    limits = {
        "gpt-5": int(os.getenv("QUOTA_GPT5_PER_IP", "3") or 3),
        "gpt-5-mini": int(os.getenv("QUOTA_GPT5_MINI_PER_IP", "10") or 10),
    }
    if model_clean not in limits:
        return True, -1, window_seconds

    limit = limits[model_clean]
    if limit <= 0:
        return True, -1, window_seconds

    key = f"{ip}::{model_clean}"
    now = time.time()
    with _quota_lock:
        count, reset_at = _model_quota_store.get(key, (0, now + window_seconds))
        if now >= reset_at:
            count, reset_at = 0, now + window_seconds
        if count < limit:
            count += 1
            _model_quota_store[key] = (count, reset_at)
            remaining = max(0, limit - count)
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

    @app.get("/")
    def root() -> tuple[dict, int] | object:
        # Redirect to configured frontend if available; else show minimal API info
        dest_raw = (os.getenv("FRONTEND_URL") or "").strip()
        if dest_raw:
            if dest_raw.startswith("@"):
                dest_raw = dest_raw[1:].strip()
            # Use the first configured origin if multiple are provided
            dest = dest_raw.split(",")[0].strip()
            if dest:
                return redirect(dest, code=302)
        return {"message": "Brilliance API", "endpoints": ["/health", "/examples", "/limits", "POST /research"]}, 200

    @app.get("/examples")
    def examples() -> tuple[dict, int]:
        """Return a curated list of example research queries."""
        example_queries = [
            "What are the latest breakthroughs in protein folding using AlphaFold?",
            "How do current climate models compare in predicting sea level rise?",
            "What trends are emerging in single-cell RNA sequencing analysis?",
            "Which Alzheimer's clinical trials showed promise in 2024?",
            "What foundation models are best suited for biological research?",
            "How is CRISPR being used in cancer immunotherapy?",
            "What advances have been made in quantum computing algorithms?",
            "How effective are mRNA vaccines against emerging variants?",
            "What role does the gut microbiome play in neurodegenerative diseases?",
            "How are large language models transforming computational biology research?",
            "What recent developments exist in neuromorphic computing architectures?",
            "How do epigenetic modifications influence cancer drug resistance?",
            "What progress has been made in fusion energy reactor designs?",
            "How are organoids being used to model human diseases?",
            "What new insights exist about dark matter detection methods?"
        ]
        return {"examples": example_queries}, 200

    @app.get("/limits")
    def limits() -> tuple[dict, int]:
        # Expose all depths by default
        allowed_depths = ["low", "med", "high"]
        return {
            "allowed_depths": allowed_depths,
            "per_source_caps": DEPTH_LIMITS,
            # Backend uses server-side OPENAI_API_KEY; user-provided keys are not required
            "require_api_key": False,
        }, 200

    @app.post("/research")
    def research() -> tuple[dict, int]:
        payload = request.get_json(silent=True) or {}
        query = (payload.get("query") or "").strip()
        # Default to 10 sources
        default_cap = 10
        max_results_raw = payload.get("max_results", default_cap)
        # Force GPT-5 model
        model = "gpt-5"
        # Default to arXiv + OpenAlex
        sources = payload.get("sources", ["arxiv", "openalex"])
        
        # Validate sources parameter
        valid_sources = ["arxiv", "pubmed", "openalex"]
        if not isinstance(sources, list) or not sources:
            sources = ["arxiv", "openalex"]
        else:
            sources = [s for s in sources if s in valid_sources]
            if not sources:
                return {"error": "At least one valid source must be selected. Valid sources: arxiv, pubmed, openalex"}, 400
        
        # Reasoning/verbosity controls (default to high reasoning if unspecified)
        def _norm_effort(val: str | None) -> str | None:
            if not val:
                return None
            v = str(val).strip().lower()
            return {"min": "minimal", "minimal": "minimal", "low": "low", "med": "medium", "medium": "medium", "high": "high"}.get(v, v)
        def _norm_verbosity(val: str | None) -> str | None:
            if not val:
                return None
            v = str(val).strip().lower()
            return {"low": "low", "med": "medium", "medium": "medium", "high": "high"}.get(v, v)
        reasoning_effort = _norm_effort(payload.get("reasoning_effort") or os.getenv("DEFAULT_REASONING_EFFORT", "high"))
        verbosity = _norm_verbosity(payload.get("verbosity") or os.getenv("DEFAULT_VERBOSITY"))
        try:
            max_results = int(max_results_raw)
        except Exception:
            max_results = 10

        if not query:
            return {"error": "Missing 'query'"}, 400

        client_ip = _get_client_ip()

        # Apply per-IP, model-specific quota unless bypassed; no user-supplied API keys are required
        if not _is_bypassed(client_ip):
            allowed, remaining, reset_in = _check_and_increment_model_quota(client_ip, model)
            if not allowed:
                return {
                    "error": "Rate limit exceeded for this model. Please try again later.",
                    "remaining": remaining,
                    "reset_in": reset_in,
                }, 429

        # Optional hard requirement handled above

        # Do NOT set user API key in process environment

        # No additional depth restriction; high depth is permitted by default

        # Optional async mode via Celery
        if os.getenv("ENABLE_ASYNC_JOBS") == "1":
            try:
                task = orchestrate_research_task.delay({
                    "user_query": query,
                    "max_results": max_results,
                    "model": model,
                    "sources": sources,
                })
                return {"task_id": task.id, "status": "queued"}, 202
            except Exception as exc:
                return jsonify({"error": f"Failed to enqueue task: {exc}"}), 500

        # Synchronous path (default)
        try:
            results = asyncio.run(
                orchestrate_research(
                    user_query=query,
                    max_results=max_results,
                    model=model,
                    sources=sources,
                    reasoning_effort=reasoning_effort,
                    verbosity=verbosity,
                )
            )
            return jsonify(results), 200
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/research/<task_id>")
    def research_status(task_id: str) -> tuple[dict, int]:
        """Poll Celery task status/result when async mode is enabled."""
        if os.getenv("ENABLE_ASYNC_JOBS") != "1":
            return {"error": "Async jobs disabled"}, 400
        try:
            from brilliance.celery_app import celery_app
            async_result = celery_app.AsyncResult(task_id)
            state = async_result.state
            if state in ("PENDING", "STARTED", "RETRY"):
                return {"task_id": task_id, "status": state.lower()}, 200
            if state == "SUCCESS":
                return {"task_id": task_id, "status": "success", "result": async_result.result}, 200
            # FAILURE or revoked
            return {"task_id": task_id, "status": "failure", "error": str(async_result.result)}, 200
        except Exception as exc:
            return {"error": str(exc)}, 500

    return app


app = create_app()


