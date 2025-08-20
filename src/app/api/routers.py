"""Главный роутер API."""

from fastapi import APIRouter

from app.api.endpoints import (
    cafe_router,
    reservation_router,
    shift_router,
    users_router,
)

# Создаем главный роутер для API
api_router = APIRouter(prefix='/api/v1')

# Подключаем все роутеры
api_router.include_router(cafe_router)
api_router.include_router(users_router)
api_router.include_router(reservation_router)
api_router.include_router(shift_router)
# Экспортируем для использования в main.py
__all__ = ['api_router']
