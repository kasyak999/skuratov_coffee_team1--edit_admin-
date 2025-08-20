from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CHAR, BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ADMIN, BARISTA, MANAGER
from app.core.db import Base

if TYPE_CHECKING:
    from app.models.cafe import Cafe
    from app.models.reservation import Reservation


class Role(str, Enum):
    """Перечисление ролей пользователя."""

    ADMIN = ADMIN
    MANAGER = MANAGER
    BARISTA = BARISTA


class User(Base):
    """Модель пользователя."""

    __tablename__ = 'users'

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        comment='Telegram ID пользователя',
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment='Полное имя пользователя',
    )
    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment='Телефон в формате 1234567890',
    )
    role: Mapped[Role] = mapped_column(
        nullable=False,
        comment='Роль пользователя',
    )
    password: Mapped[Optional[str]] = mapped_column(
        CHAR(60),
        comment='Пароль минимум 6 символов',
    )
    is_active: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment='Статус активности: подтвержден/заблокирован',
    )
    cafe_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('cafes.id'),
        nullable=True,
        comment='ID кофейни, к которой привязан пользователь',
    )

    cafe: Mapped[Optional['Cafe']] = relationship(
        'Cafe',
        foreign_keys=[cafe_id],
        back_populates='staff',
    )
    reservations: Mapped[list['Reservation']] = relationship(
        back_populates='barista',
    )

    def __repr__(self) -> str:
        return f'<Пользователь {self.id}: {self.name} ({self.role.value})>'
