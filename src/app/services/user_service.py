from typing import Annotated

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import ALGORITHM, authorization
from app.core.db import get_async_session
from app.crud.user_crud import crud_user
from app.models import Role, User


async def get_current_user(
    token: Annotated[HTTPAuthorizationCredentials, Depends(authorization)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> User:
    """Получает текущего пользователя."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Не удалось проверить учетные данные',
        headers={'WWW-Authenticate': 'Bearer'},
    )
    if token is None:
        raise credentials_exception
    try:
        payload = jwt.decode(
            token.credentials, settings.secret, algorithms=ALGORITHM
        )
        telegram_id: str = payload.get('sub')
        if telegram_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await crud_user.get_by_telegram_id(int(telegram_id), session)
    if user is None:
        raise credentials_exception
    return user


async def get_current_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Проверяет, что текущий пользователь — админ."""
    if user.role != Role.ADMIN:
        raise HTTPException(
            status_code=403, detail='Требуется роль администратора'
        )
    return user


async def get_current_manager(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Проверяет, что текущий пользователь — управляющий."""
    if user.role != Role.MANAGER:
        raise HTTPException(status_code=403, detail='Требуется роль менеджера')
    return user


async def get_current_barista(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Проверяет, что текущий пользователь — бариста."""
    if user.role != Role.BARISTA:
        raise HTTPException(status_code=403, detail='Требуется роль бариста')
    return user


pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет пароль с использованием bcrypt."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Хеширует пароль с использованием bcrypt.

    :param password: Открытый пароль
    :return: Хешированный пароль (в виде строки).
    """
    pwd_bytes = password.encode('utf-8')  # Пароль в байты
    salt = bcrypt.gensalt()  # Генерация "соли"
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')  # Возвращаем строку


def hash_schema_password(obj_in: BaseModel) -> BaseModel:
    """Создаёт копию Pydantic‑схемы с уже захешированным паролем."""
    if hasattr(obj_in, 'password') and obj_in.password:
        return obj_in.copy(update={'password': hash_password(obj_in.password)})
    return obj_in
