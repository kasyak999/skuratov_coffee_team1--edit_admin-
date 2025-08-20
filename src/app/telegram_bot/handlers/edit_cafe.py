"""Модуль редактирования кафе с интерактивным интерфейсом."""

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
from app.schemas.cafe_schema import CafeUpdate
from app.telegram_bot.commands import cancel, show_start_menu

logger = logging.getLogger(__name__)

# Состояния для редактирования кафе
LIST_CAFES, SELECT_CAFE, EDIT_CAFE_FIELDS, SELECT_MANAGER = range(4)


class EditCafeHandler:
    """Обработчик редактирования кафе с интерактивным интерфейсом."""

    def __init__(self) -> None:
        """Инициализация обработчика."""
        self.cafe_crud = cafe_crud
        self.editing_fields = {
            'name': 'Название',
            'city': 'Город',
            'address': 'Адрес',
            'open_time': 'Время открытия (ЧЧ:ММ)',
            'close_time': 'Время закрытия (ЧЧ:ММ)',
            'phone': 'Телефон',
            'description': 'Описание',
            'manager_id': 'Менеджер',
            'is_active': 'Активность'
        }

    async def list_cafes_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Начинает процесс редактирования кафе - показывает список кафе."""
        query = update.callback_query
        if query:
            await query.answer()

        async with async_session_maker() as session:
            cafes = await cafe_crud.get_multi(session)

            if not cafes:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Нет доступных кафе для редактирования."
                )
                return await show_start_menu(update, context)

            buttons = []
            for cafe in cafes:
                buttons.append([
                    InlineKeyboardButton(
                        f"{cafe.name} ({cafe.city}, {cafe.address})",
                        callback_data=f"select_cafe_{cafe.id}"
                    )
                ])

            buttons.append([
                InlineKeyboardButton(
                    "❌ Отменить", callback_data="cancel_edit_cafe")
            ])

            keyboard = InlineKeyboardMarkup(buttons)

            try:
                if query:
                    await query.edit_message_text(
                        "Выберите кафе для редактирования:",
                        reply_markup=keyboard
                    )
                else:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="Выберите кафе для редактирования:",
                        reply_markup=keyboard
                    )
            except Exception as e:
                logger.error('Error in list_cafes_start: %s', e)
                return await show_start_menu(update, context)

        return LIST_CAFES

    async def select_cafe(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор кафе для редактирования."""
        query = update.callback_query
        await query.answer()

        if query.data == "cancel_edit_cafe":
            await query.edit_message_text(
                "Редактирование кафе отменено.",
                reply_markup=None
            )
            return await show_start_menu(update, context)

        cafe_id = int(query.data.replace("select_cafe_", ""))
        context.user_data["editing_cafe_id"] = cafe_id

        async with async_session_maker() as session:
            cafe = await cafe_crud.get(cafe_id, session)
            if not cafe:
                await query.edit_message_text(
                    "Кафе не найдено.",
                    reply_markup=None
                )
                return await show_start_menu(update, context)

            context.user_data["current_cafe"] = {
                'name': cafe.name,
                'city': cafe.city,
                'address': cafe.address,
                'open_time': cafe.open_time,
                'close_time': cafe.close_time,
                'phone': cafe.phone,
                'description': cafe.description,
                'manager_id': cafe.manager_id,
                'is_active': cafe.is_active
            }

        return await self.edit_cafe_fields(update, context)

    async def edit_cafe_fields(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отображает поля кафе для редактирования."""
        query = update.callback_query
        if query:
            await query.answer()

        cafe_id = context.user_data.get("editing_cafe_id")
        if not cafe_id:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Ошибка: не выбрано кафе для редактирования."
            )
            return await show_start_menu(update, context)

        cafe_data = context.user_data["current_cafe"]

        buttons = []
        for field, label in self.editing_fields.items():
            field_value = cafe_data.get(field)

            if field_value is None:
                field_value = "Не указано"
            elif isinstance(field_value, bool):
                field_value = "Да" if field_value else "Нет"
            elif field == "manager_id" and field_value:
                async with async_session_maker() as session:
                    manager = await crud_user.get(field_value, session)
                    field_value = manager.name if manager else "Неизвестный"
            elif isinstance(field_value, time):
                field_value = field_value.strftime("%H:%M")

            buttons.append([
                InlineKeyboardButton(
                    f"{label}: {field_value}",
                    callback_data=f"edit_cafe_{field}"
                )
            ])

        buttons.append([
            InlineKeyboardButton("✅ Сохранить изменения",
                                 callback_data="save_cafe_changes"),
            InlineKeyboardButton(
                "❌ Отменить", callback_data="cancel_edit_cafe")
        ])

        keyboard = InlineKeyboardMarkup(buttons)
        message = "Редактирование кафе. Выберите поле для изменения:\n"

        try:
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
        except Exception as e:
            logger.error('Error in edit_cafe_fields: %s', e)
            return await show_start_menu(update, context)

        return EDIT_CAFE_FIELDS

    async def edit_cafe_field(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int | str:
        """Запрашивает редактирование конкретного поля."""
        query = update.callback_query
        await query.answer()

        field = query.data.replace("edit_cafe_", "")
        context.user_data["editing_field"] = field

        if field == "manager_id":
            return await self.select_manager(update, context)
        if field == "is_active":
            return await self.toggle_cafe_active(update, context)

        field_prompts = {
            "name": "Введите новое название кафе:",
            "city": "Введите новый город:",
            "address": "Введите новый адрес кафе:",
            "open_time": "Введите новое время открытия (ЧЧ:ММ):",
            "close_time": "Введите новое время закрытия (ЧЧ:ММ):",
            "phone": "Введите новый телефон кафе:",
            "description": "Введите новое описание кафе:",
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

    async def toggle_cafe_active(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Переключает статус активности кафе."""
        query = update.callback_query
        await query.answer()

        current_value = context.user_data["current_cafe"]["is_active"]
        context.user_data["current_cafe"]["is_active"] = not current_value

        return await self.edit_cafe_fields(update, context)

    async def select_manager(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Показывает список менеджеров для выбора и сохраняет ID сообщения."""
        query = update.callback_query
        await query.answer()

        async with async_session_maker() as session:
            managers = await crud_user.get_multi_by_role("manager", session)

            buttons = []
            for manager in managers:
                buttons.append([
                    InlineKeyboardButton(
                        f"{manager.name} (ID: {manager.telegram_id})",
                        callback_data=f"select_manager_{manager.id}",
                    )
                ])

            buttons.append([
                InlineKeyboardButton("⏪ Назад", callback_data="back_to_edit")
            ])

            keyboard = InlineKeyboardMarkup(buttons)
            message = await query.edit_message_text(
                "Выберите менеджера для кафе:", reply_markup=keyboard
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

        if query.data == "back_to_edit":
            return await self.edit_cafe_fields(update, context)

        manager_id = int(query.data.replace("select_manager_", ""))
        context.user_data["current_cafe"]["manager_id"] = manager_id

        return await self.edit_cafe_fields(update, context)

    async def process_cafe_field_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает введенное значение поля."""
        field = context.user_data.get("editing_field")
        if not field:
            await update.message.reply_text(
                "Ошибка: не указано поле для редактирования."
            )
            return await show_start_menu(update, context)

        value = update.message.text

        try:
            if field in ["open_time", "close_time"]:
                # Проверяем, есть ли смены у кафе
                cafe_id = context.user_data.get("editing_cafe_id")
                async with async_session_maker() as session:
                    cafe = await cafe_crud.get_with_stats(cafe_id, session)
                    if cafe and cafe.shifts:  # Проверяем наличие смен
                        warning_msg = await update.message.reply_text(
                            "Внимание! У этого кафе есть созданные смены. "
                            "После изменения времени работы необходимо "
                            "обновить соответствующие смены."
                        )
                        # Сохраняем ID предупреждения для удаления
                        if 'last_bot_messages' not in context.user_data:
                            context.user_data['last_bot_messages'] = []
                        context.user_data['last_bot_messages'].append(
                            warning_msg.message_id)

                hours, minutes = map(int, value.split(":"))
                value = time(hours, minutes)
            elif field == "phone" and not value.startswith("+"):
                value = f"+{value}"
        except Exception as e:
            logger.error('Error processing field %s: %s', field, e)
            await update.message.reply_text("Некорректный формат данных.")
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

        context.user_data["current_cafe"][field] = value

        return await self.edit_cafe_fields(update, context)

    async def save_cafe_changes(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Сохраняет изменения кафе в БД."""
        query = update.callback_query
        await query.answer()

        cafe_id = context.user_data.get("editing_cafe_id")
        if not cafe_id:
            await query.edit_message_text(
                "Ошибка: не выбрано кафе для редактирования.",
                reply_markup=None
            )
            return await show_start_menu(update, context)

        cafe_data = context.user_data["current_cafe"]

        # Удаляем поля, которые не изменились
        async with async_session_maker() as session:
            original_cafe = await cafe_crud.get(cafe_id, session)
            update_data = {}

            for field, value in cafe_data.items():
                original_value = getattr(original_cafe, field)
                if original_value != value:
                    update_data[field] = value

        if not update_data:
            await query.edit_message_text(
                "Изменений не обнаружено.",
                reply_markup=None
            )
            return await show_start_menu(update, context)

        try:
            cafe_update = CafeUpdate(**update_data)
            async with async_session_maker() as session:
                updated_cafe = await cafe_crud.update(
                    db_obj=original_cafe, obj_in=cafe_update, session=session
                )

            await query.edit_message_text(
                f"Кафе '{updated_cafe.name}' успешно обновлено!",
                reply_markup=None
            )
        except Exception as e:
            logger.error('Error updating cafe: %s', e)
            await query.edit_message_text(
                "Ошибка при обновлении кафе",
                reply_markup=None
            )

        # Очищаем данные после сохранения
        if "editing_cafe_id" in context.user_data:
            del context.user_data["editing_cafe_id"]
        if "current_cafe" in context.user_data:
            del context.user_data["current_cafe"]
        if "editing_field" in context.user_data:
            del context.user_data["editing_field"]

        return await show_start_menu(update, context)

    async def cancel_edit_cafe(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отменяет редактирование кафе."""
        query = update.callback_query
        await query.answer()

        await query.edit_message_text(
            "Редактирование кафе отменено",
            reply_markup=None
        )

        # Очищаем данные после отмены
        if "editing_cafe_id" in context.user_data:
            del context.user_data["editing_cafe_id"]
        if "current_cafe" in context.user_data:
            del context.user_data["current_cafe"]
        if "editing_field" in context.user_data:
            del context.user_data["editing_field"]

        return await show_start_menu(update, context)

    def get_conversation_handler(self) -> ConversationHandler:
        """Возвращает обработчик диалога редактирования кафе."""
        return ConversationHandler(
            entry_points=[
                CommandHandler("edit_cafe", self.list_cafes_start),
                CallbackQueryHandler(
                    self.list_cafes_start, pattern="^edit_cafe$"
                ),
            ],
            states={
                LIST_CAFES: [
                    CallbackQueryHandler(
                        self.select_cafe,
                        pattern="^select_cafe_|^cancel_edit_cafe$"
                    )
                ],
                SELECT_CAFE: [
                    CallbackQueryHandler(
                        self.select_cafe,
                        pattern="^select_cafe_|^cancel_edit_cafe$"
                    )
                ],
                EDIT_CAFE_FIELDS: [
                    CallbackQueryHandler(
                        self.edit_cafe_field, pattern="^edit_cafe_"
                    ),
                    CallbackQueryHandler(
                        self.save_cafe_changes, pattern="^save_cafe_changes$"
                    ),
                    CallbackQueryHandler(
                        self.cancel_edit_cafe, pattern="^cancel_edit_cafe$"
                    ),
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.process_cafe_field_input,
                    ),
                ],
                SELECT_MANAGER: [
                    CallbackQueryHandler(
                        self.process_manager_selection,
                        pattern="^select_manager_|^back_to_edit$",
                    )
                ],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            per_message=False,
        )

    def setup_handlers(self, application: Application) -> None:
        """Регистрирует обработчики команд."""
        application.add_handler(self.get_conversation_handler())
