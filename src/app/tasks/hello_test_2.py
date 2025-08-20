from celery import shared_task


@shared_task(name='Тестовая задача 2')
def hello_2() -> str:
    """Пример задачи Celery, которая возвращает 'hello world'."""
    return '"Эта задача запустилась через 5 секунд"'
