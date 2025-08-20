from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    Mapped,
    declarative_base,
    mapped_column,
    sessionmaker,
)
from sqlalchemy.sql import func

from app.core.config import settings


class PreBase:
    """Базовый класс для моделей SQLAlchemy."""

    @classmethod
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


Base = declarative_base(cls=PreBase)
engine = create_async_engine(settings.database_url)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Асинхронный генератор сессий."""
    async with AsyncSessionLocal() as async_session:
        yield async_session
