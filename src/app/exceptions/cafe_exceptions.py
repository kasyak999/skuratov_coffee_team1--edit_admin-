"""Исключения для работы с кафе."""

from .common_exceptions import NotFoundError, ValidationError


class CafeNotFoundError(NotFoundError):
    """Кафе не найдено."""

    def __init__(self, cafe_id: int) -> None:
        """Инициализация ошибки - кафе не найдено."""
        super().__init__(f'Кафе с ID {cafe_id} не найдено')


class InvalidManagerError(ValidationError):
    """Неверный менеджер."""

    def __init__(self, manager_id: int) -> None:
        """Инициализация ошибки - неверный менеджер."""
        super().__init__(
            f'Пользователь с ID {manager_id} не найден или не имеет '
            f'роли менеджера/администратора',
        )


class CafeValidationError(ValidationError):
    """Ошибка валидации данных кафе."""

    def __init__(self, message: str) -> None:
        """Инициализация ошибки валидации кафе."""
        super().__init__(f'Ошибка валидации кафе: {message}')


class ManagerAssignmentError(ValidationError):
    """Ошибка назначения менеджера."""

    def __init__(self, message: str) -> None:
        """Инициализация ошибки назначения менеджера."""
        super().__init__(f'Ошибка назначения менеджера: {message}')
