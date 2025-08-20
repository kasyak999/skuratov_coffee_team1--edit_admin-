import re

from app.core.constants import PHONE_LENGTH_MESSAGE, PHONE_START_MESSAGE


def clean_phone_number(phone_number: str) -> str:
    """Приводит номер к формату: 8XXXXXXXXXX."""
    digits = re.sub(r'\D', '', phone_number)
    if digits.startswith('7') and len(digits) == 11:
        return '8' + digits[1:]
    if digits.startswith('9') and len(digits) == 10:
        return '8' + digits
    if digits.startswith('8') and len(digits) == 11:
        return digits
    return digits


def validate_phone_number(phone_number: str) -> tuple[bool, str]:
    """Проверяет номер на соответствие формату."""
    cleaned = clean_phone_number(phone_number)
    if not re.fullmatch(r'^8\d{10}$', cleaned):
        if len(cleaned) != 11:
            return False, PHONE_LENGTH_MESSAGE
        return False, PHONE_START_MESSAGE
    return True, cleaned
