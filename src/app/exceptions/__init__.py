"""Кастомные исключения приложения."""

from .cafe_exceptions import (
    CafeNotFoundError,
    CafeValidationError,
    InvalidManagerError,
    ManagerAssignmentError,
)
from .common_exceptions import (
    BaseAppException,
    NotFoundError,
    ServerError,
    ValidationError,
)

__all__ = [
    'BaseAppException',
    'ValidationError',
    'NotFoundError',
    'ServerError',
    'CafeNotFoundError',
    'CafeValidationError',
    'InvalidManagerError',
    'ManagerAssignmentError',
]
