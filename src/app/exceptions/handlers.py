"""Exception handlers для автоматической обработки ошибок."""
from fastapi import Request
from fastapi.responses import JSONResponse

from .common_exceptions import BaseAppException


async def base_exception_handler(
    request: Request,
    exc: BaseAppException,
) -> JSONResponse:
    """Обработчик базовых исключений приложения."""
    return JSONResponse(
        status_code=exc.status_code,
        content={'detail': exc.message},
    )


async def validation_error_handler(
    request: Request,
    exc: ValueError,
) -> JSONResponse:
    """Обработчик ValueError (ошибки валидации)."""
    return JSONResponse(
        status_code=400,
        content={'detail': str(exc)},
    )


async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Обработчик общих исключений."""
    return JSONResponse(
        status_code=500,
        content={'detail': f'Внутренняя ошибка сервера: {str(exc)}'},
    )
