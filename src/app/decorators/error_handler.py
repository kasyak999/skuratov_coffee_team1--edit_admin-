"""Декоратор для обработки ошибок в роутерах."""

from functools import wraps
from typing import Any, Callable

from fastapi import HTTPException, status

from app.exceptions import BaseAppException


def handle_errors(func: Callable) -> Callable:
    """Декоратор для автоматической обработки ошибок в эндпоинтах.

    Автоматически конвертирует:
    - BaseAppException -> HTTPException с соответствующим статусом
    - ValueError -> HTTPException 400
    - Exception -> HTTPException 500
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except BaseAppException as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=e.message,
            ) from e
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f'Внутренняя ошибка сервера: {str(e)}',
            ) from e

    return wrapper
