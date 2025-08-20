import logging
from enum import IntEnum

from pydantic import ValidationError as PydanticValidationError
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
from app.crud.user_crud import crud_user
from app.models.user import User
from app.schemas.user_schema import UserRead, UserUpdate
from app.telegram_bot.commands import show_start_menu
from app.telegram_bot.handlers.base import BaseHandler

logger = logging.getLogger(__name__)


# Состояния диалога
class EditUserStates(IntEnum):
    """Состояния диалога редактирования пользователя."""

    AWAITING_QUERY = 0
    SELECTING = 1
    EDITING_FIELD = 2


# 📌 Префиксы
CB_SELECT_PREFIX = 'select_user_'
CB_EDIT_PREFIX = 'edit_'
CB_SAVE = 'save_changes'
CB_CANCEL = 'cancel_edit'

SELECT_PATTERN = rf'^{CB_SELECT_PREFIX}\d+$'
EDIT_PATTERN = rf'^{CB_EDIT_PREFIX}\w+$'
SAVE_PATTERN = rf'^{CB_SAVE}$'
CANCEL_PATTERN = rf'^{CB_CANCEL}$'

# 🧾 Сообщения
MSG_ENTER_QUERY = (
    '🔎 <b>Поиск пользователя</b>\n\n'
    'Введите одно из значений:\n'
    '• <b>Имя</b> (например, <code>Иван</code>)\n'
    '• <b>Телефон</b> (например, <code>+79991234567</code>)\n'
    '• <b>Telegram ID</b> (например, <code>123456789</code>)\n\n'
    'Подсказка: можно ввести часть имени или номера.'
)
MSG_NO_RESULTS = 'Пользователь не найден.'
MSG_SELECT_USER = 'Выберите пользователя из списка:'
MSG_UPDATED_FIELD = (
    'Поле "{field}" обновлено. '
    'Выберите следующее поле или нажмите "Сохранить".'
)
MSG_FIELD_INPUT = 'Введите новое значение для поля: «{field}»'
MSG_CHOOSE_STATUS = '🔄 Выберите новый статус:'
MSG_CHOOSE_ROLE = '🔐 Выберите роль:'
MSG_UPDATED = '✅ Данные пользователя обновлены.'
MSG_CANCELLED = 'Редактирование отменено.'
MSG_ERROR = '❗ {error}'
MSG_ALREADY_SAVING = 'Уже сохраняется…'
MSG_EDIT_PROMPT = (
    'Редактирование пользователя:\n\n'
    'Имя: {name}\n'
    'Телефон: {phone}\n\n'
    'Выберите поле:'
)

CB_STATUS_PREFIX = 'status_'
STATUS_ACTIVE = 'active'
STATUS_INACTIVE = 'inactive'
STATUS_PATTERN = rf'^{CB_STATUS_PREFIX}({STATUS_ACTIVE}|{STATUS_INACTIVE})$'

LABEL_STATUS_ACTIVE   = '✅ Активный'
LABEL_STATUS_INACTIVE = '⛔ Неактивный'
LABEL_BACK            = '🔙 Назад'

CB_ROLE_PREFIX = 'role_'
ROLE_BARISTA   = 'barista'
ROLE_MANAGER   = 'manager'
ROLE_ADMIN     = 'admin'
ROLE_PATTERN = (
    rf'^{CB_ROLE_PREFIX}({ROLE_BARISTA}|'
    rf'{ROLE_MANAGER}|{ROLE_ADMIN})$'
)

LABEL_ROLE_BARISTA = '👤 Бариста'
LABEL_ROLE_MANAGER = '🧑‍💼 Менеджер'
LABEL_ROLE_ADMIN   = '🛡️ Админ'


def human_status(v: bool | None) -> str:
    """Возвращает статус Active при True, Inactive при False ."""
    return LABEL_STATUS_ACTIVE if v else LABEL_STATUS_INACTIVE


def human_role(v: object) -> str:
    """Преобразует объект роли в человекочитаемое название."""
    raw = getattr(v, 'value', getattr(v, 'name', str(v))).lower()
    mapping = {
        'barista': 'Бариста',
        'manager': 'Менеджер',
        'admin': 'Админ'}
    return mapping.get(raw, raw)


