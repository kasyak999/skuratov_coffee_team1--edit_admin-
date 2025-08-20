import logging
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
from app.models.reservation import Status as ReservationStatus
from app.models.shift import Shift
from app.schemas.reservation_schema import ReservationUpdate
from app.tasks.activity_manager import activity_manager
from app.telegram_bot.commands import show_start_menu

# Состояния для изменения бронирования
SELECT_DATE, SELECT_SHIFT, CHANGE_BOOKING, SELECT_BARISTA = range(4)

logger = logging.getLogger(__name__)


class ChangeBookingHandler:
    """Обработчик изменения бронирования слотов бариста."""

    def __init__(self) -> None:
        """Инициализация обработчика."""
        self.reservation_crud = reservation_crud
        self.shift_crud = shift_crud
        self.user_crud = crud_user

    async def change_booking_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Начинает процесс изменения бронирования."""
        query = update.callback_query
        if query:
            await query.answer()
            message = query.message
        else:
            message = update.message

        # Получаем cafe_id менеджера
        user_id = update.effective_user.id
        async with async_session_maker() as session:
            user = await self.user_crud.get_by_telegram_id(user_id, session)
            if not user or not user.cafe_id:
                await message.reply_text(
                    'Ошибка: вы не привязаны к кафе или не авторизованы.'
                )
                return ConversationHandler.END

            context.user_data['cafe_id'] = user.cafe_id

        # Предлагаем выбрать дату
        today = date.today()
        buttons = [
            [
                InlineKeyboardButton(
                    'Сегодня', callback_data=f'select_date_{today}'
                ),
                InlineKeyboardButton(
                    'Завтра',
                    callback_data=(
                        f'select_date_{today.replace(day=today.day + 1)}'
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    '❌ Отменить', callback_data='cancel_change_booking'
                )
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        if query:
            await query.edit_message_text(
                'Выберите дату для изменения бронирования:',
                reply_markup=keyboard,
            )
        else:
            await message.reply_text(
                'Выберите дату для изменения бронирования:',
                reply_markup=keyboard,
            )

        return SELECT_DATE

    async def select_date(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор даты."""
        query = update.callback_query
        await query.answer()

        selected_date = query.data.replace('select_date_', '')
        context.user_data['selected_date'] = selected_date

        return await self.show_shifts_for_date(update, context)

    async def show_shifts_for_date(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Показывает слоты на выбранную дату."""
        query = update.callback_query
        cafe_id = context.user_data['cafe_id']
        selected_date = context.user_data['selected_date']

        async with async_session_maker() as session:
            start_datetime = datetime.strptime(selected_date, '%Y-%m-%d')
            end_datetime = datetime.combine(
                start_datetime.date(), datetime.max.time()
            )

            shifts = await shift_crud.get_multi(
                session=session,
                cafe_id=cafe_id,
                start_time=start_datetime,
                end_time=end_datetime,
            )
            if not shifts:
                await query.edit_message_text(
                    'На выбранную дату нет доступных слотов.',
                    reply_markup=None,
                )
                return await show_start_menu(update, context)

            buttons = []
            for shift in shifts:
                status = await self._get_shift_status(shift, session)
                btn_text = (
                    f'{shift.start_time.strftime("%H:%M")}-'
                    f'{shift.end_time.strftime("%H:%M")}'
                    f' {status}'
                )

                buttons.append([
                    InlineKeyboardButton(
                        btn_text, callback_data=f'select_shift_{shift.id}'
                    )
                ])

            buttons.append([
                InlineKeyboardButton(
                    '❌ Отменить', callback_data='cancel_change_booking'
                )
            ])

            keyboard = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(
                f'Слоты на {selected_date}:\nВыберите слот для изменения:',
                reply_markup=keyboard,
            )

        return SELECT_SHIFT

    async def select_shift(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор слота."""
        query = update.callback_query
        await query.answer()

        shift_id = int(query.data.replace('select_shift_', ''))
        context.user_data['shift_id'] = shift_id

        async with async_session_maker() as session:
            shift = await self.shift_crud.get(shift_id, session)
            reservations = await self.reservation_crud.get_by_shift(
                shift_id, session
            )
            buttons = []
            if not reservations:
                buttons.append(
                    [
                        InlineKeyboardButton(
                            '➕ Назначить первого бариста',
                            callback_data='assign_barista',
                        )
                    ],
                )
                message = (
                    f'Смена {shift.start_time.strftime("%H:%M")}-'
                    f'{shift.end_time.strftime("%H:%M")} полностью свободна.\n'
                    f'Вы можете назначить баристу:'
                )
            else:
                for reservation in reservations:
                    barista = await self.user_crud.get(
                        reservation.barista_id, session
                    )
                    buttons.append(
                        [
                            InlineKeyboardButton(
                                f'❌ бронь {barista.name}',
                                callback_data=f'remove_booking_{reservation.id}',
                            ),
                            InlineKeyboardButton(
                                '🔄 Заменить',
                                callback_data=f'change_barista_{reservation.id}',
                            ),
                        ],
                    )

                    message = (
                        f'Смена {shift.start_time.strftime("%H:%M")}-'
                        f'{shift.end_time.strftime("%H:%M")}\n'
                        f'Текущие бронирования:'
                    )

                if len(reservations) < shift.barista_count:
                    buttons.append(
                        [
                            InlineKeyboardButton(
                                '➕ Назначить дополнительного бариста',
                                callback_data='assign_barista',
                            )
                        ],
                    )
            buttons.append([
                InlineKeyboardButton(
                    '↩️ Вернуться к списку смен', callback_data='back_to_shifts'
                )
            ])
            keyboard = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, reply_markup=keyboard)

        return CHANGE_BOOKING

    async def handle_booking_change(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает изменение бронирования."""
        query = update.callback_query
        await query.answer()

        action = query.data
        shift_id = context.user_data['shift_id']

        if action == 'back_to_shifts':
            return await self.show_shifts_for_date(update, context)

        async with async_session_maker() as session:
            shift = await self.shift_crud.get(shift_id, session)

        if action.startswith('remove_booking_'):
            reservation_id = int(query.data.replace('remove_booking_', ''))
            context.user_data['reservation_id'] = reservation_id
            reservation = await self.reservation_crud.get(
                reservation_id, session
            )

            # Удаляем бронирование
            if reservation:
                barista = await self.user_crud.get(
                    reservation.barista_id, session
                )
                await self.reservation_crud.remove(reservation, session)
                await session.commit()

                # Отправляем уведомление бариста
                try:
                    activity_manager.delay(
                        chat_id=barista.telegram_id,
                        text=(
                            f'Ваша бронь на слот '
                            f'{shift.start_time.strftime("%H:%M")}-'
                            f'{shift.end_time.strftime("%H:%M")} '
                            # f'{shift.date} была отменена.'
                            f' была отменена.'
                        ),
                    )
                except Exception as e:
                    logger.error(f'Не удалось отправить уведомление: {e}')

                await query.edit_message_text(
                    'Бронирование успешно отменено.',
                    reply_markup=None,
                )
            else:
                await query.edit_message_text(
                    'Ошибка: бронирование не найдено.',
                    reply_markup=None,
                )

            # return ConversationHandler.END
            return await show_start_menu(update, context)

        if action.startswith('assign_barista'):
            # Показываем список доступных бариста
            baristas = await self.user_crud.get_multi_by_role(
                'barista', session
            )
            context.user_data['reservation_id'] = None
            async with async_session_maker() as session:
                shift = await self.shift_crud.get(shift_id, session)
            buttons = []
            for barista in baristas:
                buttons.append([
                    InlineKeyboardButton(
                        barista.name,
                        callback_data=f'select_barista_{barista.id}',
                    )
                ])

            buttons.append([
                InlineKeyboardButton('↩️ Назад', callback_data='back_to_shift')
            ])

            keyboard = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(
                'Выберите бариста для этого слота:',
                reply_markup=keyboard,
            )

            return SELECT_BARISTA

        if action.startswith('change_barista_'):
            # Показываем список доступных бариста
            baristas = await self.user_crud.get_multi_by_role(
                'barista', session
            )
            reservation_id = int(query.data.replace('change_barista_', ''))
            context.user_data['reservation_id'] = reservation_id
            reservation = await self.reservation_crud.get(
                reservation_id, session
            )
            buttons = []
            for barista in baristas:
                buttons.append([
                    InlineKeyboardButton(
                        barista.name,
                        callback_data=f'select_barista_{barista.id}',
                    )
                ])

            buttons.append([
                InlineKeyboardButton('↩️ Назад', callback_data='back_to_shift')
            ])

            keyboard = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(
                'Выберите бариста для этого слота:',
                reply_markup=keyboard,
            )

            return SELECT_BARISTA

        return await show_start_menu(update, context)

    async def select_barista(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор бариста для слота."""
        query = update.callback_query
        await query.answer()

        barista_id = int(query.data.replace('select_barista_', ''))
        shift_id = context.user_data['shift_id']
        reservation_id = context.user_data['reservation_id']
        old_reservation = None

        async with async_session_maker() as session:
            shift = await self.shift_crud.get(shift_id, session)
            barista = await self.user_crud.get(barista_id, session)

            if reservation_id:
                old_reservation = await self.reservation_crud.get(
                    reservation_id, session
                )
            # Создаем или обновляем бронирование
            if old_reservation:
                # Уведомляем старого бариста
                old_barista = await self.user_crud.get(
                    old_reservation.barista_id, session
                )
                try:
                    activity_manager.delay(
                        chat_id=old_barista.telegram_id,
                        text=(
                            f'Ваша бронь на слот '
                            f'{shift.start_time.strftime("%H:%M")}-'
                            f'{shift.end_time.strftime("%H:%M")} '
                            # f'{shift.date} была отменена.'
                            f' была отменена.'
                        ),
                    )
                except Exception as e:
                    logger.error(f'Не удалось отправить уведомление: {e}')

                # Обновляем бронирование
                reservation_update = ReservationUpdate(
                    barista_id=barista_id, status='onconfirm'
                )
                await self.reservation_crud.update(
                    old_reservation, reservation_update, session
                )
            else:
                # Создаем новое бронирование
                await self.reservation_crud.create_with_status(
                    barista_id, shift_id, 'onconfirm', session
                )
            await session.commit()
            # Уведомляем нового бариста
            try:
                activity_manager.delay(
                    chat_id=barista.telegram_id,
                    text=(
                        f'Вам назначен слот '
                        f'{shift.start_time.strftime("%H:%M")}-'
                        # f'{shift.end_time.strftime("%H:%M")} {shift.date}. '
                        f'{shift.end_time.strftime("%H:%M")}. '
                        f'Пожалуйста, подтвердите или отклоните бронь.'
                    ),
                )
            except Exception as e:
                logger.error(f'Не удалось отправить уведомление: {e}')

            await query.edit_message_text(
                f'Бариста {barista.name} успешно назначен на слот.',
                reply_markup=None,
            )

        return await show_start_menu(update, context)

    async def _get_shift_status(
        self, shift: Shift, session: AsyncSession
    ) -> str:
        """Определяет статус смены на основе резерваций."""
        await session.refresh(shift, ['reservations'])

        if not shift.reservations:
            return '🟢 Свободна'

        status_labels = {
            'RESERVED': 'забронировано',
            'ONCONFIRM': 'на подтверждении',
            'ATTENDED': 'присутствовал',
            'CANCELLED': 'отменено',
        }

        status_counts = {}
        for r in shift.reservations:
            status_name = r.status.name
            status_counts[status_name] = status_counts.get(status_name, 0) + 1

        status_stats = '\n' + '\n'.join(
            f'{status_labels[status]}: {count}'
            for status, count in sorted(status_counts.items())
        )

        active_reservations = [
            r
            for r in shift.reservations
            if r.status
            in [
                ReservationStatus.RESERVED,
                ReservationStatus.ONCONFIRM,
                ReservationStatus.ATTENDED,
            ]
        ]
        active_count = len(active_reservations)

        if active_count >= shift.barista_count:
            return f'🔴 Заполнена{status_stats}'
        if active_count > 0:
            return (
                f'🟡 Частично занята {active_count}/{shift.barista_count}'
                # f'{status_stats}'
            )
        return f'🟢 Свободна{status_stats}'

    async def cancel_change_booking(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отменяет процесс изменения бронирования."""
        query = update.callback_query
        await query.answer()

        await query.edit_message_text(
            'Изменение бронирования отменено.',
            reply_markup=None,
        )

        return await show_start_menu(update, context)

    def get_conversation_handler(self) -> ConversationHandler:
        """Возвращает обработчик диалога изменения бронирования."""
        return ConversationHandler(
            entry_points=[
                CommandHandler('change_booking', self.change_booking_start),
                CallbackQueryHandler(
                    self.change_booking_start, pattern='^change_booking$'
                ),
            ],
            states={
                SELECT_DATE: [
                    CallbackQueryHandler(
                        self.select_date, pattern='^select_date_'
                    ),
                    CallbackQueryHandler(
                        self.cancel_change_booking,
                        pattern='^cancel_change_booking$',
                    ),
                ],
                SELECT_SHIFT: [
                    CallbackQueryHandler(
                        self.select_shift, pattern='^select_shift_'
                    ),
                    CallbackQueryHandler(
                        self.cancel_change_booking,
                        pattern='^cancel_change_booking$',
                    ),
                ],
                CHANGE_BOOKING: [
                    CallbackQueryHandler(
                        self.handle_booking_change,
                        pattern='^(remove_booking_|change_barista_|assign_barista|back_to_shifts)',
                    ),
                ],
                SELECT_BARISTA: [
                    CallbackQueryHandler(
                        self.select_barista, pattern='^select_barista_'
                    ),
                    CallbackQueryHandler(
                        self.select_shift, pattern='^back_to_shift$'
                    ),
                ],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_change_booking)],
        )

    def setup_handlers(self, application: Application) -> None:
        """Регистрирует обработчики команд."""
        application.add_handler(self.get_conversation_handler())
