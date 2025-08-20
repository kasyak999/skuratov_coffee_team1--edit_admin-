import logging
from typing import Any, Dict

from celery import shared_task

from app.core.config import settings

logger = logging.getLogger(__name__)


@shared_task(name='notify_manager_about_barista')
def notify_manager_about_barista(
    manager_tg_id: int,
    barista_name: str,
    barista_phone: str,
    cafe_name: str
) -> Dict[str, Any]:
    """Отправка уведомления."""
    import asyncio

    from telegram import Bot

    async def async_send() -> Dict[str, Any]:
        bot = Bot(token=settings.bot_token)
        try:
            message = await bot.send_message(
                chat_id=manager_tg_id,
                text=f"⚠️ Новый бариста зарегестрирован:\n"
                     f"👤 Имя: {barista_name}\n"
                     f"📞 Телефон: {barista_phone}\n"
                     f"🏠 Кафе: {cafe_name}"
            )
            return {"status": "success", "message_id": message.message_id}
        except Exception as e:
            logger.error(f"Notification error: {e}")
            return {"status": "error", "error": str(e)}

    return asyncio.run(async_send())
