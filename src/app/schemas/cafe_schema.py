from datetime import datetime, time
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from ..core.constants import (
    MAX_LENGTH_ADDRESS,
    MAX_LENGTH_CAFE_NAME,
    MAX_LENGTH_CITY,
    MAX_LENGTH_DESCRIPTION,
    MAX_LENGTH_PHONE,
    MIN_LENGTH_ADDRESS,
    MIN_LENGTH_CAFE_NAME,
    MIN_LENGTH_CITY,
)
from ..validators.cafe_validators import (
    validate_manager_id,
    validate_working_hours_for_create,
    validate_working_hours_for_update,
)


class CafeBase(BaseModel):
    """Базовые поля кафе."""

    name: str = Field(
        ...,
        min_length=MIN_LENGTH_CAFE_NAME,
        max_length=MAX_LENGTH_CAFE_NAME,
    )
    city: str = Field(
        ...,
        min_length=MIN_LENGTH_CITY,
        max_length=MAX_LENGTH_CITY,
    )
    address: str = Field(
        ...,
        min_length=MIN_LENGTH_ADDRESS,
        max_length=MAX_LENGTH_ADDRESS,
    )
    open_time: time
    close_time: time
    phone: str = Field(..., max_length=MAX_LENGTH_PHONE)
    description: Optional[str] = Field(None, max_length=MAX_LENGTH_DESCRIPTION)
    is_active: bool = Field(default=True, description='Статус активности кафе')

    @field_validator('close_time')
    @classmethod
    def validate_working_hours(cls, v: time, info: Any) -> time:
        """Проверяет, что время закрытия позже времени открытия."""
        return validate_working_hours_for_create(v, info)


class CafeCreate(CafeBase):
    """Схема для создания нового кафе."""

    manager_id: Optional[int] = None

    @field_validator('manager_id')
    @classmethod
    def validate_manager_id_field(cls, v: Optional[int]) -> Optional[int]:
        """Конвертирует 0 в None для manager_id."""
        return validate_manager_id(v)


class CafeUpdate(BaseModel):
    """Схема для обновления данных кафе."""

    name: Optional[str] = Field(
        None,
        min_length=MIN_LENGTH_CAFE_NAME,
        max_length=MAX_LENGTH_CAFE_NAME,
    )
    city: Optional[str] = Field(
        None,
        min_length=MIN_LENGTH_CITY,
        max_length=MAX_LENGTH_CITY,
    )
    address: Optional[str] = Field(
        None,
        min_length=MIN_LENGTH_ADDRESS,
        max_length=MAX_LENGTH_ADDRESS,
    )
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    phone: Optional[str] = Field(None, max_length=MAX_LENGTH_PHONE)
    description: Optional[str] = Field(None, max_length=MAX_LENGTH_DESCRIPTION)
    is_active: Optional[bool] = None
    manager_id: Optional[int] = None

    @field_validator('close_time')
    @classmethod
    def validate_working_hours(
        cls,
        v: Optional[time],
        info: Any,
    ) -> Optional[time]:
        """Проверяет, что время закрытия позже времени открытия."""
        return validate_working_hours_for_update(v, info)

    @field_validator('manager_id')
    @classmethod
    def validate_manager_id_field(cls, v: Optional[int]) -> Optional[int]:
        """Конвертирует 0 в None для manager_id."""
        return validate_manager_id(v)


class CafeResponse(CafeBase):
    """Схема для возврата данных кафе."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        """Конфигурация Pydantic."""

        from_attributes = True


class ManagerShort(BaseModel):
    """Короткая схема для менеджера."""

    id: int
    name: Optional[str] = None
    phone: Optional[str] = None

    model_config = {'from_attributes': True}


class CafeWithManager(CafeResponse):
    """Схема кафе с данными управляющего."""

    # manager: Optional[dict] = None
    manager: Optional[ManagerShort] = None


class CafeWithStats(CafeWithManager):
    """Схема кафе с статистикой."""

    total_staff: int = 0
    total_shifts: int = 0
    # manager: Optional[dict] = None
    model_config = {'from_attributes': True}


class CafeShort(BaseModel):
    """Краткая информация о кафе."""

    id: int
    name: str
    city: str
    address: str
    phone: str
    is_active: bool

    open_time: time # добавила чтобы в админке было время работы кафе
    close_time: time

    class Config:
        """Конфигурация Pydantic."""

        from_attributes = True
