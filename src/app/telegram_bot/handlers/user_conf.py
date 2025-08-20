"""Модуль для подтверждения бариста."""
import logging
from enum import IntEnum
from typing import Optional, Sequence

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,  # оболочка для запуска и управления ботом
    CallbackQueryHandler,  # ловит нажатия на Inline-кнопки
    CommandHandler,  # ловит команды вида /user_conf
    ContextTypes,  # тип контекста (update + context)
    ConversationHandler,  # управляет многошаговыми диалогами
)

from app.core.db import async_session_maker
from app.crud.user_crud import crud_user
from app.exceptions.common_exceptions import NotFoundError, ValidationError
from app.schemas.user_schema import UserRead
from app.telegram_bot.commands import show_start_menu
from app.telegram_bot.handlers.base import BaseHandler

logger = logging.getLogger(__name__)


# Состояния диалога
class ConfirmStates(IntEnum):
    """Состояния диалога подтверждения бариста."""

    SELECTING = 0  # выбор бариста
    DECIDING  = 1  # принятие решения (да/нет)


# Callback-префиксы и паттерны
CB_APPROVE_PREFIX = 'approve_'                   # approve_<id> — «подтвердить»
CB_CANCEL         = 'cancel_'                    # cancel_        — «отмена»
CB_YES            = 'yes'                        # yes            — «да»
CB_NO             = 'no'                         # no             — «нет»
CB_BACK           = 'back'                       # back           — «назад»

APPROVE_PATTERN  = rf'^{CB_APPROVE_PREFIX}\d+$'  #  approve_123
CANCEL_PATTERN   = rf'^{CB_CANCEL}$'           #  cancel_
DECISION_PATTERN = (
    rf'^({CB_YES}|{CB_NO}|{CB_BACK})$'  # yes или no или back
)
# Тексты сообщений
MSG_SELECT_BARISTA = (
    '<b>Список бариста для подтверждения:</b>\n\n'
    'Выберите одного из списка ниже:'
)
MSG_NO_BARISTAS = (
    'ℹ️ <b>Нет неподтверждённых бариста</b>\n\n'
    'Все заявки уже рассмотрены.\n'
    'Можете вернуться в меню и заняться другими задачами ☕'
)
MSG_CANCELLED      = 'Операция отменена.'
MSG_CONFIRM_PROMPT = (
    '   <b>Подтвердить регистрацию бариста?</b>\n\n'
    '👤 <b>Имя:</b> {name}\n'
    '📞 <b>Телефон:</b> {phone}\n\n'
    'Пожалуйста, подтвердите или отклоните регистрацию этого бариста.'
)

MSG_SERVER_ERROR = 'Ошибка сервера. Попробуйте позже.'
MSG_SELECTION_ERROR = 'Ошибка при обработке выбора.'
MSG_NOT_FOUND = 'Бариста не найден. Возможно, он уже был удалён.'
MSG_UNKNOWN_ERROR = 'Внутренняя ошибка сервера. Попробуйте позже.'
MSG_BARISTA_APPROVED = '✅ Бариста {name} подтверждён.'
MSG_BARISTA_DECLINED = '❌ Бариста {name} отклонён.'

# Логирование
LOG_VALIDATION_ERROR = 'ValidationError: {message}'
LOG_NOT_FOUND_ERROR = 'NotFoundError: {message}'
LOG_UNKNOWN_ERROR = 'Неизвестная ошибка при подтверждении бариста: {exc}'

# Кнопки
LABEL_CANCEL = '❌ Отменить'
LABEL_YES    = '✅ Да'
LABEL_NO     = '❌ Нет'
LABEL_BACK   = '🔙 Назад'

SELF_TG_ID = "" #Для проверки уведомлений добавьте свой тг


# Клавиатура: список бариста
def build_selection_keyboard(
        baristas: Sequence[UserRead]
) -> InlineKeyboardMarkup:
    """InlineKeyboardMarkup со списком неподтверждённых бариста."""
    buttons = []
    for barista in baristas:
        buttons.append([
            InlineKeyboardButton(
                text=(
                    f'👤 {barista.name.strip()} • '
                    f'Телефон {barista.phone.strip()}'
                ),
                callback_data=f'{CB_APPROVE_PREFIX}{barista.id}'
            )
        ])
    buttons.append([InlineKeyboardButton(
        text=LABEL_CANCEL,
        callback_data=CB_CANCEL)])
    return InlineKeyboardMarkup(buttons)


