"""API endpoints для управления кафе."""

from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.crud.cafe_crud import cafe_crud
from app.decorators import handle_errors
from app.schemas.cafe_schema import (
    CafeCreate,
    CafeResponse,
    CafeShort,
    CafeUpdate,
    CafeWithManager,
    CafeWithStats,
)

router = APIRouter(prefix='/cafes', tags=['cafes'])


@router.post(
    '/',
    response_model=CafeResponse,
    status_code=status.HTTP_201_CREATED,
    summary='Создать кафе',
    description='Создание нового кафе. Доступно только администраторам.',
)
@handle_errors
async def create_cafe(
    cafe_data: CafeCreate,
    session: AsyncSession = Depends(get_async_session),
) -> CafeResponse:
    """Создать новое кафе."""
    cafe = await cafe_crud.create(cafe_data, session)
    return CafeResponse.model_validate(cafe)


@router.get(
    '/',
    response_model=List[CafeShort],
    summary='Получить список кафе',
    description='Получение списка всех кафе с базовой информацией.',
)
@handle_errors
async def get_cafes(
    skip: int = Query(0, ge=0, description='Количество записей для пропуска'),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description='Максимальное количество записей',
    ),
    session: AsyncSession = Depends(get_async_session),
) -> List[CafeShort]:
    """Получить список кафе с базовой информацией."""
    cafes = await cafe_crud.get_multi(session)
    return [CafeShort.model_validate(cafe) for cafe in cafes]


@router.get(
    '/with-managers',
    response_model=List[CafeWithManager],
    summary='Получить список кафе с менеджерами',
    description='Получение списка кафе с информацией о менеджерах.',
)
@handle_errors
async def get_cafes_with_managers(
    skip: int = Query(0, ge=0, description='Количество записей для пропуска'),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description='Максимальное количество записей',
    ),
    session: AsyncSession = Depends(get_async_session),
) -> List[CafeWithManager]:
    """Получить список кафе с информацией о менеджерах."""
    cafes = await cafe_crud.get_multi_with_manager(session, skip, limit)
    return [CafeWithManager.model_validate(cafe) for cafe in cafes]


