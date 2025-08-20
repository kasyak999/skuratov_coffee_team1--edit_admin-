"""API endpoints для управления кафе."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.crud.shift_crud import shift_crud
from app.decorators import handle_errors
from app.schemas.shift_schema import ShiftCreate, ShiftResponse, ShiftUpdate

router = APIRouter(prefix='/shifts', tags=['shifts'])


@router.post(
    '/',
    response_model=ShiftResponse,
    status_code=status.HTTP_201_CREATED,
    summary='Создать слот',
    description='Создание слота.Только управляющим и администраторам.',
)
@handle_errors
async def create_shift(
    shift_data: ShiftCreate,
    session: AsyncSession = Depends(get_async_session),
) -> ShiftResponse:
    """Создать новый слот."""
    shift = await shift_crud.create(shift_data, session)
    return ShiftResponse.model_validate(shift)

#
# @router.get(
#     '/',
#     response_model=List[ShiftResponse],
#     summary='Получить список слотов',
#     description='Получение списка всех слотов кафе.',
# )
# @handle_errors
# async def get_shifts(
#     skip: int = Query(
#     0, ge=0, description='Количество записей для пропуска'),
#     limit: int = Query(
#         100,
#         ge=1,
#         le=1000,
#         description='Максимальное количество записей',
#     ),
#     session: AsyncSession = Depends(get_async_session),
# ) -> List[ShiftResponse]:
#     """Получить список слотов."""
#     shifts = await shift_crud.get_multi(session)
#     return [ShiftResponse.model_validate(shift) for shift in shifts]


@router.get(
    '/',
    response_model=List[ShiftResponse],
    summary='Получить список слотов',
    description='Получение списка слотов с фильтрами и пагинацией.',
)
@handle_errors
async def get_shifts(
    cafe_id: Optional[int] = Query(
        None, description='ID кофейни'),
    start_from: Optional[datetime] = Query(
        None, description='Начало не раньше'),
    start_to: Optional[datetime]   = Query(
        None, description='Начало не позже'),
    skip: int = Query(
        0, ge=0, description='Сколько пропустить'),
    limit: int = Query(
        100, ge=1, le=1000, description='Сколько вернуть'),
    session: AsyncSession = Depends(get_async_session),
) -> List[ShiftResponse]:
    """Получить список слотов2."""
    shifts_all = await shift_crud.get_multi(
        session=session,
        cafe_id=cafe_id,
        start_time=start_from,
        end_time=start_to,
    )
    page = shifts_all[skip: skip + limit]
    # схема изменена для админки
    return [ShiftResponse.model_validate(s) for s in page]


@router.get(
    '/{shift_id}',
    response_model=ShiftResponse,
    summary='Получить слот по ID',
    description='Получение детальную информацию о слоте по его ID.',
)
@handle_errors
async def get_shift(
    shift_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> ShiftResponse:
    """Получить слот по ID."""
    shift = await shift_crud.get_or_404(shift_id, session)
    return ShiftResponse.model_validate(shift)


@router.put(
    '/{shift_id}',
    response_model=ShiftResponse,
    summary='Обновить слот',
    description='Обновление информации о слоте. Доступно администраторам.',
)
@handle_errors
async def update_shift(
    shift_id: int,
    shift_update: ShiftUpdate,
    session: AsyncSession = Depends(get_async_session),
) -> ShiftResponse:
    """Обновить информацию о слоте."""
    shift = await shift_crud.get_or_404(shift_id, session)
    updated_shift = await shift_crud.update(shift, shift_update, session)
    return ShiftResponse.model_validate(updated_shift)


@router.delete(
    '/{shift_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Удалить слот',
    description='Удаление слота.Доступно только управляющим и администраторам',
)
@handle_errors
async def delete_shift(
    shift_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Удалить кафе."""
    shift = await shift_crud.get_or_404(shift_id, session)
    await shift_crud.remove(shift, session)
