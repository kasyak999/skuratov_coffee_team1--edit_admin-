from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import List, Optional

from jose import jwt
from sqlalchemy import String, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

# from app.services.user_service import hash_password
from app.core.config import settings
from app.core.constants import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    ERROR_BARISTA_ALREADY_CONFIRMED,
    ERROR_BARISTA_NOT_CONFIRMED,
    ERROR_USER_NOT_FOUND,
)
from app.crud.base_crud import CRUDBase
from app.exceptions.common_exceptions import NotFoundError, ValidationError
from app.models.user import Role, User
from app.schemas.user_schema import (
    UserRead,
    UserResponse,
)


class CRUDUser(CRUDBase):
    """CRUD-операции для модели User."""

    def __init__(self) -> None:
        """Инициализация CRUD-класса для User."""
        super().__init__(User)

    async def get_by_telegram_id(
        self,
        telegram_id: int,
        session: AsyncSession,
    ) -> User | None:
        """Получение пользователя по Telegram ID."""
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_or_404(self, user_id: int, session: AsyncSession) -> User:
        """Получение пользователя по ID или ошибка 404."""
        user = await self.get(user_id, session)
        if not user:
            raise NotFoundError(ERROR_USER_NOT_FOUND)
        return user

    async def get_pending_baristas(
        self,
        session: AsyncSession
    ) -> Sequence[User]:
        """Получение всех ожидающих подтвержденя бариста."""
        stmt = (
            select(User)
            .where(User.role == Role.BARISTA, User.is_active.is_(False))
            .order_by(User.created_at.desc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def activate_user(
        self,
        user: User,
        session: AsyncSession,
    ) -> User:
        """Подтверждает пользователя (is_activate = True)."""
        if user.is_active:
            raise ValidationError(ERROR_BARISTA_ALREADY_CONFIRMED)
        user.is_active = True
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    async def deactivate_user(
            self,
            user: User,
            session: AsyncSession,
    ) -> User:
        """Изменяет статус пользователя блокировка/разблокировка."""
        if not user.is_active:
            raise ValidationError(ERROR_BARISTA_NOT_CONFIRMED)
        user.is_active = False
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    async def get_user_role(
            self,
            telegram_id: int,
            session: AsyncSession,
    ) -> Optional[Role]:
        """Получить роль пользователя по Telegram ID."""
        result = await session.execute(
            select(User.role).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def authenticate_user(
        self,
        telegram_id: int,
    ) -> UserResponse:
        """Получить токен."""
        expire = datetime.utcnow() + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {'sub': str(telegram_id), 'exp': expire}
        token = jwt.encode(to_encode, settings.secret, algorithm=ALGORITHM)
        return UserResponse(access_token=token, token_type='bearer')

    async def get_multi_by_role(
        self,
        role: Role,
        session: AsyncSession,
    ) -> Sequence[User]:
        """Получить пользователей по роли."""
        user = await session.execute(select(User).where(User.role == role))
        return user.scalars().all()

    async def search_by_query(
            self,
            query: str,
            session: AsyncSession
    ) -> List[UserRead]:
        """Поиск пользователей по имени или телефону."""
        stmt = select(User).where(
            or_(
                User.name.ilike(f'%{query}%'),
                User.phone.ilike(f'%{query}%'),
                cast(User.telegram_id, String).ilike(f'%{query}%')
            )
        )
        result = await session.execute(stmt)
        return [UserRead.model_validate(row) for row in result.scalars()]

    async def get_by_is_active(
            self,
            is_active: bool,
            session: AsyncSession
    ) -> list[User]:
        """Возвращает пользователей по активности."""
        stmt = select(User).where(User.is_active == is_active)
        result = await session.execute(stmt)
        return result.scalars().all()


crud_user = CRUDUser()
