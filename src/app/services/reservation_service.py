# app/services/reservation_service.py

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.reservation_crud import reservation_crud
from app.crud.shift_crud import shift_crud
from app.models.reservation import Reservation, Status
from app.models.shift import Shift
from app.schemas.reservation_schema import ReservationCreate

_SORT = {
    'start_time_asc':  (Shift.start_time.asc(),  Reservation.id.asc()),
    'start_time_desc': (Shift.start_time.desc(), Reservation.id.asc()),
    'created_at_asc':  (Reservation.created_at.asc(),  Reservation.id.asc()),
    'created_at_desc': (Reservation.created_at.desc(), Reservation.id.asc()),
}


class ReservationService:
    """Сервис для работы с бронированием."""

    @staticmethod
    async def create_reservation(
        data: ReservationCreate, session: AsyncSession
    ) -> Optional[Reservation]:
        """Создание бронирования."""
        # Проверить: shift существует?
        shift = await shift_crud.get(data.shift_id, session)
        if not shift:
            raise ValueError('Смена не найдена.')

        # Проверить: не превышен ли лимит бариста в смене?
        reservations = await reservation_crud.get_by_shift(
            data.shift_id, session
        )
        if len(reservations) >= shift.max_baristas:
            raise ValueError('Лимит бариста на смену уже достигнут!')

        # Проверить: нет ли уже активной брони у этого бариста на эту смену?
        user_reservations = await reservation_crud.get_by_user(
            data.barista_id, session
        )
        exists = any(
            r.shift_id == data.shift_id and r.status != Status.CANCELLED
            for r in user_reservations
        )
        if exists:
            raise ValueError('Бронь на эту смену уже существует!')

        # Если всё ок — создать бронирование через CRUD
        # Здесь можно вызвать Celery — отправить уведомление управляющему
        # и/или бариста.
        # await send_notification_async(...)

        return await reservation_crud.create(data, session)

    @staticmethod
    async def cancel_reservation(
        reservation_id: int, session: AsyncSession
    ) -> Optional[Reservation]:
        """Отмена бронирования."""
        # Логика отмены с бизнес-проверками — например, нельзя отменить
        # “задним числом”
        reservation = await reservation_crud.get(reservation_id, session)
        if not reservation:
            raise ValueError('Бронь не найдена.')
        # Можно добавить: проверку прав пользователя и времени!
        return await reservation_crud.cancel(reservation_id, session)

    @staticmethod
    async def update_reservation_status(
        reservation_id: int, new_status: Status, session: AsyncSession
    ) -> Optional[Reservation]:
        """Обновление статуса броинрования."""
        reservation = await reservation_crud.get(reservation_id, session)
        if not reservation:
            raise ValueError('Бронь не найдена.')
        # Можно добавить бизнес-валидацию: только управляющий может
        # "confirmed", только актуальные слоты и т. д.
        return await reservation_crud.update_status(
            reservation_id, new_status, session
        )

    @staticmethod
    async def get_available_shifts_for_barista(
        barista_id: int, session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Возвращает список смен, доступных для бронирования бариста."""
        # Реализация — см. метод в reservation_crud;
        # здесь может быть добавлена фильтрация/расширенная логика
        return await reservation_crud.get_available_slots_for_barista(
            barista_id, session
        )

    @staticmethod
    async def change_shift_booking(
        shift_id: int,
        old_barista_id: int,
        new_barista_id: int,  # Можно None, если просто снимаем бронь
        session: AsyncSession,
    ) -> Optional[Reservation]:
        """Меняет бронирование: снимает или назначает бариста."""
        # Найти существующую бронь barista на эту смену
        reservations = await reservation_crud.get_by_shift(shift_id, session)
        existing = None
        for r in reservations:
            if r.barista_id == old_barista_id and r.status != Status.CANCELLED:
                existing = r
                break

        # Снимаем бронь с бариста-старого
        if existing:
            await reservation_crud.update_status(
                existing.id, Status.CANCELLED, session
            )

        # Если назначаем нового бариста
        if new_barista_id:
            # Проверить: нет ли уже брони для нового на эту смену
            for r in reservations:
                if (
                    r.barista_id == new_barista_id
                    and r.status != Status.CANCELLED
                ):
                    raise ValueError('Новый бариста уже записан на эту смену!')
            # Создать новую бронь
            data = ReservationCreate(
                barista_id=new_barista_id,
                shift_id=shift_id,
                status=Status.RESERVED,
            )
            return await reservation_crud.create(data, session)

        # Если просто сняли бронь
        return None

    @staticmethod
    async def barista_confirm_going(
        barista_id: int, session: AsyncSession
    ) -> Reservation:
        """Подтверждает выход бариста на текущую смену."""
        # Получаем актуальные резервации этого бариста
        reservations = await reservation_crud.get_by_user(barista_id, session)
        # Оставляем только будущие (или текущие!) с RESERVED
        now = datetime.now()
        active_reservations = [
            r
            for r in reservations
            if (
                r.status == Status.RESERVED
                and r.shift.start_time <= now <= r.shift.end_time
            )
        ]
        if not active_reservations:
            raise ValueError('Нет актуальной смены для подтверждения!')
        # Берём ближайшую (или единственную)
        reservation = active_reservations[0]
        await reservation_crud.update_status(
            reservation.id, Status.ATTENDED, session
        )
        return reservation


reservation_service = ReservationService()
