from typing import List, Optional, Sequence

from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DEFAULT_USER_LIST_LIMIT, authorization
from app.core.db import get_async_session
from app.crud.user_crud import crud_user
from app.models import Role, User
from app.schemas import (
    UserCreate,
    UserRead,
    UserRequest,
    UserResponse,
    UserUpdate,
)
from app.services.user_service import get_current_admin
from app.validators.user_validators import (
    check_is_active,
    check_not_is_active,
    check_not_telegram_id,
    check_password,
    check_role,
    check_telegram_id,
    check_user_id,
)

router = APIRouter(prefix='/users', tags=['users'])


@router.post(
    '/login',
    response_model=UserResponse, summary='Авторизация пользователя'
)
async def login(
    data: UserRequest = Depends(UserRequest.as_form),
    session: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    """Авторизация пользователя."""
    user = await crud_user.get_by_telegram_id(data.telegram_id, session)
    await check_not_telegram_id(user)
    await check_password(user, data.password)
    return await crud_user.authenticate_user(data.telegram_id)


@router.get(
    '/',
    response_model=List[UserRead],
    summary='Список пользователей')
async def get_users(
    skip: int = 0,
    limit: int = DEFAULT_USER_LIST_LIMIT,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_admin),
) -> Sequence[UserRead]:
    """Возвращает постраничный список всех пользователей."""
    return await crud_user.get_multi(session=session, skip=skip, limit=limit)


@router.post(
    '/',
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary='Создать пользователя')
async def create_user(
    user_in: UserCreate,
    token: Optional[HTTPAuthorizationCredentials] = Depends(authorization),
    session: AsyncSession = Depends(get_async_session),
) -> UserRead:
    """Создает пользователя."""
    user = await crud_user.get_by_telegram_id(user_in.telegram_id, session)
    await check_telegram_id(user)
    await check_role(user_in, token, session)
    return await crud_user.create(user_in, session)


@router.get(
    '/pending',
    response_model=List[UserRead],
    summary='Список неподтверждённых бариста')
async def get_pending_baristas(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_admin),
) -> Sequence[UserRead]:
    """Возвращает всех бариста, ожидающих подтверждения регистрации."""
    return await crud_user.get_pending_baristas(session)


@router.get(
    '/by-active',
    response_model=list[UserRead],
    summary='Пользователи по активности')
async def get_users_by_is_active(
    is_active: bool,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_admin),
) -> Sequence[User]:
    """Получить пользователей по статусу."""
    return await crud_user.get_by_is_active(is_active, session)


@router.get(
    '/{user_id}',
    response_model=UserRead,
    summary='Получить пользователя по ID')
async def get_user_by_id(
    user_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_admin),
) -> User:
    """Возвращает пользователя по его ID."""
    user = await crud_user.get(user_id, session)
    return await check_user_id(user)


@router.patch(
    '/{user_id}/confirm',
    response_model=UserRead,
    summary='Подтвердить регистрацию бариста')
async def confirm_user_registration(
    user_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_admin),
) -> UserRead:
    """Подтверждает регистрацию бариста (is_active = True)."""
    user = await crud_user.get(user_id, session)
    user_check_user_id = await check_user_id(user)
    await check_is_active(user_check_user_id)
    return await crud_user.activate_user(user_check_user_id, session)


@router.patch(
    '/{user_id}/decline',
    response_model=UserRead,
    summary='Отклонить регистрацию бариста')
async def decline_user_registration(
    user_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_admin),
) -> UserRead:
    """Отклоняет регистрацию бариста."""
    user = await crud_user.get(user_id, session)
    user_check_user_id = await check_user_id(user)
    await check_not_is_active(user_check_user_id)
    return await crud_user.deactivate_user(user_check_user_id, session)


@router.patch(
    '/{user_id}',
    response_model=UserRead,
    summary='Обновить пользователя')
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_admin),
) -> UserRead:
    """Обновляет пользователя."""
    user = await crud_user.get(user_id, session)
    user_check_user_id = await check_user_id(user)
    return await crud_user.update(user_check_user_id, user_in, session)


@router.delete(
    '/{user_id}',
    response_model=UserRead,
    summary='Удалить пользователя')
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_admin),
) -> UserRead:
    """Удаляет пользователя."""
    user = await crud_user.get(user_id, session)
    user_check_user_id = await check_user_id(user)
    return await crud_user.remove(user_check_user_id, session)


@router.get(
    '/{role}/role',
    response_model=List[UserRead],
    summary='Получить пользователей по роли.')
async def multi_by_role(
    role: Role,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_admin),
) -> Sequence[User]:
    """Получить пользователей по роли."""
    return await crud_user.get_multi_by_role(role, session)
