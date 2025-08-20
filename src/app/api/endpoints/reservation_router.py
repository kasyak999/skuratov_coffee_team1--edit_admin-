"""Endpoints for Reservation operations."""

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.crud.reservation_crud import reservation_crud
from app.schemas.reservation_schema import (
    ReservationCreate,
    ReservationRead,
    ReservationUpdate,
)
from app.schemas.shift_schema import ShiftResponse
from app.services.reservation_service import reservation_service

router = APIRouter(prefix='/reservations', tags=['Reservations'])


@router.post('/', response_model=ReservationRead)
async def create_reservation(
    reservation_in: ReservationCreate,
    session: AsyncSession = Depends(get_async_session),
) -> ReservationRead:
    """Создать новую бронь на смену."""
    return await reservation_crud.create(reservation_in, session)


@router.get('/all', response_model=List[ReservationRead])
async def get_all_reservations(
    date_filter: Optional[date] = Query(
        default=None,
        description='Фильтр по дате создания резервации'
    ),
    sort: str = Query(default='start_time_asc'),
    session: AsyncSession = Depends(get_async_session),
) -> List[ReservationRead]:
    """Получить все бронирования (можно фильтровать по дате создания)."""
    return await reservation_crud.get_all_with_related(session, date_filter)


@router.get('/{reservation_id}', response_model=ReservationRead)
async def get_reservation_by_id(
    reservation_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> ReservationRead:
    """Получить резервацию по её ID."""
    # reservation = await reservation_crud.get(reservation_id, session)
    reservation = await reservation_crud.get_one_with_related(
        reservation_id,
        session
    )
    if not reservation:
        raise HTTPException(status_code=404, detail='Reservation not found')
    return reservation


@router.patch('/{reservation_id}/status', response_model=ReservationRead)
async def update_reservation_status(
    reservation_id: int,
    status_in: ReservationUpdate,
    session: AsyncSession = Depends(get_async_session),
) -> ReservationRead:
    """Обновить статус бронирования."""
    updated = await reservation_crud.update_status(
        reservation_id, status_in.status, session
    )
    if not updated:
        raise HTTPException(status_code=404, detail='Reservation not found')
    # return updated
    return await reservation_crud.get_one_with_related(reservation_id, session)


@router.delete('/{reservation_id}', response_model=ReservationRead)
async def cancel_reservation(
    reservation_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> ReservationRead:
    """Отменить бронирование."""
    cancelled = await reservation_crud.cancel(reservation_id, session)
    if not cancelled:
        raise HTTPException(status_code=404, detail='Reservation not found')
    # return cancelled
    return await reservation_crud.get_one_with_related(reservation_id, session)


@router.get('/cafe/{cafe_id}', response_model=List[ReservationRead])
async def get_reservations_by_cafe(
    cafe_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> List[ReservationRead]:
    """Получить все резервации по ID кофейни."""
    return await reservation_crud.get_by_cafe(cafe_id, session)


@router.get('/available/', response_model=List[ShiftResponse])
async def get_available_slots(
    user_id: int,  # временно, пока нет авторизации
    session: AsyncSession = Depends(get_async_session),
) -> List[ShiftResponse]:
    """Получить доступные для бронирования смены для бариста."""
    return await reservation_crud.get_available_slots_for_barista(
        user_id, session
    )


@router.get('/user/{user_id}', response_model=List[ReservationRead])
async def get_reservations_by_user(
    user_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> List[ReservationRead]:
    """Получить все резервации для указанного пользователя."""
    return await reservation_crud.get_by_user(user_id, session)


@router.get('/shift/{shift_id}', response_model=List[ReservationRead])
async def get_reservations_by_shift(
    shift_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> List[ReservationRead]:
    """Получить все резервации для указанного слота (смены)."""
    return await reservation_crud.get_by_shift(shift_id, session)


class ChangeBookingRequest(BaseModel):
    """Схема запроса на изменение бронирования смены."""

    shift_id: int
    old_barista_id: int
    new_barista_id: Optional[int] = None  # None если просто снять бронь


@router.post('/change_booking')
async def change_booking(
    req: ChangeBookingRequest,
    session: AsyncSession = Depends(get_async_session),
) -> Dict[str, str]:
    """Менеджер: изменить бронирование смены.

    barista -> другой barista, или снять бронь вовсе.
    """
    try:
        result = await reservation_service.change_shift_booking(
            shift_id=req.shift_id,
            old_barista_id=req.old_barista_id,
            new_barista_id=req.new_barista_id,
            session=session,
        )
        return {'detail': 'Booking changed', 'reservation': result}
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post('/going')
async def barista_going(
    barista_id: int,  # или брать из токена,
    # если есть авторизация/аутентификация!
    session: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """Бариста: подтверждение выхода на смену (кнопка "Я вышел на смену")."""
    try:
        reservation = await reservation_service.barista_confirm_going(
            barista_id, session
        )
        return {
            'detail': 'Выход на смену подтверждён',
            'reservation': reservation,
        }
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
