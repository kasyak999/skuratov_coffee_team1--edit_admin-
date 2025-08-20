"""Константы приложения."""

from fastapi.security import HTTPBearer

# =============================================================================
# КОНСТАНТЫ ВАЛИДАЦИИ ДЛЯ КАФЕ
# =============================================================================

# Название кафе
MIN_LENGTH_CAFE_NAME = 1
MAX_LENGTH_CAFE_NAME = 255

# Город кафе
MIN_LENGTH_CITY = 1
MAX_LENGTH_CITY = 100
# Адрес кафе
MIN_LENGTH_ADDRESS = 5
MAX_LENGTH_ADDRESS = 255

# Описание кафе
MAX_LENGTH_DESCRIPTION = 1000

# Телефон кафе
MAX_LENGTH_PHONE = 20

# PHONE_REGEX = r'^\+?[1-9]\d{1,19}$'
PHONE_REGEX = r'^8\d{10}$'
# PHONE_REGEX = r'^\+[1-9]\d{9,14}$'
# Телефон кафе (наследует общие константы телефона)
CAFE_PHONE_REGEX = PHONE_REGEX

PHONE_LENGTH_MESSAGE = (
    'Введите номер телефона из 11 цифр, например: 89001234567'
)
PHONE_START_MESSAGE = (
    'Номер должен начинаться с 8 '
    'и содержать только цифры (например: 89001234567)'
)

# Для пользователя
ADMIN = 'admin'
MANAGER = 'manager'
BARISTA = 'barista'
MIN_LENGTH_NAME = 1
MIN_LENGTH_PASSWORD = 6
authorization = HTTPBearer(auto_error=False)
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Для пагинации
DEFAULT_USER_LIST_LIMIT = 50

# ==== Ошибки валидации пользователей ====
ERROR_USER_NOT_FOUND = 'Пользователь не найден'
ERROR_ONLY_BARISTA_ALLOWED = 'Действие разрешено только для бариста'
ERROR_BARISTA_ALREADY_CONFIRMED = 'Бариста уже был подтверждён ранее. ' \
    'Повторно подтверждать не нужно.'
ERROR_BARISTA_NOT_CONFIRMED = 'Этот бариста ещё не был подтвержден. ' \
    'Сначала подтвердите его.'
ERROR_WRONG_ROLE = 'Пользователь должен иметь роль {role}'
ERROR_USER_ALREADY_EXISTS = 'Пользователь с таким Telegram ID уже существует'
ERROR_INVALID_PASSWORD = 'Неверный пароль'

ERROR_USER_AUTHENTICATE = 'Неверный пароль'
ERROR_USER_ROLE = 'Вы не можете создавать пользователей с этой ролью.'
ERROR_PASSWORD_REQUIRED_FOR_ADMIN_OR_MANAGER = (
    'Для роли ADMIN или MANAGER необходим пароль'
)

# Минимальное время между сменами в часах
MIN_HOURS_BETWEEN_SHIFTS = 1

DEFAULT_SORT = 'start_time_asc'
