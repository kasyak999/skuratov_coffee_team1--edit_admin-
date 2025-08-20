from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy import Date, cast, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.expression import asc

from app.crud.base_crud import CRUDBase
from app.models.cafe import Cafe
from app.models.reservation import Reservation, Status
from app.models.shift import Shift
from app.schemas.reservation_schema import ReservationCreate, ReservationUpdate


class CRUDReservation(
    CRUDBase[Reservation, ReservationCreate, ReservationUpdate]
):
    """CRUD-класс для модели Reservation."""

    async def get_by_user(
        self,
        barista_id: int,
        session: AsyncSession,
    ) -> List[Reservation]:
        """Получить все брони пользователя."""
        db_objs = await session.execute(
            select(self.model).where(self.model.barista_id == barista_id)
        )
        return db_objs.scalars().all()

    async def get_by_shift(
        self,
        shift_id: int,
        session: AsyncSession,
    ) -> List[Reservation]:
        """Получить все брони на смену (слот)."""
        db_objs = await session.execute(
            select(self.model).where(self.model.shift_id == shift_id)
        )
        return db_objs.scalars().all()

    async def update_status(
        self,
        reservation_id: int,
        new_status: Status,
        session: AsyncSession,
    ) -> Optional[Reservation]:
        """Изменить статус брони."""
        db_obj = await self.get(reservation_id, session)
        if db_obj:
            db_obj.status = new_status
            session.add(db_obj)
            await session.commit()
            await session.refresh(db_obj)
        return db_obj

    async def cancel(
        self,
        reservation_id: int,
        session: AsyncSession,
    ) -> Optional[Reservation]:
        """Отменить бронирование."""
        return await self.update_status(
            reservation_id, Status.CANCELLED, session
        )

    async def get_by_cafe(
        self,
        cafe_id: int,
        session: AsyncSession,
    ) -> list[Reservation]:
        """Получить все брони по конкретной кофейне."""
        stmt = (
            select(Reservation)
            .join(Reservation.shift)
            .where(Shift.cafe_id == cafe_id)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    #  Добавил функцию по поиску брони по кафе и статусу для handler.

    async def get_by_cafe_and_status(
        self,
        cafe_id: int,
        status: Status,
        session: AsyncSession,
    ) -> list[Reservation]:
        """Получить все брони по конкретной кофейне и статусу."""
        stmt = (
            select(Reservation)
            .join(Reservation.shift)
            .where(Reservation.status == status and Shift.cafe_id == cafe_id)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    #  Функция выполняет только часть CRUD операций, необходимых по тз
    #  ещё часть нужно будет реализовать в handler или всю её
    #  полностью убрать в handler.

    async def get_available_slots_for_barista(
        self,
        barista_id: int,
        session: AsyncSession,
    ) -> list[Shift]:
        """Возвращает список доступных смен.

        Возможность для баристы получить
        доступные слоты на текущую и следующую неделю.
        """
        now = datetime.now()
        next_week = now + timedelta(days=14)

        stmt = (
            select(Shift)
            .where(Shift.start_time >= now)
            .where(Shift.start_time <= next_week)
            .where(
                ~Shift.reservations.any(Reservation.barista_id == barista_id)
            )
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def create_with_status(
        self,
        barista_id: int,
        shift_id: int,
        status: Status,
        session: AsyncSession,
    ) -> Reservation:
        """Создает бронирование с указанным статусом."""
        db_obj = Reservation(
            barista_id=barista_id,
            shift_id=shift_id,
            status=status,
        )
        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def get_nearest_shift(
        self,
        user_id: int,
        session: AsyncSession,
    ) -> Optional[tuple]:
        """Получает ближайшую доступную смену, начиная с текущего момента."""
        current_time = datetime.utcnow()

        result = await session.execute(
            select(Reservation, Shift, Cafe)
            .join(Shift, Reservation.shift_id == Shift.id)
            .join(Cafe, Shift.cafe_id == Cafe.id)
            .where(
                Reservation.barista_id == user_id,
                Reservation.status.in_([Status.RESERVED, Status.ONCONFIRM]),
                Shift.start_time >= current_time
            )
            .order_by(asc(Shift.start_time))
        )
        return result.first()

    async def get_all_with_related(
            self,
            session: AsyncSession,
            date_filter: Optional[date] = None,
            sort: str = "start_time_asc",
    ) -> List[Reservation]:
        """Все брони, фильтр по дате создания и сортировка по времени смены."""
        stmt = (
            select(Reservation)
            .join(Reservation.shift)
            .options(
                joinedload(Reservation.shift).joinedload(Shift.cafe),
                joinedload(Reservation.barista),
            )
        )

        if date_filter:
            stmt = stmt.where(
                cast(Reservation.created_at, Date) == date_filter
            )

        if sort == 'start_time_desc':
            stmt = stmt.order_by(Shift.start_time.desc().nulls_last())
        else:
            stmt = stmt.order_by(Shift.start_time.asc().nulls_last())

        result = await session.execute(stmt)
        rows = result.unique().scalars().all()
        return jsonable_encoder(rows)

    async def get_one_with_related(
        self, reservation_id: int, session: AsyncSession
    ) -> Optional[Reservation]:
        """Одна бронь + связанные объекты."""
        stmt = (
            select(Reservation)
            .where(Reservation.id == reservation_id)
            .options(
                joinedload(Reservation.shift).joinedload(Shift.cafe),
                joinedload(Reservation.barista),
            )
        )
        res = await session.execute(stmt)
        return res.unique().scalars().first()


reservation_crud = CRUDReservation(Reservation)
