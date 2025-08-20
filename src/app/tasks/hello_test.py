from celery import shared_task


@shared_task(name='Тестовая задача 1')
def hello() -> str:
    """Пример задачи Celery, которая возвращает 'hello world'."""
    return 'hello world'
