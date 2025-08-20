"""Сервисы для работы с кафе."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InvalidManagerError
from app.models.user import User


class CafeService:
    """Сервис для работы с кафе."""

    @staticmethod
    async def validate_manager(
        manager_id: Optional[int],
        session: AsyncSession,
    ) -> None:
        """Проверить, что менеджер существует и имеет нужную роль.

        Args:
            manager_id: ID менеджера для проверки.
            session: Асинхронная сессия базы данных.

        Raises:
            InvalidManagerError: Если менеджер не найден или не имеет
                нужной роли.

        """
        if manager_id is None or manager_id == 0:
            return  # Пустое значение допустимо

        manager_result = await session.execute(
            select(User).where(
                User.id == manager_id,
                User.role.in_(['MANAGER', 'ADMIN']),
            ),
        )
        manager = manager_result.scalars().first()
        if not manager:
            raise InvalidManagerError(manager_id)


cafe_service = CafeService()
