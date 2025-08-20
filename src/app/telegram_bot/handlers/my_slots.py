"""Модуль для команды /my_slots (просмотр своих смен баристой)."""

import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from app.core.db import async_session_maker
from app.crud.reservation_crud import reservation_crud
from app.crud.user_crud import crud_user
from app.models.reservation import Status as ReservationStatus
from app.models.user import Role
from app.telegram_bot.commands import show_start_menu

logger = logging.getLogger(__name__)


class MySlotsHandler:
    """Обработчик команды /my_slots."""

    def __init__(self) -> None:
        """Словарь для перевода статусов на русский."""
        self.status_translation = {
            ReservationStatus.RESERVED: "Забронировано",
            ReservationStatus.ONCONFIRM: "На подтверждении",
            ReservationStatus.ATTENDED: "Посещено",
            ReservationStatus.CANCELLED: "Отменено"
        }

    async def show_my_slots(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Показывает список смен баристы."""
        try:
            if update.callback_query:
                query = update.callback_query
                await query.answer()
                message = query.message
                telegram_id = query.from_user.id
            else:
                message = update.message
                telegram_id = update.effective_user.id

            async with async_session_maker() as session:
                # 1. Получаем пользователя
                user = await crud_user.get_by_telegram_id(telegram_id, session)
                if not user or user.role != Role.BARISTA:
                    await message.reply_text(
                        "❌ Команда доступна только баристам.")
                    return await show_start_menu(update, context)

                # 2. Получаем брони пользователя
                reservations = await reservation_crud.get_by_user(
                    user.id, session)
                if not reservations:
                    await message.reply_text("📭 У вас нет активных смен.")
                    return await show_start_menu(update, context)

                # 3. Формируем сообщение
                slots_info = []
                for reservation in reservations:
                    await session.refresh(reservation, ['shift'])
                    shift = reservation.shift
                    if not shift:
                        continue

                    await session.refresh(shift, ['cafe'])
                    cafe_name = shift.cafe.name if shift.cafe else "❌ Кафе не"
                    " указано"

                    status_emoji = {
                        ReservationStatus.RESERVED: "🟡",
                        ReservationStatus.ONCONFIRM: "🟠",
                        ReservationStatus.ATTENDED: "🟢",
                        ReservationStatus.CANCELLED: "🔴",
                    }.get(reservation.status, "⚪")

                    status_text = self.status_translation.get(
                        reservation.status,
                        reservation.status.value
                    )

                    slots_info.append(
                        f"{status_emoji} *"
                        f"{shift.start_time.strftime('%d.%m.%Y %H:%M')}–"
                        f"{shift.end_time.strftime('%H:%M')}*\n"
                        f"🏠 {cafe_name}\n"
                        f"📌 Статус: {status_text}\n"
                    )

                # 4. Добавляем клавиатуру
                keyboard = [
                    [InlineKeyboardButton("🔄 Обновить",
                                          callback_data="refresh_my_slots"),
                     InlineKeyboardButton("❌ Отменить",
                                          callback_data="cancel_to_menu")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                if update.callback_query:
                    await message.edit_text(
                        "📅 *Ваши смены:*\n\n" + "\n".join(slots_info),
                        reply_markup=reply_markup,
                        parse_mode="Markdown",
                    )
                else:
                    await message.reply_text(
                        "📅 *Ваши смены:*\n\n" + "\n".join(slots_info),
                        reply_markup=reply_markup,
                        parse_mode="Markdown",
                    )

        except Exception as e:
            logger.error(f"Ошибка в show_my_slots: {e}")
            await update.message.reply_text(
                "⚠️ Произошла ошибка при получении смен")

    async def refresh_my_slots(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Обновляет список смен."""
        try:
            await self.show_my_slots(update, context)
        except Exception as e:
            logger.error(f"Ошибка при обновлении смен: {e}")
            await update.callback_query.answer("⚠️ Ошибка обновления")

    async def cancel_to_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Возвращает в главное меню."""
        query = update.callback_query
        await query.answer()
        await show_start_menu(update, context)

    def setup_handlers(self, application: Application) -> None:
        """Регистрирует обработчики команд для просмотра смен."""
        handler = MySlotsHandler()

        # Обработчик команды /my_slots
        application.add_handler(CommandHandler(
            "my_slots", handler.show_my_slots))

        # Обработчик кнопки обновления
        application.add_handler(
            CallbackQueryHandler(handler.refresh_my_slots,
                                 pattern="^refresh_my_slots$")
        )

        # Обработчик для кнопки "Мои смены" из меню
        application.add_handler(
            CallbackQueryHandler(handler.show_my_slots, pattern="^my_slots$")
        )
        application.add_handler(
            CallbackQueryHandler(self.cancel_to_menu,
                                 pattern="^cancel_to_menu$")
        )
