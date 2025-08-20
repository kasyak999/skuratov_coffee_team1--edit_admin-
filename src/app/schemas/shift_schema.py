from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, validator


class ShiftBase(BaseModel):
    """Базовая схема."""

    start_time: datetime
    end_time: datetime
    barista_count: int = Field(1, ge=1, le=5)
    cafe_id: int

    @classmethod
    @validator('end_time')
    def validate_time_range(
        cls,  # Тип валидатора (класс, не self)
        v: datetime,  # Значение поля 'end_time', которое проверяем
        values: Dict[str, Any],  # Словарь с уже проверенными значениями модели
    ) -> datetime:  # Возвращаем то же значение datetime
        """Проверяет, что end_time позже start_time.

        Args:
            v: Текущее значение поля end_time.
            values: Словарь с уже валидированными полями модели.

        Returns:
            datetime: Возвращает v, если валидация успешна.

        Raises:
            ValueError: Если end_time <= start_time.

        """
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('Конец слота должен быть позже начала')
        return v  # Возвращаем значение для присвоения полю end_time


class ShiftCreate(ShiftBase):
    """Класс создания слота."""

    pass


class ShiftUpdate(BaseModel):
    """Класс обновления."""

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    barista_count: Optional[int] = Field(None, ge=1, le=5)
    cafe_id: Optional[int] = None


class ShiftResponse(ShiftBase):
    """Класс ответов на запрос по конкретному слоту."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        """Класс кофигурации."""

        from_attributes = True
