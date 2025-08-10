from __future__ import annotations

import asyncio
import os
import time
from threading import Lock
from typing import Dict, Tuple

from flask import Flask, jsonify, request
from flask_cors import CORS

from brilliance.agents.workflows import orchestrate_research


# In-memory per-process quota store: ip -> (count, reset_epoch_seconds)
_quota_lock = Lock()
_quota_store: Dict[str, Tuple[int, float]] = {}


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
    bypass_raw = os.getenv("BYPASS_IPS", "")
    if not bypass_raw:
        return False
    whitelist = {i.strip() for i in bypass_raw.split(",") if i.strip()}
    return ip in whitelist


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
    CORS(app, resources={r"/*": {"origins": origins}})

    @app.get("/health")
    def health() -> tuple[dict, int]:
        return {"status": "ok"}, 200

    @app.post("/research")
    def research() -> tuple[dict, int]:
        payload = request.get_json(silent=True) or {}
        query = (payload.get("query") or "").strip()
        max_results_raw = payload.get("max_results", 3)
        try:
            max_results = int(max_results_raw)
        except Exception:
            max_results = 3

        if not query:
            return {"error": "Missing 'query'"}, 400

        client_ip = _get_client_ip()

        # Skip quota if client supplies their own API key
        user_api_key = request.headers.get("X-User-Api-Key")
        if not user_api_key and not _is_bypassed(client_ip):
            allowed, remaining, reset_in = _check_and_increment_quota(client_ip)
            if not allowed:
                # 402 triggers the frontend key modal
                return (
                    {
                        "message": "Free limit reached. Add an API key to continue.",
                        "remaining": remaining,
                        "reset_in": reset_in,
                    },
                    402,
                )

        # Optional hard requirement regardless of quota
        if os.getenv("REQUIRE_API_KEY") == "1" and not user_api_key:
            return {"message": "API key required"}, 402

        # If a user key is supplied, expose it to downstream tools via common env names
        if user_api_key:
            os.environ.setdefault("OPENAI_API_KEY", user_api_key)
            os.environ.setdefault("XAI_API_KEY", user_api_key)
            os.environ.setdefault("GROK_API_KEY", user_api_key)
            os.environ.setdefault("ANTHROPIC_API_KEY", user_api_key)
            os.environ.setdefault("TOGETHER_API_KEY", user_api_key)
            os.environ.setdefault("GEMINI_API_KEY", user_api_key)

        try:
            results = asyncio.run(orchestrate_research(query, max_results))
            return jsonify(results), 200
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    return app


app = create_app()


