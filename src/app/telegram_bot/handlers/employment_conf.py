"""Модуль подтверждение выхода на работу с интерактивным интерфейсом."""

import logging
from typing import Optional, Union

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

from app.core.db import async_session_maker
from app.crud.reservation_crud import reservation_crud
from app.crud.shift_crud import shift_crud
from app.crud.user_crud import crud_user
from app.schemas.reservation_schema import ReservationUpdate
from app.telegram_bot.commands import show_start_menu

logger = logging.getLogger(__name__)

# Состояния для подтверждения броней
LIST_CONFIRMATIONS, CONFIRM_ACTION = range(2)


class EmpoymentConfirmHandler:
    """Обработчик подтверждения выхода на работу бариста."""

    def __init__(self) -> None:
        """Инициализация обработчика."""
        self.reservation_crud = reservation_crud

    async def get_user_cafe_id(self, user_id: int) -> int:
        """Получает cafe_id пользователя."""
        async with async_session_maker() as session:
            user = await crud_user.get_by_telegram_id(user_id, session)
            return user.cafe_id if user and user.cafe_id else None

    async def send_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str,
        reply_markup: Optional[
            Union[InlineKeyboardMarkup, ReplyKeyboardMarkup]
        ] = None,
    ) -> None:
        """Универсальный метод для отправки сообщений.

        Args:
            update: Объект Update из python-telegram-bot
            context: Контекст обработчика
            text: Текст сообщения
            reply_markup: Опциональная клавиатура для сообщения
            (InlineKeyboardMarkup или ReplyMarkup)

        Returns:
            None

        """
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text, reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)

    async def confirmation_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Начинает процесс подтверждения."""
        query = update.callback_query
        if query:
            await query.answer()

        user_id = update.effective_user.id
        cafe_id = await self.get_user_cafe_id(user_id)

        if not cafe_id:
            await self.send_message(
                update, context, 'Ошибка: не удалось определить ваше кафе.'
            )
            return await show_start_menu(update, context)

        context.user_data['cafe_id'] = cafe_id
        return await self.show_employment_list(update, context)

    async def show_employment_list(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Показывает список броней для подтверждения."""
        cafe_id = context.user_data['cafe_id']

        async with async_session_maker() as session:
            # Получаем брони с статусом onconfirm для данного кафе
            reservations = await reservation_crud.get_by_cafe_and_status(
                cafe_id=cafe_id, status='onconfirm', session=session
            )

        if not reservations:
            await self.send_message(
                update,
                context,
                'Для вашего кафе нет броней, ожидающих подтверждения.',
            )
            return await show_start_menu(update, context)

        buttons = []
        for reservation in reservations:
            # Получаем информацию о смене и бариста
            async with async_session_maker() as session:
                shift = await shift_crud.get(reservation.shift_id, session)
                barista = await crud_user.get(reservation.barista_id, session)

            button_text = (
                f'{barista.name if barista else "Неизвестный"} | '
                f'Cмена {
                    shift.start_time.strftime("%d.%m %H:%M")
                    if shift
                    else "??.?? ??:??"
                } | '
                f'Выход {
                    shift.updated_at.strftime("%d.%m %H:%M")
                    if shift
                    else "??.?? ??:??"
                }'
                # f"Статус: {reservation.status}"
            )
            buttons.append([
                InlineKeyboardButton(
                    button_text, callback_data=f'confirmation_{reservation.id}'
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                '❌ Отменить', callback_data='cancel_confirmation'
            )
        ])

        keyboard = InlineKeyboardMarkup(buttons)
        await self.send_message(
            update,
            context,
            (
                'Выберите запрос для подтверждения: '
                'имя|время смены|время выхода'
            ),
            reply_markup=keyboard,
        )

        return LIST_CONFIRMATIONS

    async def select_confirmation_to_approve(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор брони для подтверждения."""
        query = update.callback_query
        await query.answer()

        reservation_id = int(query.data.replace('confirmation_', ''))
        context.user_data['reservation_id'] = reservation_id

        # Создаем кнопки для подтверждения или отказа
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    '✅ Подтвердить', callback_data='confirm_attended'
                ),
                InlineKeyboardButton(
                    '❌ Отказать', callback_data='confirm_canceled'
                ),
            ],
            [InlineKeyboardButton('↩️ Назад', callback_data='back_to_list')],
        ])

        await query.edit_message_text(
            'Выберите действие для данного запроса:', reply_markup=keyboard
        )

        return CONFIRM_ACTION

    async def process_confirmation_action(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает действие подтверждения или отказа."""
        query = update.callback_query
        await query.answer()

        action = query.data
        reservation_id = context.user_data['reservation_id']

        if action == 'back_to_list':
            return await self.show_employment_list(update, context)

        # Определяем новый статус в зависимости от действия
        new_status = 'attended' if action == 'confirm_attended' else 'canceled'

        try:
            async with async_session_maker() as session:
                # Получаем текущую бронь
                reservation = await reservation_crud.get(
                    reservation_id, session
                )
                if not reservation:
                    await query.edit_message_text('Ошибка: бронь не найдена!')
                    return await show_start_menu(update, context)

                # Обновляем статус брони
                reservation_update = ReservationUpdate(status=new_status)
                await reservation_crud.update(
                    db_obj=reservation,
                    obj_in=reservation_update,
                    session=session,
                )
                await session.commit()

                # Получаем информацию для сообщения
                shift = await shift_crud.get(reservation.shift_id, session)
                barista = await crud_user.get(reservation.barista_id, session)

                status_text = (
                    'подтвержден' if new_status == 'attended' else 'отклонен'
                )
                message = (
                    f'Бронь для {barista.name if barista else "Неизвестного"} '
                    f'на смену {
                        shift.start_time.strftime("%d.%m %H:%M")
                        if shift
                        else "??.?? ??:??"
                    } '
                    f'{status_text}!'
                )

                await query.edit_message_text(message, reply_markup=None)

                # Возвращаемся к списку броней
                return await self.show_employment_list(update, context)

        except Exception as e:
            logger.error(f'Error updating reservation: {e}')
            await query.edit_message_text(
                f'Ошибка при обновлении брони: {str(e)}',
                reply_markup=None,
            )
            return await show_start_menu(update, context)

    async def cancel_confirmation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отменяет процесс подтверждения запросов."""
        query = update.callback_query
        if query:
            await query.answer()
            await query.edit_message_text(
                'Подтверждение запросов отменено', reply_markup=None
            )
        else:
            # Если это команда /cancel из сообщения
            await update.message.reply_text('Подтверждение запросов отменено')

        # Очищаем временные данные
        context.user_data.clear()
        return await show_start_menu(update, context)

    def get_conversation_handler(self) -> ConversationHandler:
        """Возвращает обработчик диалога подтверждения броней."""
        return ConversationHandler(
            entry_points=[
                CommandHandler('employment_conf', self.confirmation_start),
                CallbackQueryHandler(
                    self.confirmation_start, pattern='^employment_conf$'
                ),
            ],
            states={
                LIST_CONFIRMATIONS: [
                    CallbackQueryHandler(
                        self.select_confirmation_to_approve,
                        pattern='^confirmation_',
                    ),
                    CallbackQueryHandler(
                        self.cancel_confirmation,
                        pattern='^cancel_confirmation$',
                    ),
                ],
                CONFIRM_ACTION: [
                    CallbackQueryHandler(
                        self.process_confirmation_action,
                        pattern=(
                            '^(confirm_attended|'
                            'confirm_canceled|back_to_list)$'
                        ),
                    ),
                ],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_confirmation)],
            per_message=False,
        )

    def setup_handlers(self, application: Application) -> None:
        """Регистрирует обработчики команд."""
        application.add_handler(self.get_conversation_handler())
