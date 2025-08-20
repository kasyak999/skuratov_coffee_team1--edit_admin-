"""Модуль для работы со слотами (сменами) баристы."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

from app.core.constants import MIN_HOURS_BETWEEN_SHIFTS
from app.core.db import async_session_maker
from app.crud.cafe_crud import cafe_crud
from app.crud.reservation_crud import reservation_crud
from app.crud.user_crud import crud_user
from app.models.cafe import Cafe
from app.models.reservation import Reservation, Status
from app.models.shift import Shift
from app.telegram_bot.commands import cancel, show_start_menu

logger = logging.getLogger(__name__)

# Состояния для работы со слотами
SELECT_SHIFT, CONFIRM_SHIFT = range(2)


class BaristaSlotsHandler:
    """Обработчик работы со слотами для баристы."""

    async def show_available_slots(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Показывает доступные слоты для бронирования."""
        try:
            if update.message:
                msg_target = update.message
            elif update.callback_query:
                await update.callback_query.answer()
                msg_target = update.callback_query.message
            else:
                logger.error("Неизвестный тип update")
                return await show_start_menu(update, context)

            user_id = update.effective_user.id
            async with async_session_maker() as session:
                user = await crud_user.get_by_telegram_id(user_id, session)
                if not user or not user.cafe_id:
                    await msg_target.reply_text(
                        "Вы не привязаны к кафе. Обратитесь к администратору.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return await show_start_menu(update, context)

                cafe = await cafe_crud.get(user.cafe_id, session)
                if not cafe:
                    await msg_target.reply_text(
                        "Ваше кафе не найдено. Обратитесь к администратору.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return await show_start_menu(update, context)

                shifts = await self._get_available_shifts(
                    user_id, cafe.city, session)

                if not shifts:
                    await msg_target.reply_text(
                        "На текущую и следующую неделю нет "
                        "доступных смен в вашем городе.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return await show_start_menu(update, context)

                shifts_by_date = self._group_shifts_by_date(shifts)
                message_text = "📅 Доступные смены для бронирования:\n\n"
                buttons = []

                for date, date_shifts in shifts_by_date.items():
                    message_text += f"<b>{date.strftime('%d.%m.%Y')}</b>:\n"
                    for shift in date_shifts:
                        cafe_name = shift.cafe.name if shift.cafe else "кафе"
                        message_text += (
                            f"🕒 {shift.start_time.strftime('%H:%M')}-"
                            f"{shift.end_time.strftime('%H:%M')} "
                            f"📍 {cafe_name}\n"
                            f"   👥 Свободных мест: "
                            f"{shift.barista_count - len(shift.reservations)}"
                        )
                        button_text = (
                            f"{date.strftime('%d.%m')} "
                            f"{shift.start_time.strftime('%H:%M')}-"
                            f"{shift.end_time.strftime('%H:%M')} "
                            f"{cafe_name}"
                        )
                        buttons.append([
                            InlineKeyboardButton(
                                button_text,
                                callback_data=f"select_shift_{shift.id}",
                            )
                        ])

                keyboard = InlineKeyboardMarkup(buttons)
                await msg_target.reply_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )

            return SELECT_SHIFT
        except Exception as e:
            logger.error(f"Error in show_available_slots: {e}")
            await update.message.reply_text(
                "Произошла ошибка. Пожалуйста, попробуйте позже."
            )
            return await show_start_menu(update, context)

    async def _get_available_shifts(
        self, user_id: int, city: str, session: AsyncSession
    ) -> List[Shift]:
        """Возвращает список доступных смен для баристы."""
        try:
            now = datetime.now()
            next_week = now + timedelta(days=14)

            stmt = (
                select(Shift)
                .join(Shift.cafe)
                .where(Cafe.city == city)
                .where(Shift.start_time >= now)
                .where(Shift.start_time <= next_week)
                .options(
                    selectinload(Shift.reservations),
                    selectinload(Shift.cafe)
                )
                .order_by(Shift.start_time)
            )

            shifts = (await session.execute(stmt)).scalars().all()

            user = await crud_user.get_by_telegram_id(user_id, session)
            if not user:
                return []

            reservations_stmt = (
                select(Reservation)
                .where(Reservation.barista_id == user.id)
                .where(Reservation.status.in_(
                    [Status.RESERVED, Status.ATTENDED])
                ))
            reservations = (await session.execute(
                reservations_stmt)).scalars().all()
            booked_shift_ids = {r.shift_id for r in reservations}

            available_shifts = []
            for shift in shifts:
                if shift.id in booked_shift_ids:
                    continue

                reserved_count = sum(
                    1 for r in shift.reservations
                    if r.status in [Status.RESERVED, Status.ATTENDED]
                )
                if reserved_count < shift.barista_count:
                    available_shifts.append(shift)

            return available_shifts
        except Exception as e:
            logger.error(f"Error in _get_available_shifts: {e}")
            raise

    def _group_shifts_by_date(self, shifts: List[Shift]) -> dict:
        """Группирует смены по датам."""
        shifts_by_date = {}
        for shift in shifts:
            date = shift.start_time.date()
            if date not in shifts_by_date:
                shifts_by_date[date] = []
            shifts_by_date[date].append(shift)
        return shifts_by_date

    async def _check_time_conflicts(
        self, user_id: int, shift: Shift, session: AsyncSession
    ) -> Optional[Tuple[Shift, str, str]]:
        """Проверяет временные конфликты с другими сменами баристы."""
        try:
            user = await crud_user.get_by_telegram_id(user_id, session)
            if not user:
                return None

            reservations = await reservation_crud.get_by_user(
                barista_id=user.id,
                session=session,
            )

            for reservation in reservations:
                if reservation.status == Status.CANCELLED:
                    continue

                await session.refresh(reservation, ['shift'])
                other_shift = reservation.shift

                shift_start = shift.start_time
                shift_end = shift.end_time
                other_start = other_shift.start_time
                other_end = other_shift.end_time

                logger.debug(
                    f"Checking shift {shift.id} ({shift_start}-{shift_end})"
                )
                logger.debug(
                    f"Against shift {other_shift.id} "
                    f"({other_start}-{other_end})"
                )

                if (shift_start < other_end) and (shift_end > other_start):
                    logger.debug("Found time overlap conflict")
                    return (other_shift, "overlap", "пересекающаяся")

                time_between_shifts = min(
                    abs((shift_start - other_end).total_seconds()),
                    abs((other_start - shift_end).total_seconds())
                )
                logger.debug(
                    f"Time between shifts: {time_between_shifts/3600} hours"
                )

                if time_between_shifts < MIN_HOURS_BETWEEN_SHIFTS * 3600:
                    if shift_start > other_end:
                        logger.debug("Found minimum time conflict (before)")
                        return (other_shift, "before", "предыдущая")
                    logger.debug("Found minimum time conflict (after)")
                    return (other_shift, "after", "следующая")

            return None
        except Exception as e:
            logger.error(f"Error in _check_time_conflicts: {e}")
            raise

    async def select_shift(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает выбор конкретной смены."""
        try:
            query = update.callback_query
            await query.answer()

            shift_id = int(query.data.replace("select_shift_", ""))
            context.user_data["selected_shift_id"] = shift_id

            async with async_session_maker() as session:
                stmt = (
                    select(Shift)
                    .where(Shift.id == shift_id)
                    .options(
                        selectinload(Shift.cafe),
                        selectinload(Shift.reservations).selectinload(
                            Reservation.shift)
                    )
                )
                result = await session.execute(stmt)
                shift = result.scalar_one_or_none()

                if not shift:
                    await query.edit_message_text("Смена не найдена.")
                    return await show_start_menu(update, context)

                user_id = update.effective_user.id
                time_conflic = await self._check_time_conflicts(
                    user_id, shift, session
                )

                if time_conflic:
                    conflict_shift, conflict_type, conflict_name = time_conflic
                    conflict_cafe_stmt = select(Cafe).where(
                        Cafe.id == conflict_shift.cafe_id)
                    conflict_cafe = (
                        await session.execute(conflict_cafe_stmt)
                    ).scalar_one_or_none()
                    cafe_name = (
                        conflict_cafe.name if conflict_cafe
                        else "Неизвестное кафе"
                    )

                    if conflict_type == "overlap":
                        message = (
                            "⚠️ Невозможно забронировать смену:\n"
                            "У вас уже есть пересекающаяся по времени смена:\n"
                            f"📅 {conflict_shift.start_time.strftime(
                                '%d.%m.%Y %H:%M')}-"
                            f"{conflict_shift.end_time.strftime('%H:%M')}\n"
                            f"📍 {cafe_name}\n\n"
                            "Вы не можете работать в двух кафе одновременно!"
                        )
                    else:
                        message = (
                            "⚠️ Невозможно забронировать смену:\n"
                            f"У вас уже есть {conflict_name} смена:\n"
                            f"📅 {conflict_shift.start_time.strftime(
                                '%d.%m.%Y %H:%M')}-"
                            f"{conflict_shift.end_time.strftime('%H:%M')}\n"
                            f"📍 {cafe_name}\n\n"
                            f"Минимальное время между сменами: "
                            f"{MIN_HOURS_BETWEEN_SHIFTS} часов."
                        )
                    await query.edit_message_text(message)
                    return await show_start_menu(update, context)

                reserved_count = sum(
                    1 for r in shift.reservations
                    if r.status in [Status.RESERVED, Status.ATTENDED]
                )
                free_slots = shift.barista_count - reserved_count

                cafe_name = shift.cafe.name if shift.cafe else "кафе"
                message = (
                    "ℹ️ Информация о выбранной смене:\n\n"
                    f"📅 Дата: {shift.start_time.strftime('%d.%m.%Y')}\n"
                    f"🕒 Время: {shift.start_time.strftime('%H:%M')}-"
                    f"{shift.end_time.strftime('%H:%M')}\n"
                    f"📍 Кафе: {cafe_name}\n"
                    f"🏙️ Город: {shift.cafe.city}\n"
                    f"📌 Адрес: {shift.cafe.address}\n"
                    f"👥 Свободных мест: {free_slots}/{shift.barista_count}\n"
                    "Подтвердите бронирование:"
                )

                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "✅ Подтвердить", callback_data="confirm_shift"),
                        InlineKeyboardButton(
                            "❌ Отменить", callback_data="cancel"),
                    ]
                ])

                await query.edit_message_text(
                    message,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )

            return CONFIRM_SHIFT
        except Exception as e:
            logger.error(f"Error in select_shift: {e}")
            await update.callback_query.message.reply_text(
                "Произошла ошибка. Пожалуйста, попробуйте позже."
            )
            return await show_start_menu(update, context)

    async def confirm_shift_reservation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Подтверждает бронирование смены."""
        try:
            query = update.callback_query
            await query.answer()

            shift_id = context.user_data.get("selected_shift_id")
            if not shift_id:
                await query.edit_message_text("Ошибка: смена не выбрана.")
                return await show_start_menu(update, context)

            user_id = update.effective_user.id
            async with async_session_maker() as session:
                user = await crud_user.get_by_telegram_id(user_id, session)
                if not user:
                    await query.edit_message_text(
                        "Пользователь не найден.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return await show_start_menu(update, context)

                stmt = (
                    select(Shift)
                    .where(Shift.id == shift_id)
                    .options(
                        selectinload(Shift.reservations),
                        selectinload(Shift.cafe)
                    )
                )
                shift = (await session.execute(stmt)).scalar_one_or_none()

                if not shift:
                    await query.edit_message_text("Смена не найдена.")
                    return await show_start_menu(update, context)

                reserved_count = sum(
                    1 for r in shift.reservations
                    if r.status in [Status.RESERVED, Status.ATTENDED]
                )
                if reserved_count >= shift.barista_count:
                    await query.edit_message_text(
                        "К сожалению, все места на эту смену уже заняты."
                    )
                    return await show_start_menu(update, context)

                time_conflict = await self._check_time_conflicts(
                    user_id, shift, session
                )
                if time_conflict:
                    await query.edit_message_text(
                        "Обнаружен конфликт времени с другой сменой. "
                        "Бронирование невозможно."
                    )
                    return await show_start_menu(update, context)

                # Создаем бронирование
                await reservation_crud.create_with_status(
                    barista_id=user.id,
                    shift_id=shift_id,
                    status=Status.RESERVED,
                    session=session,
                )
                await session.commit()

                cafe_name = shift.cafe.name if shift.cafe else "кафе"
                message = (
                    "✅ Вы успешно забронировали смену:\n\n"
                    f"📅 Дата: {shift.start_time.strftime('%d.%m.%Y')}\n"
                    f"🕒 Время: {shift.start_time.strftime('%H:%M')}-"
                    f"{shift.end_time.strftime('%H:%M')}\n"
                    f"📍 Кафе: {cafe_name}\n"
                    f"🏙️ Город: {shift.cafe.city}\n"
                    f"📌 Адрес: {shift.cafe.address}\n\n"
                )

                # Удаляем клавиатуру при редактировании сообщения
                await query.edit_message_text(
                    message,
                    parse_mode="HTML",
                    reply_markup=None
                )

            context.user_data.clear()
            return await show_start_menu(update, context)
        except Exception as e:
            logger.error(f"Error in confirm_shift_reservation: {e}")
            await query.edit_message_text(
                "Произошла ошибка при бронировании. "
                "Пожалуйста, попробуйте позже.",
                reply_markup=ReplyKeyboardRemove()
            )
            return await show_start_menu(update, context)

    def get_conversation_handler(self) -> ConversationHandler:
        """Возвращает обработчик диалога работы со слотами."""
        return ConversationHandler(
            entry_points=[
                CommandHandler("slots", self.show_available_slots),
                CallbackQueryHandler(
                    self.show_available_slots,
                    pattern='^barista_slots$'
                ),
            ],
            states={
                SELECT_SHIFT: [
                    CallbackQueryHandler(
                        self.select_shift, pattern="^select_shift_"
                    ),
                    CallbackQueryHandler(
                        cancel,
                        pattern="^cancel$",
                    ),
                ],
                CONFIRM_SHIFT: [
                    CallbackQueryHandler(
                        self.confirm_shift_reservation,
                        pattern="^confirm_shift$",
                    ),
                    CallbackQueryHandler(
                        cancel,
                        pattern="^cancel$",
                    ),
                ],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )

    def setup_handlers(self, application: Application) -> None:
        """Регистрирует обработчики команд."""
        application.add_handler(self.get_conversation_handler())
