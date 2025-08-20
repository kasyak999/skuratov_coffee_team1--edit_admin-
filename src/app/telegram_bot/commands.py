from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import ContextTypes, ConversationHandler

from app.core.db import async_session_maker
from app.crud.user_crud import crud_user


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущее действие и возвращает в главное меню."""
    try:
        if update.message:
            await update.message.reply_text(
                "Действие отменено.",
                reply_markup=ReplyKeyboardRemove()
            )
        elif update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                "Действие отменено.",
                reply_markup=None
            )

        # Очищаем user_data
        if context.user_data:
            context.user_data.clear()

        return await show_start_menu(update, context)
    except Exception:
        return ConversationHandler.END


async def show_start_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Показывает стартовое меню в зависимости от роли пользователя."""
    role_mapping = {
        'admin': 'Администратор',
        'manager': 'Управляющий',
        'barista': 'Бариста',
    }

    async with async_session_maker() as session:
        user = await crud_user.get_by_telegram_id(
            update.effective_user.id, session=session
        )

    if not user:
        # Пользователь не зарегистрирован
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    'Зарегистрироваться как Бариста',
                    callback_data='register_barista',
                )
            ]
        ])
        text = 'Вы не зарегистрированы в системе. '
        'Хотите зарегистрироваться как Бариста?'
    else:
        # Определяем клавиатуру в зависимости от роли
        if user.role == 'admin':
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    '➕ Создать пользователя',
                    callback_data='create_user'
                )],
                [InlineKeyboardButton(
                    '➕ Создать кафе',
                    callback_data='create_cafe'
                )],
                [InlineKeyboardButton(
                    '📝 Редактировать пользователя',
                    callback_data='edit_user'
                )],
                [InlineKeyboardButton(
                    '📝 Редактировать кафе',
                    callback_data='edit_cafe'
                )],
                [InlineKeyboardButton("────────────", callback_data="none")],
                [InlineKeyboardButton(
                    '➕ Подтвердить пользователя',
                    callback_data='user_conf'
                )],
                [InlineKeyboardButton(
                    '➕ Подтвердить выход на работу',
                    callback_data='employment_conf'
                )],
                [InlineKeyboardButton(
                    '📊 Мониторинг смен кафе',
                    callback_data='monitoring'
                )],
                [InlineKeyboardButton(
                    '➕ Создать слот',
                    callback_data='create_shift'
                )],
                [InlineKeyboardButton(
                    '📝 Редактировать слот',
                    callback_data='edit_shifts'
                )],
            ])
        elif user.role == 'manager':
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    '➕ Подтвердить пользователя',
                    callback_data='user_conf'
                )],
                [InlineKeyboardButton(
                    '➕ Подтвердить выход на работу',
                    callback_data='employment_conf'
                )],
                [InlineKeyboardButton(
                    '📊 Мониторинг смен кафе',
                    callback_data='monitoring'
                )],
                [InlineKeyboardButton(
                    '➕ Создать слот',
                    callback_data='create_shift'
                )],
                [InlineKeyboardButton(
                    '📝 Редактировать слот',
                    callback_data='edit_shifts'
                )],
                [
                    InlineKeyboardButton(
                        '📝 Изменение бронирования',
                        callback_data='change_booking',
                    )
                ],
            ])
        elif user.role == 'barista' and user.is_active is True:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    '➕ выбор смен выхода на работу',
                    callback_data='barista_slots'
                )],
                [InlineKeyboardButton(
                    '📊 просмотр своих смен',
                    callback_data='my_slots'
                )],
                [InlineKeyboardButton(
                    '✅ Подтверждение выхода на смену',
                    callback_data='going'
                )],
            ],
            )
        else:
            keyboard = None

        text = f'Добро пожаловать, {role_mapping[user.role]}!'

    # Проверяем тип обновления
    if update.message:
        await update.message.reply_text(text, reply_markup=keyboard)
    elif update.callback_query:
        await update.callback_query.message.reply_text(
            text,
            reply_markup=keyboard
        )
        await update.callback_query.answer()

    return ConversationHandler.END
