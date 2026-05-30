from celery import Celery
from app.core.config import settings

celery = Celery(
    "university",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.email_tasks"],
)

celery.conf.task_routes = {
    "app.tasks.email_tasks.*": {"queue": "email"},
}
