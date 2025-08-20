from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.reservation import Status
from app.schemas.shift_schema import ShiftResponse
from app.schemas.user_schema import UserRead


class ReservationBase(BaseModel):
    """Базовая схема резерваций."""

    barista_id: int
    shift_id: int
    status: Status

    # @validator('status', pre=True)
    # def validate_status(cls, value: Any) -> Status:  # noqa: N805
    #     """Валидатор для статуса бронирования."""
    #     if isinstance(value, str):
    #         try:
    #             return Status(value.lower())
    #         except ValueError as error:
    #             valid_values = [status.value for status in Status]
    #             raise ValueError(
    #                 f'Invalid status value. Must be one of: {valid_values}'
    #             ) from error
    #     return value

    model_config = {'use_enum_values': True}


class ReservationCreate(ReservationBase):
    """Схема создания резерваций."""

    pass


class ReservationUpdate(BaseModel):
    """Схема обновления резерваций."""

    status: Optional[Status] = None
    shift_id: Optional[int] = None


class ReservationRead(ReservationBase):
    """Схема чтения резерваций."""

    id: int
    created_at: datetime
    updated_at: datetime

    shift_id: int
    barista_id: int
    status: Status

    shift: Optional[ShiftResponse] = None
    barista: Optional[UserRead] = None

    class Config:
        """Конфигурация Pydantic для работы с ORM."""

        from_attributes = True
