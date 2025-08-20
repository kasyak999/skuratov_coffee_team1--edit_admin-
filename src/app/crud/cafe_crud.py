"""CRUD операции для модели Cafe."""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base_crud import CRUDBase
from app.exceptions import CafeNotFoundError
from app.models.cafe import Cafe
from app.models.user import User
from app.schemas.cafe_schema import CafeCreate, CafeUpdate
from app.services.cafe_service import cafe_service


class CRUDCafe(CRUDBase[Cafe, CafeCreate, CafeUpdate]):
    """CRUD операции для кафе."""

    async def update(
        self,
        db_obj: Cafe,
        obj_in: CafeUpdate,
        session: AsyncSession,
    ) -> Cafe:
        """Обновить существующий объект кафе с проверкой менеджера."""
        update_data = obj_in.model_dump(exclude_unset=True)

        # Проверяем manager_id, если он указан в обновлении
        if 'manager_id' in update_data:
            manager_id = update_data['manager_id']
            await cafe_service.validate_manager(manager_id, session)
            # Конвертируем 0 в None (уже обработано в валидаторе)
            if manager_id == 0:
                update_data['manager_id'] = None

        # Обновляем поля объекта
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def create(
        self,
        obj_in: CafeCreate,
        session: AsyncSession,
        user: Optional[User] = None,
    ) -> Cafe:
        """Создать новое кафе с проверкой менеджера."""
        obj_in_data = obj_in.model_dump()

        # Проверяем manager_id, если он указан
        manager_id = obj_in_data.get('manager_id')
        await cafe_service.validate_manager(manager_id, session)

        if user is not None:
            obj_in_data['user_id'] = user.id

        db_obj = self.model(**obj_in_data)
        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def get_with_manager(
        self,
        cafe_id: int,
        session: AsyncSession,
    ) -> Optional[Cafe]:
        """Получить кафе с информацией о менеджере.

        Args:
            cafe_id: ID кафе.
            session: Асинхронная сессия базы данных.

        Returns:
            Объект кафе с загруженным менеджером или None.

        """
        result = await session.execute(
            select(self.model)
            .options(selectinload(self.model.manager))
            .where(self.model.id == cafe_id),
        )
        return result.scalars().first()

    async def get_multi_with_manager(
        self,
        session: AsyncSession,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Cafe]:
        """Получить список кафе с информацией о менеджерах.

        Args:
            session: Асинхронная сессия базы данных.
            skip: Количество записей для пропуска.
            limit: Максимальное количество возвращаемых записей.

        Returns:
            Список кафе с загруженными менеджерами.

        """
        result = await session.execute(
            select(self.model)
            .options(selectinload(self.model.manager))
            .offset(skip)
            .limit(limit),
        )
        return list(result.scalars().all())

    async def get_by_manager(
        self,
        manager_id: int,
        session: AsyncSession,
    ) -> List[Cafe]:
        """Получить кафе по ID менеджера.

        Args:
            manager_id: ID менеджера.
            session: Асинхронная сессия базы данных.

        Returns:
            Список кафе, управляемых данным менеджером.

        """
        result = await session.execute(
            select(self.model).where(self.model.manager_id == manager_id),
        )
        return list(result.scalars().all())

    async def get_with_stats(
        self,
        cafe_id: int,
        session: AsyncSession,
    ) -> Optional[Cafe]:
        """Получить кафе со статистикой персонала и смен.

        Args:
            cafe_id: ID кафе.
            session: Асинхронная сессия базы данных.

        Returns:
            Объект кафе с загруженными связями или None.

        """
        result = await session.execute(
            select(self.model)
            .options(
                selectinload(self.model.staff),
                selectinload(self.model.shifts),
                selectinload(self.model.manager),
            )
            .where(self.model.id == cafe_id),
        )
        return result.scalars().first()

    async def search_by_address(
        self,
        address_pattern: str,
        session: AsyncSession,
        limit: int = 10,
    ) -> List[Cafe]:
        """Поиск кафе по адресу.

        Args:
            address_pattern: Паттерн для поиска в адресе.
            session: Асинхронная сессия базы данных.
            limit: Максимальное количество результатов.

        Returns:
            Список найденных кафе.

        """
        result = await session.execute(
            select(self.model)
            .where(self.model.address.ilike(f'%{address_pattern}%'))
            .limit(limit),
        )
        return list(result.scalars().all())

    async def assign_manager(
        self,
        cafe_id: int,
        manager_id: Optional[int],
        session: AsyncSession,
    ) -> Cafe:
        """Назначить или удалить менеджера кафе.

        Args:
            cafe_id: ID кафе.
            manager_id: ID менеджера (None для удаления).
            session: Асинхронная сессия базы данных.

        Returns:
            Обновленный объект кафе.

        Raises:
            CafeNotFoundError: Если кафе не найдено.
            InvalidManagerError: Если менеджер невалидный.

        """
        cafe = await self.get_or_404(cafe_id, session)

        # Проверяем, что менеджер существует и имеет соответствующую роль
        await cafe_service.validate_manager(manager_id, session)

        cafe.manager_id = manager_id
        session.add(cafe)
        await session.commit()
        await session.refresh(cafe)
        return cafe

    async def get_or_404(
        self,
        cafe_id: int,
        session: AsyncSession,
    ) -> Cafe:
        """Получить кафе по ID или выбросить исключение.

        Args:
            cafe_id: ID кафе.
            session: Асинхронная сессия базы данных.

        Returns:
            Объект кафе.

        Raises:
            CafeNotFoundError: Если кафе не найдено.

        """
        cafe = await self.get(cafe_id, session)
        if not cafe:
            raise CafeNotFoundError(cafe_id)
        return cafe


# Создаем экземпляр CRUD для кафе
cafe_crud = CRUDCafe(Cafe)
