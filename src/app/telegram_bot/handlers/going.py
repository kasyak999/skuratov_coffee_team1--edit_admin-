import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

from app.core.db import async_session_maker
from app.crud.reservation_crud import reservation_crud
from app.crud.user_crud import crud_user
from app.models.reservation import Status
from app.telegram_bot.commands import cancel, show_start_menu

logger = logging.getLogger(__name__)

# Константы состояний
CHECK_ROLE, SELECT_SHIFT, CONFIRMATION = range(3)


class GoingHandler:
    """Обработчик подтверждения выхода на ближайшую смену."""

    def __init__(self) -> None:
        """Инициализация обработчика."""
        self.reservation_crud = reservation_crud
        self.crud_user = crud_user

    async def going_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Начало процесса подтверждения смены."""
        query = update.callback_query
        if query:
            await query.answer()

        # Переходим к проверке роли пользователя
        return await self.check_role(update, context)

    async def check_role(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Проверяет роль пользователя."""
        # Получаем Telegram ID пользователя независимо от типа обновления
        if update.message:
            telegram_id = update.message.from_user.id
        elif update.callback_query:
            telegram_id = update.callback_query.from_user.id
        else:
            raise ValueError("Can't determine user's Telegram ID")

        async with async_session_maker() as session:
            user = await self.crud_user.get_by_telegram_id(
                telegram_id,
                session
            )
            if not user or user.role != 'barista':
                await update.effective_message.reply_text(
                    "Только баристы могут подтвердить смену!"
                )
                return await show_start_menu(update, context)

        # Продолжаем дальше, возвращаемся к следующему состоянию
        return await self.select_shift(update, context)

    async def select_shift(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отображение вариантов подтверждения ближайшей смены."""
        # Определим Telegram ID пользователя
        if update.message:
            telegram_id = update.message.from_user.id
        elif update.callback_query:
            telegram_id = update.callback_query.from_user.id
        else:
            raise ValueError("Can't determine user's Telegram ID")

        async with async_session_maker() as session:
            user = await self.crud_user.get_by_telegram_id(
                telegram_id,
                session
            )
            if not user:
                await update.effective_message.reply_text(
                    'Пользователь не найден.')
                return await show_start_menu(update, context)

            # Получаем ближайшую смену
            # вместе с информацией о кафетерии и времени
            nearest_shift_data = await self.reservation_crud. \
                get_nearest_shift(
                    user.id,
                    session,
                )

            if not nearest_shift_data:
                await update.effective_message.reply_text(
                    'Нет доступных смен для подтверждения.')
                return await show_start_menu(update, context)

            # Разделяем полученные данные
            reservation, shift, cafe = nearest_shift_data

            # Готовим информативное сообщение
            message = (
                f"<b>Подтвердите вашу ближайшую смену:</b>\n\n"
                f"Кафе: {cafe.name}\n"
                f"Дата и время начала: {
                    shift.start_time.strftime('%d-%m-%Y %H:%M')}\n"
            )

        # Интерфейс подтверждения
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton('Да, выйти на смену',
                                     callback_data='confirm_going'),
                InlineKeyboardButton(
                    'Нет, отказаться', callback_data='decline_going'),
            ],
        ])

        # Предлагаете пользователю подтвердить смену
        await update.effective_message.reply_html(
            message,
            reply_markup=keyboard
        )

        return CONFIRMATION

    async def handle_confirmation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает решение пользователя о выходе на смену."""
        query = update.callback_query
        await query.answer()

        decision = query.data
        telegram_id = update.effective_user.id

        async with async_session_maker() as session:
            user = await self.crud_user.get_by_telegram_id(
                telegram_id,
                session
            )
            if not user:
                await query.edit_message_text('Пользователь не найден.')
                return await show_start_menu(update, context)

            # Получаем ближайшую свободную смену пользователя
            next_shift_data = await self.reservation_crud. \
                get_nearest_shift(user.id, session)

            if not next_shift_data:
                await query.edit_message_text(
                    'Нет свободных смен для подтверждения.')
                return await show_start_menu(update, context)

            # Разделяем полученные данные
            reservation, _, _ = next_shift_data

            if decision == 'confirm_going':
                # Меняем статус резервирования на "подтвержден"
                reservation.status = Status.ATTENDED
                # Добавляем изменённый объект в сессию
                session.add(reservation)
                # Сохраняем изменения в базе данных
                await session.commit()
                await query.edit_message_text('Выход на смену подтвержден!')
            else:
                await query.edit_message_text(
                    'Вы отказались от подтверждения смены.')

        return await show_start_menu(update, context)

    def get_conversation_handler(
            self
    ) -> ConversationHandler:
        """Возвращает обработчик разговора."""
        return ConversationHandler(
            entry_points=[
                CommandHandler('going', self.going_start),
                CallbackQueryHandler(
                    self.going_start,
                    pattern='^going$')
            ],
            states={
                CHECK_ROLE: [
                    CallbackQueryHandler(self.check_role),
                ],
                SELECT_SHIFT: [
                    CallbackQueryHandler(self.select_shift),
                ],
                CONFIRMATION: [
                    CallbackQueryHandler(self.handle_confirmation),
                ],
            },
            fallbacks=[
                CommandHandler('cancel', cancel),
            ],
        )
