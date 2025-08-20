import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.shift import Shift
    from app.models.user import User


class Status(str, enum.Enum):
    """Статус резервирования смены."""

    RESERVED = 'reserved'
    ATTENDED = 'attended'
    CANCELLED = 'cancelled'
    ONCONFIRM = 'onconfirm'


class Reservation(Base):
    """Модель бронирования смены."""

    __tablename__ = 'reservations'

    barista_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'),
    )
    shift_id: Mapped[int] = mapped_column(
        ForeignKey('shifts.id', ondelete='CASCADE'),
    )
    status: Mapped[Status] = mapped_column(
        SQLEnum(
            Status,
            name="status",
            native_enum=True,
            values_callable=lambda enum: [e.value for e in enum]
        ),
        nullable=False,
    )

    barista: Mapped['User'] = relationship(back_populates='reservations')
    shift: Mapped['Shift'] = relationship(back_populates='reservations')

    def __repr__(self) -> str:
        return f'<Reservation {self.id}: {self.status}>'
