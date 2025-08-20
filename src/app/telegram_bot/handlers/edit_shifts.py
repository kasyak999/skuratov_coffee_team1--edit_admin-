"""Модуль редактирования смен с интерактивным интерфейсом."""

import logging
from datetime import datetime, time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.core.db import async_session_maker
from app.crud.shift_crud import shift_crud
from app.crud.user_crud import crud_user
from app.schemas.shift_schema import ShiftUpdate
from app.telegram_bot.commands import show_start_menu

logger = logging.getLogger(__name__)

# Состояния для редактирования смены
LIST_SHIFTS, EDIT_SHIFT_FIELD, CONFIRM_EDIT = range(3)


class EditShiftHandler:
    """Обработчик редактирования смен с интерактивным интерфейсом."""

    def __init__(self) -> None:
        """Инициализация обработчика."""
        self.shift_crud = shift_crud

    async def get_user_cafe_id(self, user_id: int) -> int:
        """Получает cafe_id пользователя."""
        async with async_session_maker() as session:
            user = await crud_user.get_by_telegram_id(user_id, session)
            return user.cafe_id if user and user.cafe_id else None

    async def edit_shift_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Начинает процесс редактирования смен."""
        query = update.callback_query
        if query:
            await query.answer()

        user_id = update.effective_user.id
        cafe_id = await self.get_user_cafe_id(user_id)

        if not cafe_id:
            await update.message.reply_text(
                'Ошибка: не удалось определить ваше кафе.'
            )
            return await show_start_menu(update, context)

        context.user_data['cafe_id'] = cafe_id
        return await self.show_shifts_list(update, context)

    async def show_shifts_list(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Показывает список смен для редактирования."""
        cafe_id = context.user_data['cafe_id']

        async with async_session_maker() as session:
            shifts = await shift_crud.get_multi(
                cafe_id=cafe_id, session=session
            )

        if not shifts:
            await update.message.reply_text(
                'Для вашего кафе нет доступных смен для редактирования.'
            )
            return await show_start_menu(update, context)

        # Сортируем смены по дате (новые сверху)
        shifts = sorted(shifts, key=lambda x: x.start_time, reverse=True)

        buttons = []
        for shift in shifts:
            btn_text = (
                f'{shift.start_time.strftime("%d.%m.%Y")} '
                f'{shift.start_time.strftime("%H:%M")}-'
                f'{shift.end_time.strftime("%H:%M")} '
                f'({shift.barista_count} бариста)'
            )
            buttons.append([
                InlineKeyboardButton(
                    btn_text, callback_data=f'edit_shift_{shift.id}'
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                '❌ Отменить', callback_data='cancel_edit_shifts'
            )
        ])

        keyboard = InlineKeyboardMarkup(buttons)
        message = 'Выберите смену для редактирования:'

        try:
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    message, reply_markup=keyboard
                )
            else:
                await update.message.reply_text(message, reply_markup=keyboard)
        except Exception as e:
            logger.error(f'Error showing shifts list: {e}')
            return await show_start_menu(update, context)

        return LIST_SHIFTS

    async def select_shift_to_edit(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор смены для редактирования."""
        query = update.callback_query

        if query:
            await query.answer()
            shift_id = int(query.data.replace('edit_shift_', ''))
        else:
            shift_id = context.user_data['shift_id']
            if not shift_id:
                await update.message.reply_text(
                    'Ошибка: не выбрана смена для редактирования.'
                )
                return await show_start_menu(update, context)

        context.user_data['shift_id'] = shift_id

        async with async_session_maker() as session:
            shift = await shift_crud.get(shift_id, session)
            if not shift:
                msg = 'Смена не найдена!'
                if query:
                    await query.edit_message_text(msg)
                else:
                    await update.message.reply_text(msg)
                return await show_start_menu(update, context)

            context.user_data['current_shift'] = {
                'start_time': shift.start_time.time(),
                'end_time': shift.end_time.time(),
                'barista_count': shift.barista_count,
            }

        buttons = [
            [
                InlineKeyboardButton(
                    f'🕒 Начало: {shift.start_time.strftime("%H:%M")}',
                    callback_data='edit_start_time',
                )
            ],
            [
                InlineKeyboardButton(
                    f'🕘 Конец: {shift.end_time.strftime("%H:%M")}',
                    callback_data='edit_end_time',
                )
            ],
            [
                InlineKeyboardButton(
                    f'👥 Бариста: {shift.barista_count}',
                    callback_data='edit_barista_count',
                )
            ],
            [
                InlineKeyboardButton(
                    '✅ Сохранить', callback_data='save_shift_changes'
                ),
                InlineKeyboardButton(
                    '❌ Отменить', callback_data='back_to_shifts_list'
                ),
            ],
        ]

        keyboard = InlineKeyboardMarkup(buttons)
        message = (
            f'Редактирование смены от '
            f'{shift.start_time.strftime("%d.%m.%Y")}\n'
            f'Выберите параметр для изменения:'
        )

        if query:
            await query.edit_message_text(message, reply_markup=keyboard)
        else:
            await update.message.reply_text(message, reply_markup=keyboard)

        return EDIT_SHIFT_FIELD

    async def edit_shift_field_prompt(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Запрашивает новое значение для выбранного поля."""
        query = update.callback_query
        await query.answer()

        field = query.data.replace('edit_', '')
        context.user_data['editing_field'] = field

        prompts = {
            'start_time': 'Введите новое время начала (ЧЧ:ММ):',
            'end_time': 'Введите новое время окончания (ЧЧ:ММ):',
            'barista_count': 'Введите новое количество бариста:',
        }

        await query.edit_message_text(prompts[field], reply_markup=None)

        return EDIT_SHIFT_FIELD

    async def process_shift_field_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает введенное значение поля."""
        field = context.user_data.get('editing_field')
        if not field:
            await update.message.reply_text(
                'Ошибка: не указано поле для редактирования.'
            )
            return await show_start_menu(update, context)

        value = update.message.text

        try:
            if field in ['start_time', 'end_time']:
                hours, minutes = map(int, value.split(':'))
                value = time(hours, minutes)
            elif field == 'barista_count':
                if not value.isdigit():
                    raise ValueError('Количество бариста должно быть числом')
                value = int(value)
        except Exception as e:
            logger.error(f'Error processing field input: {e}')
            await update.message.reply_text(f'Некорректный формат данных: {e}')
            return EDIT_SHIFT_FIELD

        context.user_data['current_shift'][field] = value
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
        )

        # Получаем данные смены из контекста
        shift_id = context.user_data['shift_id']
        async with async_session_maker() as session:
            shift = await shift_crud.get(shift_id, session)
            if not shift:
                await update.message.reply_text('Смена не найдена!')
                return await show_start_menu(update, context)

        # Формируем сообщение с кнопками
        start_time = context.user_data['current_shift']['start_time'].strftime(
            '%H:%M'
        )
        end_time = context.user_data['current_shift']['end_time'].strftime(
            '%H:%M'
        )
        barista_count = context.user_data['current_shift']['barista_count']
        buttons = [
            [
                InlineKeyboardButton(
                    f'🕒 Начало: {start_time}', callback_data='edit_start_time'
                )
            ],
            [
                InlineKeyboardButton(
                    f'🕘 Конец: {end_time}', callback_data='edit_end_time'
                )
            ],
            [
                InlineKeyboardButton(
                    f'👥 Бариста: {barista_count}',
                    callback_data='edit_barista_count',
                )
            ],
            [
                InlineKeyboardButton(
                    '✅ Сохранить', callback_data='save_shift_changes'
                ),
                InlineKeyboardButton(
                    '❌ Отменить', callback_data='back_to_shifts_list'
                ),
            ],
        ]

        keyboard = InlineKeyboardMarkup(buttons)
        message = (
            f'Редактирование смены от '
            f'{shift.start_time.strftime("%d.%m.%Y")}\n'
            f'Выберите параметр для изменения:'
        )

        await update.message.reply_text(message, reply_markup=keyboard)

        return EDIT_SHIFT_FIELD

    async def save_shift_changes(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Сохраняет изменения в смене."""
        query = update.callback_query
        if query:
            await query.answer()
        else:
            await update.message.reply_text('Ошибка: неверный вызов команды.')
            return await show_start_menu(update, context)

        shift_id = context.user_data['shift_id']
        if not shift_id:
            await query.edit_message_text(
                'Ошибка: не выбрана смена для редактирования.'
            )
            return await show_start_menu(update, context)

        shift_data = context.user_data['current_shift']
        if not shift_data:
            await query.edit_message_text('Ошибка: нет данных для обновления.')
            return await show_start_menu(update, context)

        try:
            async with async_session_maker() as session:
                # Получаем текущую смену для извлечения даты
                current_shift = await shift_crud.get(shift_id, session)
                if not current_shift:
                    await query.edit_message_text('Ошибка: смена не найдена!')
                    return await show_start_menu(update, context)

                # Формируем datetime объекты для смены
                start_dt = datetime.combine(
                    current_shift.start_time.date(), shift_data['start_time']
                )
                end_dt = datetime.combine(
                    current_shift.end_time.date(), shift_data['end_time']
                )

                # Проверка пересечений с существующими сменами
                existing_shifts = await shift_crud.get_multi(
                    cafe_id=current_shift.cafe_id, session=session
                )

                for shift in existing_shifts:
                    if shift.id == shift_id:  # Пропускаем текущую смену
                        continue
                    # Приводим все даты к одинаковому формату
                    # (без временной зоны)
                    existing_start = shift.start_time.replace(tzinfo=None)
                    existing_end = shift.end_time.replace(tzinfo=None)
                    if start_dt < existing_end and end_dt > existing_start:
                        keyboard = InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton(
                                    '← Вернуться к списку смен',
                                    callback_data='back_to_shifts_list',
                                )
                            ]
                        ])
                        await query.edit_message_text(
                            f'❌ Ошибка: пересечение с существующей сменой!\n'
                            f'Невозможно сохранить изменения.\n\n'
                            f'Конфликтующая смена:\n'
                            f'{shift.start_time.strftime("%d.%m.%Y %H:%M")}-'
                            f'{shift.end_time.strftime("%H:%M")}',
                            reply_markup=keyboard,
                        )
                        return EDIT_SHIFT_FIELD

                shift_update = ShiftUpdate(
                    start_time=start_dt,
                    end_time=end_dt,
                    barista_count=shift_data['barista_count'],
                )

                # Обновляем смену
                await shift_crud.update(
                    db_obj=current_shift, obj_in=shift_update, session=session
                )

                await session.commit()

                # Показываем обновленный список смен
                shifts = await shift_crud.get_multi(
                    cafe_id=current_shift.cafe_id, session=session
                )

                # Формируем сообщение
                shifts_list = '\n'.join(
                    f'• {s.start_time.strftime("%d.%m.%Y %H:%M")}-'
                    f'{s.end_time.strftime("%H:%M")} '
                    f'({s.barista_count} бариста)'
                    for s in sorted(shifts, key=lambda x: x.start_time)
                )
                message = (
                    f'✅ Изменения сохранены!\n\n'
                    f'📅 Актуальные смены:\n{shifts_list}\n\n'
                    f'Продолжить редактирование?'
                )
                # Кнопки для продолжения
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            'Да', callback_data='continue_editing'
                        ),
                        InlineKeyboardButton(
                            'Нет', callback_data='finish_editing'
                        ),
                    ]
                ])

                await query.edit_message_text(message, reply_markup=keyboard)

                # Сохраняем cafe_id для повторного использования
                context.user_data['current_cafe_id'] = current_shift.cafe_id

                return CONFIRM_EDIT

        except Exception as e:
            logger.error(f'Error saving shift changes: {e}')
            await query.edit_message_text(
                f'Ошибка при сохранении изменений: {str(e)}.',
                reply_markup=None,
            )
            return await show_start_menu(update, context)

    async def handle_continue_editing(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор продолжения редактирования."""
        query = update.callback_query
        await query.answer()

        choice = query.data

        if choice == 'continue_editing':
            # Возвращаемся к списку смен
            cafe_id = context.user_data.get('current_cafe_id')
            if cafe_id:
                # Очищаем данные текущей смены, но сохраняем cafe_id
                context.user_data.pop('shift_id', None)
                context.user_data.pop('current_shift', None)
                context.user_data.pop('editing_field', None)

                return await self.show_shifts_list(update, context)

        # Если выбрано "Нет" или cafe_id не найден
        await query.edit_message_text(
            'Редактирование завершено.', reply_markup=None
        )

        # Полная очистка контекста
        context.user_data.clear()

        return await show_start_menu(update, context)

    async def back_to_shifts_list(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Возвращает к списку смен без сохранения изменений."""
        query = update.callback_query
        await query.answer()

        # Очищаем временные данные
        context.user_data.pop('shift_id', None)
        context.user_data.pop('current_shift', None)

        return await self.show_shifts_list(update, context)

    async def cancel_edit_shifts(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отменяет процесс редактирования смен."""
        query = update.callback_query
        await query.answer()

        # Очищаем все временные данные
        context.user_data.clear()

        await query.edit_message_text(
            'Редактирование смен отменено', reply_markup=None
        )

        return await show_start_menu(update, context)

    def get_conversation_handler(self) -> ConversationHandler:
        """Возвращает обработчик диалога редактирования смен."""
        return ConversationHandler(
            entry_points=[
                CommandHandler('edit_shifts', self.edit_shift_start),
                CallbackQueryHandler(
                    self.edit_shift_start, pattern='^edit_shifts$'
                ),
            ],
            states={
                LIST_SHIFTS: [
                    CallbackQueryHandler(
                        self.select_shift_to_edit, pattern='^edit_shift_'
                    ),
                    CallbackQueryHandler(
                        self.cancel_edit_shifts, pattern='^cancel_edit_shifts$'
                    ),
                ],
                EDIT_SHIFT_FIELD: [
                    CallbackQueryHandler(
                        self.edit_shift_field_prompt,
                        pattern='^edit_(start_time|end_time|barista_count)$',
                    ),
                    CallbackQueryHandler(
                        self.save_shift_changes, pattern='^save_shift_changes$'
                    ),
                    CallbackQueryHandler(
                        self.back_to_shifts_list,
                        pattern='^back_to_shifts_list$',
                    ),
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.process_shift_field_input,
                    ),
                ],
                CONFIRM_EDIT: [
                    CallbackQueryHandler(
                        self.handle_continue_editing,
                        pattern='^(continue_editing|finish_editing)$',
                    )
                ],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_edit_shifts)],
            per_message=False,
        )

    def setup_handlers(self, application: Application) -> None:
        """Регистрирует обработчики команд."""
        application.add_handler(self.get_conversation_handler())
