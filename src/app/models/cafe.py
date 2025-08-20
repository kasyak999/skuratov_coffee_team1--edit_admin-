from datetime import time
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.shift import Shift
    from app.models.user import User


class Cafe(Base):
    """Модель кофейни."""

    __tablename__ = 'cafes'

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment='Название кофейни',
    )
    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment='Город',
    )
    address: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment='Адрес',
    )
    open_time: Mapped[time] = mapped_column(Time, nullable=False)
    close_time: Mapped[time] = mapped_column(Time, nullable=False)
    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment='Телефон в формате 1234567890',
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment='Статус активности кофейни',
    )
    manager_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('users.id'),
        nullable=True,
        comment='ID менеджера кофейни',
    )

    staff: Mapped[list['User']] = relationship(
        'User',
        foreign_keys='User.cafe_id',
        back_populates='cafe',
    )
    shifts: Mapped[list['Shift']] = relationship(back_populates='cafe')
    manager: Mapped[Optional['User']] = relationship(
        'User',
        foreign_keys=[manager_id],
        lazy='select',
    )

    def __repr__(self) -> str:
        return f'<Cafe {self.id}: {self.address}>'
