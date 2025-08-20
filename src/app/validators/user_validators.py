from http import HTTPStatus
from typing import Optional

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    ERROR_BARISTA_ALREADY_CONFIRMED,
    ERROR_BARISTA_NOT_CONFIRMED,
    ERROR_USER_ALREADY_EXISTS,
    ERROR_USER_AUTHENTICATE,
    ERROR_USER_NOT_FOUND,
    ERROR_USER_ROLE,
)
from app.models import Role, User
from app.schemas.user_schema import UserCreate
from app.services.user_service import get_current_user


async def check_not_telegram_id(
    result: User | None,
) -> None:
    """Проверка по телеграм id. Пользователь  не существует."""
    if result is None:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=ERROR_USER_NOT_FOUND,
        )


async def check_password(
    result: User | None,
    password: str,
) -> None:
    """Проверка введеного пароля."""
    pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
    if result and not pwd_context.verify(password, result.password):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=ERROR_USER_AUTHENTICATE,
        )


async def check_telegram_id(
    result: User | None,
) -> None:
    """Проверка по телеграм id. Пользователь существует."""
    if result is not None:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=ERROR_USER_ALREADY_EXISTS,
        )


async def check_role(
    result: UserCreate,
    token: Optional[HTTPAuthorizationCredentials],
    session: AsyncSession,
) -> None:
    """Проверка роли."""
    token_user = await get_current_user(token, session) if token else None
    if token_user is not None and token_user.role == Role.ADMIN:
        pass
    elif result.role in [Role.ADMIN, Role.MANAGER]:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=ERROR_USER_ROLE,
        )


async def check_user_id(
    result: User | None,
) -> User:
    """Проверка существует пользователь."""
    if not result:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=ERROR_USER_NOT_FOUND,
        )
    return result


async def check_is_active(
    result: User,
) -> None:
    """Проверка что пользователь подтвержден."""
    if result.is_active:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=ERROR_BARISTA_ALREADY_CONFIRMED,
        )


async def check_not_is_active(
    result: User,
) -> None:
    """Проверка что пользователь не подтвержден."""
    if not result.is_active:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=ERROR_BARISTA_NOT_CONFIRMED,
        )