# Клавиатура: решение «Да/Нет/Назад»
def build_decision_keyboard() -> InlineKeyboardMarkup:
    """InlineKeyboardMarkup с вариантами: Да, Нет и Назад."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(text=LABEL_YES, callback_data=CB_YES),
        InlineKeyboardButton(text=LABEL_NO, callback_data=CB_NO),
        InlineKeyboardButton(text=LABEL_BACK, callback_data=CB_BACK),
    ]])


class ConfirmBaristaHandler(BaseHandler):
    """Обработчик команды /user_conf — менеджер подтверждает бариста."""

    def __init__(self) -> None:
        """Инициализация ConfirmBaristaHandler."""
        self.states = ConfirmStates

    async def get_baristas_unconfirmed(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """/user_conf — показать список неподтверждённых бариста."""
        try:
            async with async_session_maker() as session:
                baristas = await crud_user.get_pending_baristas(session)

            if not baristas:
                if update.callback_query:
                    await update.callback_query.message.reply_text(
                        MSG_NO_BARISTAS, parse_mode='HTML')
                else:
                    await self.send_text_safely(update, MSG_NO_BARISTAS)
                await show_start_menu(update, context)
                return ConversationHandler.END

            keyboard = build_selection_keyboard(baristas)
            await self.send_text_safely(
                update,
                MSG_SELECT_BARISTA,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            return self.states.SELECTING

        except Exception as error:
            logger.exception(LOG_UNKNOWN_ERROR.format(exc=error))
            await self.send_text_safely(update, MSG_SERVER_ERROR)
            return await show_start_menu(update, context)

    async def selecting_barista(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Метод обработки выбора бариста или отмены."""
        query = update.callback_query
        await query.answer()
        data = query.data

        if data == CB_CANCEL:
            await self.send_text_safely(update, MSG_CANCELLED)
            return await show_start_menu(update, context)

        try:
            # извлекаем ID из коллбека: 'approve_123' → 123
            barista_id = int(data.replace(CB_APPROVE_PREFIX, ''))
            context.user_data['barista_id'] = barista_id

            # Получаем бариста из БД
            async with async_session_maker() as session:
                user = await crud_user.get_or_404(barista_id, session)
                context.user_data['barista_name'] = user.name
                context.user_data['barista_phone'] = user.phone

            await query.edit_message_text(
                MSG_CONFIRM_PROMPT.format(name=user.name, phone=user.phone),
                reply_markup=build_decision_keyboard(),
                parse_mode='HTML'
            )
            return self.states.DECIDING

        except Exception as error:
            logger.exception(LOG_UNKNOWN_ERROR.format(exc=error))
            await self.send_text_safely(update, MSG_SELECTION_ERROR)
            return await show_start_menu(update, context)

    def notification(self, decision: str, telegram_id: int) -> None:
        """Уведомление."""
        from app.tasks.activity_barista import activity_barista
        activity_barista.delay(
            status=decision,
            barista_tg_id=SELF_TG_ID#telegram_id),
        )

    async def processing_decision(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Метод обработки решения — «да», «нет» или «назад»."""
        query = update.callback_query
        await query.answer()
        decision = query.data
        barista_id = context.user_data.get('barista_id')

        if decision == CB_BACK:
            # вернуться к списку barista
            return await self.get_baristas_unconfirmed(update, context)
        try:
            async with async_session_maker() as session:
                user = await crud_user.get_or_404(barista_id, session)

                if decision == CB_YES:
                    await crud_user.activate_user(user, session)
                    text = MSG_BARISTA_APPROVED.format(name=user.name)
                    logger.info(MSG_BARISTA_APPROVED.format(name=user.name))
                else:
                    #await crud_user.deactivate_user(user, session)
                    # crud будет вечно выбрасывать ошибку
                    # так как баристы на подтверждение
                    # показываються если не активны
                    text = MSG_BARISTA_DECLINED.format(name=user.name)

                    logger.info(MSG_BARISTA_DECLINED.format(name=user.name))
                self.notification(
                    decision,
                    SELF_TG_ID)#user.telegram_id)

        except ValidationError as error:
            logger.warning(LOG_VALIDATION_ERROR.format(message=error.message))
            text = f'{error.message}'

        except NotFoundError as error:
            logger.warning(LOG_NOT_FOUND_ERROR.format(message=error.message))
            text = MSG_NOT_FOUND

        except Exception as error:
            logger.exception(LOG_UNKNOWN_ERROR.format(exc=error))
            text = MSG_UNKNOWN_ERROR

        await query.edit_message_text(text)
        return await show_start_menu(update, context)

    async def send_text_safely(
            self,
            update: Update,
            text: str,
            *,
            reply_markup: InlineKeyboardMarkup | None = None,
            parse_mode: Optional[str] = None
    ) -> None:
        """Метод универсальной отправки сообщения."""
        if update.message:
            await update.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode)
        elif update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode)

    def get_conversation_handler_baristas(self) -> ConversationHandler:
        """Собираем ConversationHandler для /user_conf."""
        return ConversationHandler(
            entry_points=[
                CommandHandler(
                    'user_conf',
                    self.get_baristas_unconfirmed),
                CallbackQueryHandler(
                    self.get_baristas_unconfirmed,
                    pattern="^user_conf$")
            ],
            states={
                self.states.SELECTING: [
                    CallbackQueryHandler(
                        self.selecting_barista,
                        pattern=APPROVE_PATTERN),
                    CallbackQueryHandler(
                        self.selecting_barista,
                        pattern=CANCEL_PATTERN),
                ],
                self.states.DECIDING: [
                    CallbackQueryHandler(
                        self.processing_decision,
                        pattern=DECISION_PATTERN),
                ],
            },
            fallbacks=[CommandHandler(
                'cancel',
                self.cancel)],
            per_message=False,
            allow_reentry=True,
        )

    def setup(self, app: Application) -> None:
        """Регистрируем хендлер в приложении."""
        app.add_handler(self.get_conversation_handler_baristas())
