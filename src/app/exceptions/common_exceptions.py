"""Общие кастомные исключения."""


class BaseAppException(Exception):
    """Базовое исключение приложения."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        """Инициализация базового исключения."""
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(BaseAppException):
    """Ошибка валидации данных."""

    def __init__(self, message: str) -> None:
        """Инициализация ошибки валидации."""
        super().__init__(message, status_code=400)


class NotFoundError(BaseAppException):
    """Ошибка - ресурс не найден."""

    def __init__(self, message: str) -> None:
        """Инициализация ошибки 'не найдено'."""
        super().__init__(message, status_code=404)


class ServerError(BaseAppException):
    """Внутренняя ошибка сервера."""

    def __init__(self, message: str) -> None:
        """Инициализация серверной ошибки."""
        super().__init__(message, status_code=500)
