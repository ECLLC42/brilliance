"""
Celery application factory for background job processing.

Broker and backend are taken from environment variables in this order:
- CELERY_BROKER_URL / CELERY_RESULT_BACKEND
- REDIS_URL (Heroku Redis add-on)
- fallback: redis://localhost:6379/0
"""
from __future__ import annotations

import os
from celery import Celery


def _redis_url_default() -> str:
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


def make_celery() -> Celery:
    broker_url = os.getenv("CELERY_BROKER_URL") or _redis_url_default()
    result_backend = os.getenv("CELERY_RESULT_BACKEND") or _redis_url_default()

    # Include the module that defines tasks so the worker knows about them
    app = Celery(
        "brilliance",
        broker=broker_url,
        backend=result_backend,
        include=[
            "brilliance.agents.workflows",  # contains orchestrate_research_task
        ],
    )

    # Prefer JSON serialization for safety in hosted environments
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        result_expires=int(os.getenv("CELERY_RESULT_EXPIRES", "86400")),  # 24h
        worker_hijack_root_logger=False,
    )

    # Eagerly import tasks to ensure registration in environments where include is ignored
    try:
        # no-op import purely to register tasks
        import brilliance.agents.workflows  # noqa: F401
    except Exception:
        pass

    return app


celery_app = make_celery()


