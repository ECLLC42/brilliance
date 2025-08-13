web: PYTHONPATH=backend gunicorn backend.brilliance.api.v1:app --bind 0.0.0.0:$PORT --workers 3 --threads 4 --timeout 60
worker: PYTHONPATH=backend celery -A brilliance.celery_app:celery_app worker --loglevel=info
heroku restart