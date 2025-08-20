import asyncio
import logging

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
from app.schemas.user_schema import UserCreate
from app.tasks.barista_start import notify_manager_about_barista
from app.telegram_bot.commands import cancel, show_start_menu

logger = logging.getLogger(__name__)

SELECT_ROLE, EDIT_FIELDS, SELECT_CAFE = range(3)

SELF_TG_ID = "" #Для проверки уведомлений добавьте свой тг


class CreateUserHandler:
    """Обработчик для диалога создания пользователя."""

    def __init__(self) -> None:
        """Инициализация."""
        self.user_data_template = {
            "name": None,
            "telegram_id": None,
            "phone": None,
            "role": None,
            "password": None,
            "cafe_id": None,
        }

    async def _initialize_data(
        self, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if "new_user" not in context.user_data:
            context.user_data["new_user"] = self.user_data_template.copy()

    async def start_by_admin(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Вход для администратора: выбор роли."""
        query = update.callback_query
        if query:
            await query.answer()

        await self._initialize_data(context)
        context.user_data["is_self_registering"] = False

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Администратор", callback_data="role_admin"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "Менеджер", callback_data="role_manager"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "Бариста", callback_data="role_barista"
                    )
                ],
            ]
        )
        message = "Выберите роль нового пользователя:"

        if query:
            await query.edit_message_text(message, reply_markup=keyboard)
        else:
            await context.bot.send_message(
                update.effective_chat.id, text=message, reply_markup=keyboard
            )
        return SELECT_ROLE

    async def self_register_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Вход для саморегистрации."""
        query = update.callback_query
        await query.answer()
        await self._initialize_data(context)

        # Сразу устанавливаем флаг, роль и telegram_id
        context.user_data["is_self_registering"] = True
        context.user_data["new_user"]["role"] = "barista"
        context.user_data["new_user"]["telegram_id"] = update.effective_user.id
        context.user_data["new_user"]["is_active"] = False

        # Сразу переходим к заполнению полей
        return await self.edit_fields(update, context)

    async def select_role(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обработка выбора роли (только для админа)."""
        query = update.callback_query
        await query.answer()
        role = query.data.replace("role_", "")
        context.user_data["new_user"]["role"] = role
        return await self.edit_fields(update, context)

    async def edit_fields(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отображение полей пользователя для редактирования."""
        query = update.callback_query
        if query:
            try:
                await context.bot.delete_message(
                    chat_id=query.message.chat_id,
                    message_id=query.message.message_id
                )
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение: {e}")

        user_data = context.user_data["new_user"]
        role = user_data["role"]
        is_self_reg = context.user_data.get("is_self_registering", False)

        buttons = []
        fields_map = {
            "name": "Имя",
            "telegram_id": "Telegram ID",
            "phone": "Телефон",
            "password": "Пароль",
        }

        for field, label in fields_map.items():
            # Пропускаем кнопку Telegram ID при саморегистрации
            if field == "telegram_id" and is_self_reg:
                continue
            if field == "password" and role not in ["admin", "manager"]:
                continue

            field_value = user_data.get(field) or "Не указано"
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"{label}: {field_value}",
                        callback_data=f"edit_user_{field}",
                    )
                ]
            )

        if role in ["barista", "manager"]:
            cafe_text = "Не выбрано"
            if user_data["cafe_id"]:
                async with async_session_maker() as session:
                    cafe = await cafe_crud.get(user_data["cafe_id"], session)
                    cafe_text = cafe.address if cafe else "Неизвестное кафе"
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"Кафе: {cafe_text}", callback_data="user_select_cafe"
                    )
                ]
            )

        buttons.extend(
            [
                [
                    InlineKeyboardButton(
                        "✅ Сохранить", callback_data="save_user"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ Отменить", callback_data="cancel_creation"
                    )
                ],
            ]
        )
        keyboard = InlineKeyboardMarkup(buttons)
        message = (
            "Заполните свои данные:"
            if is_self_reg
            else "Заполните данные пользователя:"
        )

        if query:
            msg = await context.bot.send_message(
                query.message.chat_id, text=message, reply_markup=keyboard
            )
        else:
            msg = await context.bot.send_message(
                update.effective_chat.id, text=message, reply_markup=keyboard
            )
        context.user_data["last_keyboard_message_id"] = msg.message_id
        return EDIT_FIELDS

    async def edit_field_prompt(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Запрос ввода для конкретного поля."""
        query = update.callback_query
        await query.answer()
        field = query.data.replace("edit_user_", "")
        context.user_data["editing_field"] = field
        prompts = {
            "name": "Введите имя:",
            "telegram_id": "Введите Telegram ID:",
            "phone": "Введите номер телефона:",
            "password": "Введите пароль (мин. 6 символов):",
        }
        await context.bot.delete_message(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id
        )

        # Отправляем новое сообщение и сохраняем его ID
        msg = await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=prompts[field]
        )
        context.user_data["last_prompt_message_id"] = msg.message_id

        return EDIT_FIELDS

    @staticmethod
    async def _delete_message_after_delay(
        context: ContextTypes.DEFAULT_TYPE,
        chat_id: int,
        message_id: int,
        delay: int = 3
    ) -> None:
        """Удаляет сообщение после задержки."""
        await asyncio.sleep(delay)
        try:
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=message_id
            )
        except Exception:
            pass

    async def process_field_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обработка введенного значения."""
        field = context.user_data.get("editing_field")
        if not field:
            return ConversationHandler.END

        value = update.message.text
        asyncio.create_task(
            self._delete_message_after_delay(
                context,
                update.effective_chat.id,
                update.message.message_id,
            )
        )
        try:
            if field == "telegram_id" and not value.isdigit():
                raise ValueError("Telegram ID должен содержать только цифры.")
            if field == "password" and len(value) < 6:
                raise ValueError("Пароль должен содержать минимум 6 символов.")
            if field == "phone" and not value.startswith("+"):
                value = f"+{value}"
            if field == "telegram_id":
                value = int(value)
        except ValueError as e:
            msg = await update.message.reply_text(str(e))
            await asyncio.sleep(3)
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=msg.message_id
            )
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )
            return EDIT_FIELDS

        context.user_data["new_user"][field] = value

        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )

        if "last_prompt_message_id" in context.user_data:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=context.user_data["last_prompt_message_id"]
                )
            except Exception:
                pass

        return await self.edit_fields(update, context)

    async def select_cafe(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Выбор кафе."""
        query = update.callback_query
        await query.answer()
        async with async_session_maker() as session:
            cafes = await cafe_crud.get_multi(session)
        buttons = [
            [
                InlineKeyboardButton(
                    cafe.address, callback_data=f"set_cafe_{cafe.id}"
                )
            ]
            for cafe in cafes
        ]
        buttons.append(
            [InlineKeyboardButton("⏪ Назад", callback_data="back_to_edit")]
        )
        await query.edit_message_text(
            "Выберите кафе:", reply_markup=InlineKeyboardMarkup(buttons)
        )
        return SELECT_CAFE

    async def set_cafe(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Присвоение кафе."""
        query = update.callback_query
        await query.answer()
        if "back_to_edit" in query.data:
            return await self.edit_fields(update, context)
        cafe_id = int(query.data.replace("set_cafe_", ""))
        context.user_data["new_user"]["cafe_id"] = cafe_id
        return await self.edit_fields(update, context)

    async def save_user(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Сохранение пользователя."""
        query = update.callback_query
        await query.answer()
        try:
        # Try to edit the message first instead of deleting
            await query.edit_message_text("Сохранение пользователя...")
        except Exception as e:
            logger.warning(f"Не удалось изменить сообщение: {e}")
            # If edit fails, send a new message
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Сохранение пользователя..."
            )
        user_data = context.user_data["new_user"]

        try:
            if user_data["role"] in [
                "barista",
                "manager",
            ] and not user_data.get("cafe_id"):
                raise ValueError("Для этой роли необходимо выбрать кафе.")

            user_create = UserCreate(**user_data)
            async with async_session_maker() as session:
                user = await crud_user.create(
                    obj_in=user_create, session=session
                )
            if context.user_data["is_self_registering"] is False:
                await query.edit_message_text(
                    f"Пользователь {user.name} успешно создан!"
                )
            else:
                await query.edit_message_text(
                    f"Спасибо {user.name} за регистрацию,"
                    "ожидайте подтверждения от управляющего."
                )
                cafe = await cafe_crud.get_with_manager(
                    cafe_id=user_data["cafe_id"],
                    session=session
                )
                if cafe and cafe.manager:
                    notify_manager_about_barista.delay(
                        manager_tg_id=SELF_TG_ID,
                        #manager_tg_id=cafe.manager.telegram_id
                        barista_name=user.name,
                        barista_phone=user.phone,
                        cafe_name=cafe.name
                    )
        except Exception as e:
            logger.error(f"Error creating user: {e}", exc_info=True)
            await query.edit_message_text(f"Ошибка при создании: {e}")

        if "new_user" in context.user_data:
            del context.user_data["new_user"]
        if "is_self_registering" in context.user_data:
            del context.user_data["is_self_registering"]
        if "last_prompt_message_id" in context.user_data:
            del context.user_data["last_prompt_message_id"]
        if "last_keyboard_message_id" in context.user_data:
            del context.user_data["last_keyboard_message_id"]
        return await show_start_menu(update, context)

    async def cancel_creation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отменяет создание пользователя."""
        query = update.callback_query
        await query.answer()

        await query.edit_message_text(
            'Создание пользователя отменено', reply_markup=None
        )

        if 'new_user' in context.user_data:
            del context.user_data['new_user']
        if "is_self_registering" in context.user_data:
            del context.user_data["is_self_registering"]

        return await show_start_menu(update, context)

    def get_conversation_handler(self) -> ConversationHandler:
        """Возвращает ConversationHandler для создания пользователя."""
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    self.start_by_admin, pattern="^create_user$"
                ),
                CallbackQueryHandler(
                    self.self_register_start, pattern="^register_barista$"
                ),
            ],
            states={
                SELECT_ROLE: [
                    CallbackQueryHandler(self.select_role, pattern="^role_")
                ],
                EDIT_FIELDS: [
                    CallbackQueryHandler(
                        self.edit_field_prompt, pattern="^edit_user_"
                    ),
                    CallbackQueryHandler(
                        self.save_user, pattern="^save_user$"
                    ),
                    CallbackQueryHandler(
                        self.select_cafe, pattern="^user_select_cafe$"
                    ),
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.process_field_input,
                    ),
                    CallbackQueryHandler(
                        self.cancel_creation,
                        pattern='^cancel_creation$',
                    ),
                ],
                SELECT_CAFE: [
                    CallbackQueryHandler(
                        self.set_cafe, pattern="^set_cafe_|^back_to_edit$"
                    )
                ],
            },
            fallbacks=[
                CommandHandler("cancel", cancel),
            ],
            per_message=False,
            name="create_user_conversation",
            persistent=False,
        )

    def setup_handlers(self, application: Application) -> None:
        """Регистрирует обработчики команд."""
        application.add_handler(self.get_conversation_handler())
        application.add_handler(
            CommandHandler("create_user", self.start_by_admin)
            )
