import os
from celery import Celery

# Fetches the Redis URL from your .env, or defaults to a local Docker Redis instance
REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

# Initialize the Celery application
celery_app = Celery(
    "compliance_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['app.worker.tasks'] # Tells Celery where your task functions live
)

# Standard configuration for serialization and timezones
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)