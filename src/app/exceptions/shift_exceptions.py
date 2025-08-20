"""Исключения для работы с кафе."""

from .common_exceptions import NotFoundError, ValidationError


class ShiftNotFoundError(NotFoundError):
    """Слот не найдено."""

    def __init__(self, shift_id: int) -> None:
        """Инициализация ошибки - слот не найден."""
        super().__init__(f'Кафе с ID {shift_id} не найдено')


class ShiftValidationError(ValidationError):
    """Ошибка валидации данных кафе."""

    def __init__(self, message: str) -> None:
        """Инициализация ошибки валидации слота."""
        super().__init__(f'Ошибка валидации слота: {message}')