@router.get(
    '/{cafe_id}',
    response_model=CafeResponse,
    summary='Получить кафе по ID',
    description='Получение детальной информации о кафе по его ID.',
)
@handle_errors
async def get_cafe(
    cafe_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> CafeResponse:
    """Получить кафе по ID."""
    cafe = await cafe_crud.get_or_404(cafe_id, session)
    return CafeResponse.model_validate(cafe)


@router.get(
    '/{cafe_id}/with-manager',
    response_model=CafeWithManager,
    summary='Получить кафе с менеджером',
    description='Получение информации о кафе с данными менеджера.',
)
@handle_errors
async def get_cafe_with_manager(
    cafe_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> CafeWithManager:
    """Получить кафе с информацией о менеджере."""
    # Сначала проверим что кафе существует
    await cafe_crud.get_or_404(cafe_id, session)
    # Затем получим с менеджером
    cafe = await cafe_crud.get_with_manager(cafe_id, session)
    return CafeWithManager.model_validate(cafe)

#
# @router.get(
#     '/{cafe_id}/stats',
#     response_model=CafeWithStats,
#     summary='Получить кафе со статистикой',
#     description='Получение информации о кафе со статистикой.',
# )
# @handle_errors
# async def get_cafe_with_stats(
#     cafe_id: int,
#     session: AsyncSession = Depends(get_async_session),
# ) -> CafeWithStats:
#     """Получить кафе со статистикой."""
#     # Сначала проверим что кафе существует
#     await cafe_crud.get_or_404(cafe_id, session)
#     # Затем получим со статистикой
#     cafe = await cafe_crud.get_with_stats(cafe_id, session)
#
#     # Подсчитываем статистику
#     # Cafe не может быть None, так как мы уже проверили его существование
#     total_staff = len(cafe.staff) if cafe and cafe.staff else 0
#     total_shifts = len(cafe.shifts) if cafe and cafe.shifts else 0
#
#     # Создаем объект ответа с вычисленной статистикой
#     cafe_dict = cafe.__dict__.copy()
#     cafe_dict['total_staff'] = total_staff
#     cafe_dict['total_shifts'] = total_shifts
#
#     return CafeWithStats.model_validate(cafe_dict)


@router.get(
    '/{cafe_id}/stats',
    response_model=CafeWithStats,
    summary='Получить кафе со статистикой',
    description='Получение информации о кафе со статистикой.',
)
@handle_errors
async def get_cafe_with_stats(
    cafe_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> CafeWithStats:
    """Получить кафе со статистикой."""
    await cafe_crud.get_or_404(cafe_id, session)
    cafe = await cafe_crud.get_with_stats(cafe_id, session)
    staff = list(cafe.staff or [])
    shifts = list(cafe.shifts or [])

    total_staff = len({u.id for u in staff})
    total_shifts = len(shifts)

    base = CafeWithManager.model_validate(
        cafe,
        from_attributes=True
    ).model_dump()
    base['total_staff'] = total_staff
    base['total_shifts'] = total_shifts

    return CafeWithStats.model_validate(base)


@router.put(
    '/{cafe_id}',
    response_model=CafeResponse,
    summary='Обновить кафе',
    description='Обновление информации о кафе. Доступно администраторам.',
)
@handle_errors
async def update_cafe(
    cafe_id: int,
    cafe_update: CafeUpdate,
    session: AsyncSession = Depends(get_async_session),
) -> CafeResponse:
    """Обновить информацию о кафе."""
    cafe = await cafe_crud.get_or_404(cafe_id, session)
    updated_cafe = await cafe_crud.update(cafe, cafe_update, session)
    return CafeResponse.model_validate(updated_cafe)


@router.patch(
    '/{cafe_id}/manager',
    response_model=CafeWithManager,
    summary='Назначить менеджера кафе',
    description='Назначение или удаление менеджера кафе.',
)
@handle_errors
async def assign_cafe_manager(
    cafe_id: int,
    manager_id: int = Query(
        None,
        description='ID менеджера (null для удаления)',
    ),
    session: AsyncSession = Depends(get_async_session),
) -> CafeWithManager:
    """Назначить или удалить менеджера кафе."""
    await cafe_crud.assign_manager(cafe_id, manager_id, session)

    # Загружаем кафе с менеджером для ответа
    cafe_with_manager = await cafe_crud.get_with_manager(cafe_id, session)
    return CafeWithManager.model_validate(cafe_with_manager)


@router.get(
    '/search/',
    response_model=List[CafeShort],
    summary='Поиск кафе по адресу',
    description='Поиск кафе по части адреса.',
)
@handle_errors
async def search_cafes(
    address: str = Query(..., description='Часть адреса для поиска'),
    limit: int = Query(
        10,
        ge=1,
        le=100,
        description='Максимальное количество результатов',
    ),
    session: AsyncSession = Depends(get_async_session),
) -> List[CafeShort]:
    """Поиск кафе по адресу."""
    cafes = await cafe_crud.search_by_address(address, session, limit)
    return [CafeShort.model_validate(cafe) for cafe in cafes]


@router.get(
    '/manager/{manager_id}',
    response_model=List[CafeShort],
    summary='Получить кафе по менеджеру',
    description='Получение списка кафе, управляемых определенным менеджером.',
)
@handle_errors
async def get_cafes_by_manager(
    manager_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> List[CafeShort]:
    """Получить кафе по ID менеджера."""
    cafes = await cafe_crud.get_by_manager(manager_id, session)
    return [CafeShort.model_validate(cafe) for cafe in cafes]


@router.delete(
    '/{cafe_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Удалить кафе',
    description='Удаление кафе. Доступно только администраторам.',
)
@handle_errors
async def delete_cafe(
    cafe_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Удалить кафе."""
    cafe = await cafe_crud.get_or_404(cafe_id, session)
    await cafe_crud.remove(cafe, session)
