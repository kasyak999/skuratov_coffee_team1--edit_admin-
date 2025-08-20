from typing import Optional

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.crud.user_crud import crud_user
from app.models import Role
from app.schemas import UserCreate


async def add_admin() -> Optional[None]:
    """Создание админа."""
    async with AsyncSessionLocal() as session:
        result = await crud_user.get_by_telegram_id(
            int(settings.superuser_telegram_id), session
        )
        if result is None:
            user_in = UserCreate(
                name=settings.superuser_name,
                telegram_id=int(settings.superuser_telegram_id),
                phone=settings.superuser_phone,
                password=settings.superuser_password,
                cafe_id=None,
                role=Role.BARISTA,
            )
            result = await crud_user.create(user_in, session)
            result.role = Role.ADMIN
            await session.commit()
