"""Валидаторы для модели кафе."""

from datetime import time
from typing import Any, Optional


def validate_working_hours_for_create(v: time, info: Any) -> time:
    """Проверяет, что время закрытия позже времени открытия для создания."""
    if hasattr(info, 'data') and 'open_time' in info.data:
        open_time = info.data['open_time']
        if v <= open_time:
            raise ValueError(
                'Время закрытия должно быть позже времени открытия',
            )
    return v


def validate_working_hours_for_update(
    v: Optional[time],
    info: Any,
) -> Optional[time]:
    """Проверяет, что время закрытия позже времени открытия для обновления."""
    if (
        v is not None
        and hasattr(info, 'data')
        and 'open_time' in info.data
        and info.data['open_time'] is not None
        and v <= info.data['open_time']
    ):
        raise ValueError(
            'Время закрытия должно быть позже времени открытия',
        )
    return v


def validate_manager_id(v: Optional[int]) -> Optional[int]:
    """Конвертирует 0 в None для manager_id."""
    if v == 0:
        return None
    return v
