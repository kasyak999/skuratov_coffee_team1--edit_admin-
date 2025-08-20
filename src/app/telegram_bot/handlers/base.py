# app/telegram_bot/handlers/base.py

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InlineKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes, ConversationHandler

from app.core.db import get_async_session

logger = logging.getLogger(__name__)


class BaseHandler:
    """Базовый класс для всех обработчиков."""

    async def cancel(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отмена текущего действия."""
        await update.message.reply_text(
            'Действие отменено.', reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    async def _get_db_session(
        self, context: ContextTypes.DEFAULT_TYPE
    ) -> AsyncSession:
        """Создает и возвращает новую асинхронную сессию."""
        return await get_async_session()

    async def send_text_safely(
            self,
            update: Update,
            text: str,
            *,
            reply_markup: InlineKeyboardMarkup | None = None,
            parse_mode: Optional[str] = None
    ) -> None:
        """Метод универсальной отправки сообщения."""
        if update.message:
            await update.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        elif update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
