from datetime import datetime
from typing import Optional, Self

# from app.validators.base_validators import validate_phone_number
import bcrypt
from fastapi import Form
from pydantic import BaseModel, Field, field_validator

from app.core.constants import (
    MIN_LENGTH_NAME,
    MIN_LENGTH_PASSWORD,
)
from app.models import Role


def validate_and_hash_password(password_value: str) -> str:
    """Хеширует пароль с использованием bcrypt."""
    if password_value:
        pwd_bytes = password_value.encode('utf-8')  # Пароль в байты
        salt = bcrypt.gensalt()  # Генерация "соли"
        hashed = bcrypt.hashpw(pwd_bytes, salt)
        return hashed.decode('utf-8')  # Возвращаем строку
    return password_value


class UserBase(BaseModel):
    """Базовые поля пользователя."""

    telegram_id: int
    name: str = Field(..., min_length=MIN_LENGTH_NAME)
    phone: str
    cafe_id: Optional[int] = Field(None)
    role: Role = Field(Role.BARISTA)

    # @field_validator('phone', mode='before')
    # def validate_phone(cls, value: str) -> str:
    #     """Очищает и валидирует номер телефона перед сохранением."""
    #     is_valid, result = validate_phone_number(value)
    #     if not is_valid:
    #         raise ValidationError(result)
    #     return result


class UserCreate(UserBase):
    """Схема для создания нового пользователя."""

    password: Optional[str] = Field(
        default=None, min_length=MIN_LENGTH_PASSWORD
    )

    @field_validator('password')
    @classmethod
    def validate_password(cls, password_value: str) -> str:
        """Валидация пароля."""
        return validate_and_hash_password(password_value)


class UserRead(UserBase):
    """Схема для получения данных пользователя."""

    id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool

    model_config = {
        'from_attributes': True
    }


class UserUpdate(BaseModel):
    """Схема для обновления данных пользователя."""

    name: Optional[str] = Field(None, min_length=MIN_LENGTH_NAME)
    phone: Optional[str] = Field(None)
    role: Optional[Role] = Field(None)
    cafe_id: Optional[int] = Field(None)
    password: Optional[str] = Field(
        default=None, min_length=MIN_LENGTH_PASSWORD)
    is_active: Optional[bool] = Field(None)

    @field_validator('password')
    @classmethod
    def validate_password(cls, password_value: str) -> str:
        """Валидация пароля."""
        return validate_and_hash_password(password_value)


class UserRequest(BaseModel):
    """Схема для авторизации пользователя."""

    telegram_id: int = Field(...)
    password: str = Field(...)

    @classmethod
    def as_form(
        cls,
        telegram_id: int = Form(..., description='Telegram ID'),
        password: str = Form(...),
    ) -> Self:
        """Создание экземпляра из формы."""
        return cls(telegram_id=telegram_id, password=password)


class UserResponse(BaseModel):
    """Получение токена доступа после авторизации."""

    access_token: str
    token_type: str
