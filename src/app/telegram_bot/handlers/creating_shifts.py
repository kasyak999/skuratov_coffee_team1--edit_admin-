"""Модуль создания кафе с интерактивным интерфейсом."""

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
from app.crud.cafe_crud import cafe_crud
from app.crud.shift_crud import shift_crud
from app.crud.user_crud import crud_user
from app.schemas.shift_schema import ShiftCreate
from app.telegram_bot.commands import cancel, show_start_menu

logger = logging.getLogger(__name__)

# Состояния для создания кафе
EDIT_SHIFT_FIELDS, CONFIRM_SHIFT_DATA = range(2)


class CreateShiftHandler:
    """Обработчик создания слота в интерактивным интерфейсом."""

    def __init__(self) -> None:
        """Инициализация обработчика."""
        self.shift_crud = shift_crud
        self.shift_data_template = {
            'date': None,
            'start_time': None,
            'end_time': None,
            'barista_count': None,
            'cafe_id': None,
        }

    async def initialize_shift_data(
        self, context: ContextTypes.DEFAULT_TYPE, user_id: int = None
    ) -> None:
        """Инициализирует данные нового слота."""
        if 'new_shift' not in context.user_data:
            # Получаем cafe_id из таблицы пользователей
            cafe_id = None
            start_time = None
            end_time = None
            if user_id:
                async with async_session_maker() as session:
                    user = await crud_user.get_by_telegram_id(user_id, session)
                    if user and user.cafe_id:
                        cafe_id = user.cafe_id
            if cafe_id:
                async with async_session_maker() as session:
                    cafe = await cafe_crud.get_or_404(cafe_id, session)
                    if cafe and cafe.open_time:
                        start_time = cafe.open_time
                    if cafe and cafe.close_time:
                        end_time = cafe.close_time
            # Создаем шаблон с предзаполненным cafe_id
            self.shift_data_template = {
                'date': datetime.now().date(),
                'start_time': start_time,
                'end_time': end_time,
                'barista_count': None,
                'cafe_id': cafe_id,  # Предзаполняем cafe_id
            }

            context.user_data['new_shift'] = self.shift_data_template.copy()

    async def edit_shift_fields(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отображает поля слота для редактирования."""
        query = update.callback_query
        if query:
            await query.answer()  #

        await self.initialize_shift_data(context)
        shift_data = context.user_data['new_shift']

        buttons = []
        fields = [
            ('date', 'Дата смены (ДД.MM.ГГГГ)'),
            ('start_time', 'Время начала смены (ЧЧ:ММ)'),
            ('end_time', 'Время окончания смены(ЧЧ:ММ)'),
            ('barista_count', 'Количество бариста в смену'),
            ('cafe_id', 'ID кафе'),
        ]

        for field, label in fields:
            field_value = shift_data[field] or 'Не указано'
            buttons.append([
                InlineKeyboardButton(
                    f'{label}: {field_value}',
                    callback_data=f'edit_shift_{field}',
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                '✅ Сохранить слот', callback_data='save_shift'
            ),
            InlineKeyboardButton(
                '❌ Отменить', callback_data='cancel_shift_creation'
            ),
        ])

        keyboard = InlineKeyboardMarkup(buttons)
        message = 'Заполните данные слота:\n'

        try:
            if query:
                try:
                    await query.edit_message_text(
                        message, reply_markup=keyboard
                    )
                except Exception as e:
                    logger.warning('Failed to edit message: %s', e)
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=message,
                        reply_markup=keyboard,
                    )
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=message,
                    reply_markup=keyboard,
                )
        except Exception as e:
            logger.error('Error in edit_shift_fields: %s', e)
            return await show_start_menu(update, context)

        return EDIT_SHIFT_FIELDS

    async def proceed_to_create_shift(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Переходит к созданию новой смены после показа списка."""
        query = update.callback_query
        await query.answer()

        # Удаляем сообщение со списком смен
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=query.message.message_id,
        )

        return await self.edit_shift_fields(update, context)

    async def create_shift_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Cозданиt слота с выводом списка существующих смен."""
        query = update.callback_query
        if query:
            await query.answer()

        # Получаем ID пользователя из update
        user_id = update.effective_user.id

        # Инициализируем данные с предзаполненным cafe_id
        await self.initialize_shift_data(context, user_id)
        shift_data = context.user_data['new_shift']
        cafe_id = shift_data['cafe_id']

        if cafe_id:
            # Получаем существующие смены для этого кафе
            async with async_session_maker() as session:
                shifts = await shift_crud.get_multi(
                    cafe_id=cafe_id, session=session
                )

                # Формируем список смен
                if shifts:
                    shifts_list = ''
                    for i, shift in enumerate(shifts, 1):
                        shifts_list += (
                            f'{i}. {shift.start_time.strftime("%d.%m.%Y")} '
                            f'{shift.start_time.strftime("%H:%M")}-'
                            f'{shift.end_time.strftime("%H:%M")}\n'
                            f'   👥 Бариста: {shift.barista_count}\n'
                        )
                    message = (
                        f'📅 Текущие смены кафе:\n'
                        f'{shifts_list}\n\nВыберите действие:'
                    )
                else:
                    message = (
                        'ℹ️ Для этого кафе еще нет созданных смен.\n\n'
                        'Выберите действие:'
                    )

                # Кнопки для продолжения
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            '➕ Создать новую смену',
                            callback_data='proceed_to_create_shift',
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            '❌ Отменить',
                            callback_data='cancel_shift_creation',
                        )
                    ],
                ])

                if query:
                    await query.edit_message_text(
                        message, reply_markup=keyboard
                    )
                else:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=message,
                        reply_markup=keyboard,
                    )

                return CONFIRM_SHIFT_DATA
        else:
            await update.message.reply_text(
                'Ошибка: не удалось определить кафе.'
                'Обратитесь к администратору.'
            )
            return await show_start_menu(update, context)

    async def edit_shift_field(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Запрашивает редактирование конкретного поля."""
        query = update.callback_query
        await query.answer()

        field = query.data.replace('edit_shift_', '')
        context.user_data['editing_field'] = field

        field_prompts = {
            'date': 'Дата смены (ДД.ММ.ГГГГ):',
            'start_time': 'Время начала смены (ЧЧ:ММ):',
            'end_time': 'Время окончания смены(ЧЧ:ММ):',
            'barista_count': 'Количество бариста в смену:',
            'cafe_id': 'ID кафе:',
        }

        await query.edit_message_text(field_prompts[field], reply_markup=None)
        return EDIT_SHIFT_FIELDS

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
            if field == 'date':
                value = datetime.strptime(value, '%d.%m.%Y').date()
                if value < datetime.now().date():
                    await update.message.reply_text(
                        'Дата должна быть текущей или позже.'
                    )
                    return EDIT_SHIFT_FIELDS
            elif field in ['start_time', 'end_time']:
                hours, minutes = map(int, value.split(':'))
                value = time(hours, minutes)
            elif field == 'barista_count':
                if not value.isdigit():
                    await update.message.reply_text(
                        'Количество бариста должно быть числом.'
                    )
                    return EDIT_SHIFT_FIELDS
                value = int(value)
            elif field == 'cafe_id':
                value = int(value)
        except Exception as e:
            logger.error('Error processing field %s: %s', field, e)
            await update.message.reply_text('Некорректный формат данных.')
            return EDIT_SHIFT_FIELDS

        await self.initialize_shift_data(context)
        context.user_data['new_shift'][field] = value

        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
        )

        return await self.edit_shift_fields(update, context)

    async def save_shift(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Сохраняет слот в БД."""
        query = update.callback_query
        await query.answer()

        await self.initialize_shift_data(context)
        shift_data = context.user_data['new_shift']

        required_fields = [
            'date',
            'start_time',
            'end_time',
            'barista_count',
            'cafe_id',
        ]
        missing_fields = [
            field for field in required_fields if not shift_data.get(field)
        ]

        if missing_fields:
            await query.edit_message_text(
                f'Ошибка: не заполнены поля: {", ".join(missing_fields)}!',
                reply_markup=None,
            )
            return await show_start_menu(update, context)

        try:
            # Формируем datetime объекты для новой смены
            start_dt = datetime.combine(
                shift_data['date'], shift_data['start_time']
            )
            end_dt = datetime.combine(
                shift_data['date'], shift_data['end_time']
            )

            # Проверка корректности времени (конец после начала)
            if end_dt <= start_dt:
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            '← Вернуться к редактированию',
                            callback_data='continue_creating_shifts',
                        )
                    ]
                ])
                await query.edit_message_text(
                    '❌ Ошибка:время окончания должно быть позже начала!',
                    reply_markup=keyboard,
                )
                return EDIT_SHIFT_FIELDS

            async with async_session_maker() as session:
                # Получаем данные кафе для проверки времени работы
                cafe = await cafe_crud.get_or_404(
                    shift_data['cafe_id'], session
                )
                if not cafe:
                    await query.edit_message_text(
                        '❌ Ошибка: кафе не найдено!', reply_markup=None
                    )
                    return ConversationHandler.END

                # Проверка времени работы кафе
                if (
                    shift_data['start_time'] < cafe.open_time
                    or shift_data['end_time'] > cafe.close_time
                ):
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(
                                '← Вернуться к созданию смены',
                                callback_data='continue_creating_shifts',
                            )
                        ]
                    ])
                    await query.edit_message_text(
                        f'❌ Ошибка: смена выходит за пределы работы кафе!\n'
                        f'Невозможно сохранить изменения.\n\n'
                        f'Кафе работает с {cafe.open_time.strftime("%H:%M")}'
                        f'до {cafe.close_time.strftime("%H:%M")}',
                        reply_markup=keyboard,
                    )
                    return EDIT_SHIFT_FIELDS

                # Проверка пересечений с существующими сменами
                existing_shifts = await shift_crud.get_multi(
                    cafe_id=shift_data['cafe_id'], session=session
                )

                for shift in existing_shifts:
                    # Приводим все даты к одинаковому формату
                    # (без временной зоны)
                    existing_start = shift.start_time.replace(tzinfo=None)
                    existing_end = shift.end_time.replace(tzinfo=None)
                    if start_dt < existing_end and end_dt > existing_start:
                        keyboard = InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton(
                                    '← Вернуться к созданию смены',
                                    callback_data='continue_creating_shifts',
                                )
                            ]
                        ])
                        await query.edit_message_text(
                            f'❌ Ошибка: пересечение с существующей сменой!\n'
                            f'Конфликтующая смена: '
                            f'{shift.start_time.strftime("%d.%m.%Y %H:%M")}-'
                            f'{shift.end_time.strftime("%H:%M")}',
                            reply_markup=keyboard,
                        )
                        return EDIT_SHIFT_FIELDS

                shift_create = ShiftCreate(
                    start_time=start_dt,
                    end_time=end_dt,
                    barista_count=shift_data['barista_count'],
                    cafe_id=shift_data['cafe_id'],
                )
                # async with async_session_maker() as session:
                shift = await shift_crud.create(
                    obj_in=shift_create, session=session
                )

                # Получаем обновленный список смен
                shifts = await shift_crud.get_multi(
                    session=session, cafe_id=shift_data['cafe_id']
                )
                # Формируем сообщение с подтверждением и списком смен
                shifts_list = '\n'.join(
                    f'• {s.start_time.strftime("%d.%m.%Y %H:%M")}-'
                    f'{s.end_time.strftime("%H:%M")} '
                    f'({s.barista_count} бариста)'
                    for s in sorted(shifts, key=lambda x: x.start_time)
                )

                message = (
                    f'✅ Смена успешно создана!\n\n'
                    f'📅 Текущие смены кафе:\n{shifts_list}\n\n'
                    f'Создать еще одну смену?'
                )

                # Кнопки для продолжения
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            'Да', callback_data='continue_creating_shifts'
                        ),
                        InlineKeyboardButton(
                            'Нет', callback_data='finish_creating_shifts'
                        ),
                    ]
                ])
                await query.edit_message_text(message, reply_markup=keyboard)
                context.user_data['current_cafe_id'] = shift_data['cafe_id']
            return CONFIRM_SHIFT_DATA
        except Exception as e:
            logger.error('Error creating shift: %s', e)
            await query.edit_message_text(
                'Ошибка при создании слота', reply_markup=None
            )
        return await show_start_menu(update, context)

    async def cancel_shift_creation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отменяет создание слота."""
        query = update.callback_query
        await query.answer()

        await query.edit_message_text(
            'Создание слота отменено', reply_markup=None
        )

        if 'new_shift' in context.user_data:
            del context.user_data['new_shift']

        return await show_start_menu(update, context)

    async def handle_continue_choice(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор продолжения создания смен."""
        query = update.callback_query
        await query.answer()

        choice = query.data

        if choice == 'continue_creating_shifts':
            # Инициализируем новую смену с теми же данными кафе
            cafe_id = context.user_data.get('current_cafe_id')
            if cafe_id:
                # Очищаем предыдущие данные, кроме cafe_id
                context.user_data['new_shift'] = {
                    'date': datetime.now().date(),
                    'start_time': None,
                    'end_time': None,
                    'barista_count': None,
                    'cafe_id': cafe_id,
                }

                # Удаляем сообщение с кнопками
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=query.message.message_id,
                )

                return await self.edit_shift_fields(update, context)

        # Если выбрано "Нет" или cafe_id не найден
        await query.edit_message_text(
            'Завершение создания смен', reply_markup=None
        )

        # Очищаем временные данные
        context.user_data.clear()

        return await show_start_menu(update, context)

    async def handle_back_to_editing(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает возврат к редактированию смены."""
        query = update.callback_query
        await query.answer()
        return await self.edit_shift_fields(update, context)

    def get_conversation_handler(self) -> ConversationHandler:
        """Возвращает обработчик диалога создания слота."""
        return ConversationHandler(
            entry_points=[
                CommandHandler('create_shift', self.create_shift_start),
                CallbackQueryHandler(
                    self.create_shift_start, pattern='^create_shift$'
                ),
            ],
            states={
                CONFIRM_SHIFT_DATA: [
                    CallbackQueryHandler(
                        self.proceed_to_create_shift,
                        pattern='^proceed_to_create_shift$',
                    ),
                    CallbackQueryHandler(
                        self.handle_continue_choice,
                        pattern=(
                            '^(continue_creating_shifts|'
                            'finish_creating_shifts)$'
                        ),
                    ),
                    CallbackQueryHandler(
                        self.cancel_shift_creation,
                        pattern='^cancel_shift_creation$',
                    ),
                ],
                EDIT_SHIFT_FIELDS: [
                    CallbackQueryHandler(
                        self.edit_shift_field, pattern='^edit_shift_'
                    ),
                    CallbackQueryHandler(
                        self.save_shift, pattern='^save_shift$'
                    ),
                    CallbackQueryHandler(
                        self.cancel_shift_creation,
                        pattern='^cancel_shift_creation$',
                    ),
                    CallbackQueryHandler(
                        self.handle_back_to_editing,
                        pattern='^continue_creating_shifts$',
                    ),
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.process_shift_field_input,
                    ),
                ],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
            per_message=False,
        )

    def setup_handlers(self, application: Application) -> None:
        """Регистрирует обработчики команд."""
        application.add_handler(self.get_conversation_handler())
