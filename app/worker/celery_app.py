from celery import Celery

from app.core.config import get_settings

# Redis URL from the environment/.env, defaulting to a local Docker Redis instance
REDIS_URL = get_settings().celery_broker_url

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