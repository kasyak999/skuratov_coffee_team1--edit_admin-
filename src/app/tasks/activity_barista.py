import logging
from typing import Any, Dict

from celery import shared_task

from app.core.config import settings

logger = logging.getLogger(__name__)


status_text={
    'yes': 'Подтвердил вашу регистрацию',
    'no': 'Отклонил вашу регистрацию'
}


@shared_task(name='activity_barista')
def activity_barista(status: str, barista_tg_id: int) -> Dict[str, Any]:
    """Отправка уведомления."""
    import asyncio

    from telegram import Bot

    async def async_send() -> Dict[str, Any]:
        bot = Bot(token=settings.bot_token)
        try:
            message = await bot.send_message(
                chat_id=barista_tg_id,
                text=f'Управляющий '
                f'{status_text[status]}')
            return {"status": "success", "message_id": message.message_id}
        except Exception as e:
            logger.error(f"Notification error: {e}")
            return {"status": "error", "error": str(e)}
    return asyncio.run(async_send())