def build_role_keyboard(current: object | None) -> InlineKeyboardMarkup:
    """Клавиатура выбора роли: Бариста / Менеджер / Админ + Назад/Отмена."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            LABEL_ROLE_BARISTA,
            callback_data=f'{CB_ROLE_PREFIX}{ROLE_BARISTA}')],
        [InlineKeyboardButton(
            LABEL_ROLE_MANAGER,
            callback_data=f'{CB_ROLE_PREFIX}{ROLE_MANAGER}')],
        [InlineKeyboardButton(
            LABEL_ROLE_ADMIN,
            callback_data=f'{CB_ROLE_PREFIX}{ROLE_ADMIN}')],
        [InlineKeyboardButton(
            LABEL_BACK,
            callback_data=CB_CANCEL)],
    ])


def build_status_keyboard(current: bool | None
                          ) -> InlineKeyboardMarkup:
    """Клавиатура выбора статуса: Активный / Неактивный + отмена."""
    buttons = [
        [
            InlineKeyboardButton(
                LABEL_STATUS_ACTIVE,
                callback_data=f'{CB_STATUS_PREFIX}{STATUS_ACTIVE}'),
            InlineKeyboardButton(
                LABEL_STATUS_INACTIVE,
                callback_data=f'{CB_STATUS_PREFIX}{STATUS_INACTIVE}'),
        ],
        [InlineKeyboardButton(
            LABEL_BACK,
            callback_data=CB_CANCEL)],
    ]
    return InlineKeyboardMarkup(buttons)


def build_keyboard(user: UserRead) -> InlineKeyboardMarkup:
    """Создание клавиатуры редактирования."""
    buttons = [
        [InlineKeyboardButton(
            f'✏️ Имя: {user.name}',
            callback_data=f'{CB_EDIT_PREFIX}Имя')],
        [InlineKeyboardButton(
            f'📱 Телефон: {user.phone}',
            callback_data=f'{CB_EDIT_PREFIX}Телефон')],
        [InlineKeyboardButton(
            f'🆔 Telegram ID: {user.telegram_id}',
            callback_data=f'{CB_EDIT_PREFIX}Telegram ID')],
        [InlineKeyboardButton(
            f'🔐 Роль: {human_role(user.role)}',
            callback_data=f'{CB_EDIT_PREFIX}Роль')],
        [InlineKeyboardButton(
            f'🏪 Кафе ID: {user.cafe_id}',
            callback_data=f'{CB_EDIT_PREFIX}Кафе ID')],
        [InlineKeyboardButton(
            f'🔄 Статус: {human_status(user.is_active)}',
            callback_data=f'{CB_EDIT_PREFIX}Статус'
        )],
        [InlineKeyboardButton(
            '✅ Сохранить',
            callback_data=CB_SAVE)],
        [InlineKeyboardButton(
            '❌ Отменить',
            callback_data=CB_CANCEL)],
    ]
    return InlineKeyboardMarkup(buttons)


class EditUserHandler(BaseHandler):
    """Обработчик команды /edit_user — редактирование пользователей."""

    def __init__(self) -> None:
        """Инициализация EditUserHandler."""
        self.user_crud = crud_user

    async def start_edit_user(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Начало диалога — запрос на ввод критерия поиска."""
        context.user_data.clear()
        await self.send_text_safely(
            update,
            MSG_ENTER_QUERY,
            parse_mode='HTML'
        )
        return EditUserStates.AWAITING_QUERY

    async def process_query(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обработка запроса админа (поиск пользователей по критерию)."""
        query = update.message.text.strip()
        async with async_session_maker() as session:
            users = await self.user_crud.search_by_query(query, session)

        if not users:
            await self.send_text_safely(update, MSG_NO_RESULTS)
            return EditUserStates.AWAITING_QUERY

        if len(users) == 1:
            return await self._select_user(update, context, users[0])

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                f'{u.name} ({u.phone})',
                callback_data=f'{CB_SELECT_PREFIX}{u.id}')
        ] for u in users])

        await self.send_text_safely(
            update,
            MSG_SELECT_USER,
            reply_markup=keyboard)
        return EditUserStates.SELECTING

    async def handle_user_selection(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обработка выбора юзера из списка (через inline-кнопку)."""
        query = update.callback_query
        await query.answer()

        user_id = int(query.data.replace(CB_SELECT_PREFIX, ''))
        async with async_session_maker() as session:
            user = await self.user_crud.get_or_404(user_id, session)
        return await self._select_user(update, context, user)

    async def _select_user(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
            user: User
    ) -> int:
        """Обработка выбора конкретного пользователя."""
        user_data = UserRead.model_validate(user)
        context.user_data['edit_user'] = user_data.model_dump()
        context.user_data['user_id'] = user.id
        await self.send_text_safely(
            update,
            MSG_EDIT_PROMPT.format(name=user.name, phone=user.phone),
            reply_markup=build_keyboard(user_data)
        )
        return EditUserStates.EDITING_FIELD

    async def choose_field(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Запоминает, какое поле редактировать, и просит ввести новое."""
        query = update.callback_query
        await query.answer()
        field = query.data.replace(CB_EDIT_PREFIX, '')
        context.user_data['editing_field'] = field

        if field == 'Статус':
            current = context.user_data.get('edit_user', {}).get('is_active')
            await query.edit_message_text(
                MSG_CHOOSE_STATUS,
                reply_markup=build_status_keyboard(current)
            )
            return EditUserStates.EDITING_FIELD

        if field == 'Роль':
            current_role = context.user_data.get('edit_user', {}).get('role')
            await query.edit_message_text(
                MSG_CHOOSE_ROLE,
                reply_markup=build_role_keyboard(current_role)
            )
            return EditUserStates.EDITING_FIELD

        await query.edit_message_text(MSG_FIELD_INPUT.format(field=field))
        return EditUserStates.EDITING_FIELD

    async def handle_new_value(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Принимает новое значение, проверяет и сохраняет."""
        field = context.user_data.get('editing_field')
        raw_value = update.message.text.strip()
        context.user_data['edit_user'][field] = raw_value
        try:
            UserUpdate(**context.user_data['edit_user'])
        except PydanticValidationError as e:
            await self.send_text_safely(
                update,
                MSG_ERROR.format(error=e.errors()[0]['msg']))
            return EditUserStates.EDITING_FIELD

        updated_user = UserRead(**context.user_data['edit_user'])
        await self.send_text_safely(
            update,
            MSG_UPDATED_FIELD.format(field=field),
            reply_markup=build_keyboard(updated_user)
        )
        return EditUserStates.EDITING_FIELD

    async def handle_status_choice(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает нажатие на Активный/Неактивный и валидирует."""
        query = update.callback_query
        await query.answer()

        choice = query.data.replace(CB_STATUS_PREFIX, '')
        is_active = (choice == STATUS_ACTIVE)
        context.user_data['edit_user']['is_active'] = is_active

        try:
            UserUpdate(**context.user_data['edit_user'])
        except PydanticValidationError as e:
            await query.edit_message_text(MSG_ERROR.format(
                error=e.errors()[0]['msg']))
            return EditUserStates.EDITING_FIELD

        updated_user = UserRead(**context.user_data['edit_user'])
        await query.edit_message_text(
            MSG_UPDATED_FIELD.format(field='Статус'),
            reply_markup=build_keyboard(updated_user)
        )
        return EditUserStates.EDITING_FIELD

    async def handle_role_choice(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает нажатие на выбор роли и валидирует."""
        query = update.callback_query
        await query.answer()
        role_choice = query.data.replace(CB_ROLE_PREFIX, '')
        context.user_data['edit_user']['role'] = role_choice
        try:
            UserUpdate(**context.user_data['edit_user'])
        except PydanticValidationError as e:
            await query.edit_message_text(
                MSG_ERROR.format(error=e.errors()[0]['msg']))
            return EditUserStates.EDITING_FIELD

        updated_user = UserRead(**context.user_data['edit_user'])
        await query.edit_message_text(
            MSG_UPDATED_FIELD.format(field='Роль'),
            reply_markup=build_keyboard(updated_user)
        )
        return EditUserStates.EDITING_FIELD

    async def confirm_save(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Сохраняет изменения в базе данных после подтверждения.

        Завершает диалог редактирования.
        """
        query = update.callback_query
        if context.user_data.get('saving'):
            await query.answer(MSG_ALREADY_SAVING)
            return await show_start_menu(update, context)

        context.user_data['saving'] = True
        await query.answer()

        user_id = context.user_data['user_id']
        update_data = UserUpdate(**context.user_data['edit_user'])

        async with async_session_maker() as session:
            db_user = await self.user_crud.get_or_404(user_id, session)
            await self.user_crud.update(
                db_obj=db_user,
                obj_in=update_data,
                session=session
            )
        # await self.send_text_safely(update, MSG_UPDATED)
        await query.edit_message_text(MSG_UPDATED)
        return await show_start_menu(update, context)

    async def cancel(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Переопределен с поддержкой inline-кнопок и красивым выводом."""
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(MSG_CANCELLED)
        else:
            await self.send_text_safely(update, MSG_CANCELLED)
        return await show_start_menu(update, context)

    def get_handler(self) -> ConversationHandler:
        """Возвращает ConversationHandler для редактирования пользователя."""
        return ConversationHandler(
            entry_points=[
                CommandHandler(
                    'edit_user', self.start_edit_user),
                CallbackQueryHandler(
                    self.start_edit_user,
                    pattern='^edit_user$')
            ],
            states={
                EditUserStates.AWAITING_QUERY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND,
                                   self.process_query)],
                EditUserStates.SELECTING: [
                    CallbackQueryHandler(self.handle_user_selection,
                                         pattern=SELECT_PATTERN)],
                EditUserStates.EDITING_FIELD: [
                    CallbackQueryHandler(self.handle_status_choice,
                                         pattern=STATUS_PATTERN),
                    CallbackQueryHandler(self.handle_role_choice,
                                         pattern=ROLE_PATTERN),
                    CallbackQueryHandler(self.choose_field,
                                         pattern=EDIT_PATTERN),
                    CallbackQueryHandler(self.confirm_save,
                                         pattern=SAVE_PATTERN),
                    CallbackQueryHandler(self.cancel,
                                         pattern=CANCEL_PATTERN),
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.handle_new_value),
                ],
            },
            fallbacks=[
                CommandHandler(
                    'cancel',
                    self.cancel)],
            per_message=False,
        )

    def setup(self, app: Application) -> None:
        """Подключает обработчик диалога к приложению Telegram-бота."""
        app.add_handler(self.get_handler())
