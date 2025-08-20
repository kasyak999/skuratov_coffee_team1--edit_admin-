from celery import Celery

from app.core.config import settings

CELERY_HOST = 'localhost' if settings.DEBUG else 'redis_service'
BROKER = f'redis://:{settings.redis_pass}@{CELERY_HOST}:6380/0'

celery_app = Celery("Селери", broker=BROKER, backend=BROKER)
celery_app.autodiscover_tasks([
    "app.tasks",       # ищет все задачии в папке app/tasks
])
