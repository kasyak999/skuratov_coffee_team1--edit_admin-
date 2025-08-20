from datetime import datetime
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base_crud import CRUDBase
from app.exceptions.shift_exceptions import ShiftNotFoundError
from app.models.cafe import Cafe
from app.models.shift import Shift
from app.schemas.shift_schema import ShiftCreate, ShiftUpdate


class ShiftCRUD(CRUDBase[Shift, ShiftCreate, ShiftUpdate]):
    """CRUD операции для смен."""

    async def get_multi(
        self,
        session: AsyncSession,
        cafe_id: int | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[Shift]:
        """Получить список смен.

        Если указан cafe_id — фильтрует по кафе;
        Если указаны start_time и/или end_time — выбирает смены,
        полностью попадающие в диапазон.
        """
        query = select(self.model).options(selectinload(self.model.cafe))

        if cafe_id is not None:
            query = query.where(self.model.cafe_id == cafe_id)
        if start_time is not None:
            query = query.where(self.model.start_time >= start_time)
        if end_time is not None:
            query = query.where(self.model.end_time <= end_time)

        result = await session.execute(query)
        return result.scalars().all()

    async def get_shift_at_the_same_time(
        self,
        *,
        start_time: datetime,
        end_time: datetime,
        cafe_id: int,
        session: AsyncSession,
        shift_id: int | None = None,
    ) -> list[Shift]:
        """Найти смены, пересекающиеся с заданным интервалом.

        Выбирает все смены в заданном кафе, у которых есть пересечение
        с временным диапазоном [start_time, end_time]. Используется для
        валидации, чтобы избежать конфликтов смен.

        Если передан shift_id, то смена с этим ID исключается из результатов.
        """
        query = select(self.model).where(
            self.model.cafe_id == cafe_id,
            self.model.start_time <= end_time,
            self.model.end_time >= start_time,
        )
        if shift_id is not None:
            query = query.where(self.model.id != shift_id)

        result = await session.execute(query)
        return result.scalars().all()

    async def get_or_404(
        self,
        shift_id: int,
        session: AsyncSession,
    ) -> Shift:
        """Получить слот по ID или выбросить исключение.

        Args:
            shift_id: ID кафе.
            session: Асинхронная сессия базы данных.

        Returns:
            Объект Shift.

        Raises:
            ShiftNotFoundError: Если кафе не найдено.

        """
        shift = await self.get(shift_id, session)
        if not shift:
            raise ShiftNotFoundError(shift_id)
        return shift

    async def get_shifts_in_city(
        self,
        city: str,
        start_from: datetime,
        end_to: datetime,
        session: AsyncSession,
    ) -> List[Shift]:
        """Получает смены в указанном городе в заданном временном диапазоне."""
        stmt = (
            select(Shift)
            .join(Shift.cafe)
            .where(Cafe.city == city)
            .where(Shift.start_time >= start_from)
            .where(Shift.start_time <= end_to)
            .order_by(Shift.start_time)
        )
        result = await session.execute(stmt)
        return result.scalars().all()


shift_crud = ShiftCRUD(Shift)
