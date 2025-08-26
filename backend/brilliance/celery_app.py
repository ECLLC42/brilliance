"""
Celery application factory for background job processing.

Broker and backend are taken from environment variables in this order:
- CELERY_BROKER_URL / CELERY_RESULT_BACKEND
- REDIS_URL (Heroku Redis add-on)
- fallback: redis://localhost:6379/0
"""
from __future__ import annotations

import os
import json
from celery import Celery
from kombu.serialization import register


class OptimizedQueryEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle OptimizedQuery objects."""
    def default(self, obj):
        # Import here to avoid circular imports
        try:
            from brilliance.agents.query_optimizer_agent import OptimizedQuery
            if isinstance(obj, OptimizedQuery):
                return obj.to_dict()
        except ImportError:
            pass
        return super().default(obj)


def dumps(obj):
    """Custom JSON dumps function with OptimizedQuery support."""
    return json.dumps(obj, cls=OptimizedQueryEncoder)


def loads(s):
    """Custom JSON loads function."""
    return json.loads(s)


# Register the custom serializer
register('optimized_json', dumps, loads, content_type='application/json', content_encoding='utf-8')


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

    # Use custom JSON serialization to handle OptimizedQuery objects
    app.conf.update(
        task_serializer="optimized_json",
        result_serializer="optimized_json",
        accept_content=["optimized_json", "json"],
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


