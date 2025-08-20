from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.cafe import Cafe
    from app.models.reservation import Reservation


class Shift(Base):
    """Модель смены бариста."""

    __tablename__ = 'shifts'

    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )
    barista_count: Mapped[int] = mapped_column(Integer, nullable=False)
    cafe_id: Mapped[int] = mapped_column(
        ForeignKey('cafes.id', ondelete='CASCADE'),
    )

    cafe: Mapped['Cafe'] = relationship(back_populates='shifts')
    reservations: Mapped[List['Reservation']] = relationship(
        back_populates='shift',
    )

    def __repr__(self) -> str:
        return f'<Смена {self.id}: {self.start_time}-{self.end_time}>'
