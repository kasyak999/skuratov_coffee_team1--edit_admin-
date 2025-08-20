"""Главное приложение FastAPI."""

import sys
from contextlib import asynccontextmanager

from typing import AsyncGenerator

from fastapi import Depends, FastAPI

from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers import api_router
from app.core.config import settings
from app.core.db import get_async_session, engine
from app.core.init_db import add_admin
from app.exceptions import BaseAppException
from app.exceptions.handlers import (
    base_exception_handler,
    general_exception_handler,
    validation_error_handler,
)
from app.tasks import hello, hello_2  # Файлы задач
from sqladmin import Admin
from app.core.admin import (
    UserAdmin,
    CafeAdmin,
    ReservationAdmin,
    ShiftAdmin,
    auth_backend,
)
from pathlib import Path
from fastapi.staticfiles import StaticFiles

logger.remove()
logger.add(
    sys.stdout,
    format='{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}',
    level='INFO',
)

BASE_DIR = Path(__file__).resolve().parent


def static(path: str):
    return f"/statics/{path}"



@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Контекстный менеджер для инициализации приложения."""
    logger.info('Запуск приложения')
    await add_admin()
    yield
    logger.info('Завершение работы приложения')


# Создаем FastAPI приложение
app = FastAPI(
    title=settings.app_title,
    description=settings.description,
    version=settings.version,
    lifespan=lifespan,
)

admin = Admin(
    app,
    engine,
    authentication_backend=auth_backend,
    templates_dir=BASE_DIR / "templates",
)

from fastapi import Request
from jinja2 import pass_context

@pass_context
def relative_url_for(ctx, name: str, **kwargs):
    request: Request = ctx["request"]
    url = str(request.url_for(name, **kwargs))
    return url.replace(str(request.base_url), "/")


app.mount(
    "/statics",
    StaticFiles(directory=BASE_DIR / "static"),
    name="statics"
)

# def relative_url_for(request: Request, name: str, **kwargs):
#     """Функция, возвращающая относительный URL"""
#     # return f"/{name}/{kwargs.get("path", "")}"
#     # return request.url_for(name, **kwargs).replace(str(request.base_url), "/")
#     url = str(request.url_for(name, **kwargs))
#     return url.replace(str(request.base_url), "/")


# admin.templates.env.globals['url_for'] = relative_url_for

admin.add_view(UserAdmin)
admin.add_view(CafeAdmin)
admin.add_view(ReservationAdmin)
admin.add_view(ShiftAdmin)


# Подключаем API роутеры
app.include_router(api_router)


@app.get("/ping_celery", summary="Проверка Celery")
async def ping_celery() -> dict:
    """Проверка работы Celery."""
    try:
        hello.delay()  # отправляем задачу в очередь
        hello_2.apply_async(countdown=5)  # запуск через 5 секунд
        return {"message": "Если нет ошибки все ок"}
    except Exception as e:
        return {"error": str(e)}


@app.get(
    '/ping_db',
    summary='Проверка подключения к базе данных',
    description=(
        'Этот эндпоинт выполняет простой SQL-запрос `SELECT 1`, '
        'чтобы убедиться, что соединение с базой данных установлено.'
    ),
    response_description='Статус соединения и результат запроса',
)
async def ping_db(
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Проверка подключения к базе данных."""
    try:
        result = await session.execute(text('SELECT 1'))
        return {'status': 'подключено', 'result': result.scalar()}
    except SQLAlchemyError as e:
        return {'status': 'ошибка', 'detail': str(e)}


@app.get("/test")
async def test(request: Request):
    return {"url": str(request.url), "base_url": str(request.base_url)}

app.add_exception_handler(BaseAppException, base_exception_handler)
app.add_exception_handler(ValueError, validation_error_handler)
app.add_exception_handler(Exception, general_exception_handler)
