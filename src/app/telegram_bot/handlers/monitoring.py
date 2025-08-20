"""Модуль мониторинга загруженности смен."""

import logging
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
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
from app.crud.cafe_crud import cafe_crud
from app.crud.shift_crud import shift_crud
from app.crud.user_crud import crud_user
from app.models.reservation import Status as ReservationStatus
from app.models.shift import Shift
from app.telegram_bot.commands import show_start_menu

logger = logging.getLogger(__name__)

# Состояния для мониторинга
SELECT_CAFE, SELECT_DATE, SHOW_RESULTS = range(3)


class MonitoringHandler:
    """Обработчик мониторинга загруженности смен."""

    def __init__(self) -> None:
        """Инициализация обработчика."""
        self.shift_crud = shift_crud

    async def monitoring_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Начало команды мониторинга."""
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            message = query.message
            telegram_id = query.from_user.id
        else:
            message = update.message
            telegram_id = update.effective_user.id

        async with async_session_maker() as session:
            # 1. Получаем пользователя по telegram_id
            user = await crud_user.get_by_telegram_id(telegram_id, session)
            if not user:
                await message.reply_text("❌ Пользователь не найден")
                return await show_start_menu(update, context)

            # 2. Получаем кафе по внутреннему user.id (manager_id)
            cafes = await cafe_crud.get_by_manager(user.id, session)

            logger.info(
                f"Checking cafes for manager with internal ID: {user.id}")
            logger.info(f"Found cafes: {cafes}")

            if not cafes:
                await message.reply_text(
                    "❌ У вас нет кафе для мониторинга. "
                    "Обратитесь к администратору."
                )
                return await show_start_menu(update, context)

            if len(cafes) == 1:
                # Если только одно кафе, сразу переходим к выбору даты
                context.user_data['selected_cafe_id'] = cafes[0].id
                return await self.select_date(update, context)

            # Если несколько кафе - предлагаем выбрать
            keyboard = [
                [InlineKeyboardButton(
                    cafe.name,
                    callback_data=f"select_cafe_{cafe.id}"
                )]
                for cafe in cafes
            ]
            keyboard.append([
                InlineKeyboardButton(
                    "❌ Отменить",
                    callback_data="cancel_monitoring"
                )
            ])

            if update.callback_query:
                await message.edit_text(
                    "🏪 Выберите кафе для мониторинга:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await message.reply_text(
                    "🏪 Выберите кафе для мониторинга:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

            return SELECT_CAFE

    async def select_cafe(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обработка выбора кафе."""
        query = update.callback_query
        await query.answer()

        if query.data.startswith("select_cafe_"):
            cafe_id = int(query.data.split("_")[-1])
            context.user_data['selected_cafe_id'] = cafe_id

            # Удаляем сообщение с выбором кафе
            await query.delete_message()

            return await self.select_date(update, context)

        return await show_start_menu(update, context)

    async def select_date(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Выбор даты для мониторинга."""
        # Предлагаем клавиатуру с датами (сегодня и предыдущие дни)
        today = date.today()
        dates = [
            date(today.year, today.month, today.day + 2),
            date(today.year, today.month, today.day + 1),
            today,
            date(today.year, today.month, today.day - 1),
            date(today.year, today.month, today.day - 2),
        ]

        keyboard = [
            [InlineKeyboardButton(
                d.strftime("%d.%m.%Y"),
                callback_data=f"select_date_{d.strftime('%Y-%m-%d')}"
            )]
            for d in dates
        ]
        keyboard.append([
            InlineKeyboardButton(
                "❌ Отменить",
                callback_data="cancel_monitoring"
            )
        ])

        if update.callback_query:
            await update.callback_query.edit_message_text(
                "📅 Выберите дату для мониторинга:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                "📅 Выберите дату для мониторинга:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        return SELECT_DATE

    async def show_monitoring_results(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Показывает результаты мониторинга."""
        query = update.callback_query
        await query.answer()

        if query.data.startswith("select_date_"):
            selected_date = query.data.split("_")[-1]
            cafe_id = context.user_data['selected_cafe_id']

            async with async_session_maker() as session:
                # Получаем все смены на выбранную дату
                start_datetime = datetime.strptime(selected_date, "%Y-%m-%d")
                end_datetime = datetime.combine(
                    start_datetime.date(),
                    datetime.max.time()
                )

                shifts = await shift_crud.get_multi(
                    session=session,
                    cafe_id=cafe_id,
                    start_time=start_datetime,
                    end_time=end_datetime
                )

                if not shifts:
                    await query.edit_message_text(
                        f"ℹ️ На {selected_date} смен не найдено.",
                        reply_markup=None
                    )
                    return await show_start_menu(update, context)

                # Формируем отчет по сменам
                report = []
                for shift in shifts:
                    status = await self._get_shift_status(shift, session)
                    report.append(
                        f"🕒 {shift.start_time.strftime('%H:%M')}-"
                        f"{shift.end_time.strftime('%H:%M')}\n"
                        f"   👥 Необходимо бариста: {shift.barista_count}\n"
                        f"   📊 Статус: {status}\n"
                    )

                cafe = await cafe_crud.get(cafe_id, session)
                message = (
                    f"📊 Мониторинг загруженности смен\n"
                    f"🏪 Кафе: {cafe.name}\n"
                    f"📅 Дата: {selected_date}\n\n" +
                    "\n".join(report)
                )

                await query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            "🔄 Выбрать другую дату",
                            callback_data="select_another_date"
                        )
                    ]])
                )

                return SHOW_RESULTS

        return await show_start_menu(update, context)

    async def _get_shift_status(
            self,
            shift: Shift,
            session: AsyncSession
    ) -> str:
        """Определяет статус смены на основе резерваций."""
        await session.refresh(shift, ['reservations'])

        if not shift.reservations:
            return "🟢 Свободна\nнет резерваций"

        status_labels = {
            "RESERVED": "забронировано",
            "ONCONFIRM": "на подтверждении",
            "ATTENDED": "присутствовал",
            "CANCELLED": "отменено"
        }

        status_counts = {}
        for r in shift.reservations:
            status_name = r.status.name
            status_counts[status_name] = status_counts.get(status_name, 0) + 1

        status_stats = "\n" + "\n".join(
            f"{status_labels[status]}: {count}"
            for status, count in sorted(status_counts.items())
        )

        active_reservations = [
            r for r in shift.reservations
            if r.status in [ReservationStatus.RESERVED,
                            ReservationStatus.ONCONFIRM,
                            ReservationStatus.ATTENDED,
                            ]
        ]
        active_count = len(active_reservations)

        if active_count >= shift.barista_count:
            return f"🔴 Заполнена{status_stats}"
        if active_count > 0:
            return (f"🟡 Частично занята {active_count}/{shift.barista_count})"
                    f"{status_stats}")
        return f"🟢 Свободна{status_stats}"

    async def select_another_date(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обработчик выбора другой даты."""
        query = update.callback_query
        await query.answer()
        return await self.select_date(update, context)

    async def cancel_monitoring(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отмена мониторинга."""
        query = update.callback_query
        await query.answer()

        await query.edit_message_text(
            "Мониторинг отменен",
            reply_markup=None
        )

        if 'selected_cafe_id' in context.user_data:
            del context.user_data['selected_cafe_id']

        return await show_start_menu(update, context)

    def get_conversation_handler(self) -> ConversationHandler:
        """Возвращает обработчик диалога мониторинга."""
        return ConversationHandler(
            entry_points=[
                CommandHandler("monitoring", self.monitoring_start),
                CallbackQueryHandler(self.monitoring_start,
                                     pattern="^monitoring$")
            ],
            states={
                SELECT_CAFE: [
                    CallbackQueryHandler(
                        self.select_cafe,
                        pattern="^select_cafe_"
                    ),
                    CallbackQueryHandler(
                        self.cancel_monitoring,
                        pattern="^cancel_monitoring$"
                    )
                ],
                SELECT_DATE: [
                    CallbackQueryHandler(
                        self.show_monitoring_results,
                        pattern="^select_date_"
                    ),
                    CallbackQueryHandler(
                        self.cancel_monitoring,
                        pattern="^cancel_monitoring$"
                    )
                ],
                SHOW_RESULTS: [
                    CallbackQueryHandler(
                        self.select_another_date,
                        pattern="^select_another_date$"
                    )
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_monitoring)],
            per_message=False
        )

    def setup_handlers(self, application: Application) -> None:
        """Регистрирует обработчики команд."""
        application.add_handler(self.get_conversation_handler())
