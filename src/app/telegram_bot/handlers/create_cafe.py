"""Модуль создания кафе с интерактивным интерфейсом."""

import logging
from datetime import time

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
from app.crud.user_crud import crud_user
from app.schemas.cafe_schema import CafeCreate
from app.telegram_bot.commands import cancel, show_start_menu

logger = logging.getLogger(__name__)

# Состояния для создания кафе
EDIT_CAFE_FIELDS, SELECT_MANAGER = range(2)


class CreateCafeHandler:
    """Обработчик создания кафе с интерактивным интерфейсом."""

    def __init__(self) -> None:
        """Инициализация обработчика."""
        self.cafe_crud = cafe_crud
        self.cafe_data_template = {
            'name': None,
            'city': None,
            'address': None,
            'open_time': None,
            'close_time': None,
            'phone': None,
            'description': None,
            'manager_id': None,
            'is_active': True
        }

    async def initialize_cafe_data(
        self, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Инициализирует данные нового кафе."""
        if 'new_cafe' not in context.user_data:
            context.user_data['new_cafe'] = self.cafe_data_template.copy()

    async def create_cafe_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Начинает процесс создания кафе."""
        query = update.callback_query
        if query:
            await query.answer()

        await self.initialize_cafe_data(context)
        return await self.edit_cafe_fields(update, context)

    async def edit_cafe_fields(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отображает поля кафе для редактирования."""
        query = update.callback_query
        if query:
            await query.answer()

        await self.initialize_cafe_data(context)
        cafe_data = context.user_data['new_cafe']

        buttons = []
        fields = [
            ('name', 'Название'),
            ('city', 'Город'),
            ('address', 'Адрес'),
            ('open_time', 'Время открытия (ЧЧ:ММ)'),
            ('close_time', 'Время закрытия (ЧЧ:ММ)'),
            ('phone', 'Телефон'),
            ('description', 'Описание'),
            ('manager_id', 'Менеджер'),
        ]

        for field, label in fields:
            field_value = cafe_data[field] or 'Не указано'
            if field == 'manager_id' and cafe_data[field]:
                async with async_session_maker() as session:
                    manager = await crud_user.get(cafe_data[field], session)
                    field_value = manager.name if manager else 'Неизвестный'

            buttons.append([
                InlineKeyboardButton(
                    f'{label}: {field_value}',
                    callback_data=f'edit_cafe_{field}',
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                '✅ Сохранить кафе', callback_data='save_cafe'
            ),
            InlineKeyboardButton(
                '❌ Отменить', callback_data='cancel_cafe_creation'
            ),
        ])

        keyboard = InlineKeyboardMarkup(buttons)
        message = 'Заполните данные кафе:\n'

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
            logger.error('Error in edit_cafe_fields: %s', e)
            return ConversationHandler.END

        return EDIT_CAFE_FIELDS

    async def edit_cafe_field(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Запрашивает редактирование конкретного поля."""
        query = update.callback_query
        await query.answer()

        field = query.data.replace('edit_cafe_', '')
        context.user_data['editing_field'] = field

        if field == 'manager_id':
            return await self.select_manager(update, context)

        field_prompts = {
            'name': 'Введите название кафе:',
            'city': 'Введите город:',
            'address': 'Введите адрес кафе:',
            'open_time': 'Введите время открытия (ЧЧ:ММ):',
            'close_time': 'Введите время закрытия (ЧЧ:ММ):',
            'phone': 'Введите телефон кафе:',
            'description': 'Введите описание кафе:',
        }

        # Отправляем сообщение с запросом ввода
        message = await query.edit_message_text(
            field_prompts[field],
            reply_markup=None
        )

        # Сохраняем ID сообщения бота для последующего удаления
        if 'last_bot_messages' not in context.user_data:
            context.user_data['last_bot_messages'] = []
        context.user_data['last_bot_messages'].append(message.message_id)

        return EDIT_CAFE_FIELDS

    async def select_manager(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Показывает список менеджеров для выбора и сохраняет ID сообщения."""
        query = update.callback_query
        await query.answer()

        async with async_session_maker() as session:
            managers = await crud_user.get_multi_by_role('manager', session)

            buttons = []
            for manager in managers:
                buttons.append([
                    InlineKeyboardButton(
                        f'{manager.name} (ID: {manager.telegram_id})',
                        callback_data=f'select_manager_{manager.id}',
                    )
                ])

            buttons.append([
                InlineKeyboardButton('⏪ Назад', callback_data='back_to_edit')
            ])

            keyboard = InlineKeyboardMarkup(buttons)
            message = await query.edit_message_text(
                'Выберите менеджера для кафе:', reply_markup=keyboard
            )

            # Сохраняем ID сообщения бота для последующего удаления
            if 'last_bot_messages' not in context.user_data:
                context.user_data['last_bot_messages'] = []
            context.user_data['last_bot_messages'].append(message.message_id)

        return SELECT_MANAGER

    async def process_manager_selection(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор менеджера."""
        query = update.callback_query
        await query.answer()

        if query.data == 'back_to_edit':
            return await self.edit_cafe_fields(update, context)

        manager_id = int(query.data.replace('select_manager_', ''))
        await self.initialize_cafe_data(context)
        context.user_data['new_cafe']['manager_id'] = manager_id

        return await self.edit_cafe_fields(update, context)

    async def process_cafe_field_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает введенное значение поля."""
        field = context.user_data.get('editing_field')
        if not field:
            await update.message.reply_text(
                'Ошибка: не указано поле для редактирования.'
            )
            return ConversationHandler.END

        value = update.message.text

        try:
            if field in ['open_time', 'close_time']:
                hours, minutes = map(int, value.split(':'))
                value = time(hours, minutes)
            elif field == 'phone' and not value.startswith('+'):
                value = f'+{value}'
        except Exception as e:
            logger.error('Error processing field %s: %s', field, e)
            await update.message.reply_text('Некорректный формат данных.')
            return EDIT_CAFE_FIELDS

        # Удаляем предыдущие сообщения бота (запросы на ввод)
        if 'last_bot_messages' in context.user_data:
            for msg_id in context.user_data['last_bot_messages']:
                try:
                    await context.bot.delete_message(
                        chat_id=update.effective_chat.id,
                        message_id=msg_id,
                    )
                except Exception as e:
                    logger.error(f"Error deleting message {msg_id}: {e}")
            del context.user_data['last_bot_messages']

        # Удаляем сообщение пользователя с вводом данных
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
        )

        await self.initialize_cafe_data(context)
        context.user_data['new_cafe'][field] = value

        return await self.edit_cafe_fields(update, context)

    async def save_cafe(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Сохраняет кафе в БД."""
        query = update.callback_query
        await query.answer()

        await self.initialize_cafe_data(context)
        cafe_data = context.user_data['new_cafe']

        required_fields = [
            'name',
            'city',
            'address',
            'open_time',
            'close_time',
            'phone'
        ]
        missing_fields = [
            field for field in required_fields if not cafe_data.get(field)
        ]

        if missing_fields:
            await query.edit_message_text(
                f'Ошибка: не заполнены поля: {", ".join(missing_fields)}!',
                reply_markup=None,
            )
            return await show_start_menu(update, context)

        try:
            cafe_create = CafeCreate(**cafe_data)
            async with async_session_maker() as session:
                cafe = await cafe_crud.create(
                    obj_in=cafe_create, session=session
                )

            await query.edit_message_text(
                f'Кафе по адресу: город {cafe.city}, {cafe.address} успешно '
                f'создано!',
                reply_markup=None,
            )
        except Exception as e:
            logger.error('Error creating cafe: %s', e)
            await query.edit_message_text(
                'Ошибка при создании кафе', reply_markup=None
            )

        if 'new_cafe' in context.user_data:
            del context.user_data['new_cafe']

        return await show_start_menu(update, context)

    async def cancel_cafe_creation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отменяет создание кафе."""
        query = update.callback_query
        await query.answer()

        await query.edit_message_text(
            'Создание кафе отменено', reply_markup=None
        )

        if 'new_cafe' in context.user_data:
            del context.user_data['new_cafe']

        return await show_start_menu(update, context)

    def get_conversation_handler(self) -> ConversationHandler:
        """Возвращает обработчик диалога создания кафе."""
        return ConversationHandler(
            entry_points=[
                CommandHandler('create_cafe', self.create_cafe_start),
                CallbackQueryHandler(
                    self.create_cafe_start, pattern='^create_cafe$'
                ),
            ],
            states={
                EDIT_CAFE_FIELDS: [
                    CallbackQueryHandler(
                        self.edit_cafe_field, pattern='^edit_cafe_'
                    ),
                    CallbackQueryHandler(
                        self.save_cafe, pattern='^save_cafe$'
                    ),
                    CallbackQueryHandler(
                        self.cancel_cafe_creation,
                        pattern='^cancel_cafe_creation$',
                    ),
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.process_cafe_field_input,
                    ),
                ],
                SELECT_MANAGER: [
                    CallbackQueryHandler(
                        self.process_manager_selection,
                        pattern='^select_manager_|^back_to_edit$',
                    )
                ],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
            per_message=False,
        )

    def setup_handlers(self, application: Application) -> None:
        """Регистрирует обработчики команд."""
        application.add_handler(self.get_conversation_handler())
