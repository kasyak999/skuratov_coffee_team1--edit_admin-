from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.telegram_bot.commands import cancel, show_start_menu

from .barista_slots import BaristaSlotsHandler
from .change_booking import ChangeBookingHandler
from .create_cafe import CreateCafeHandler
from .create_user import CreateUserHandler
from .creating_shifts import CreateShiftHandler
from .edit_cafe import EditCafeHandler
from .edit_shifts import EditShiftHandler
from .edit_user import EditUserHandler
from .employment_conf import EmpoymentConfirmHandler
from .going import GoingHandler
from .monitoring import MonitoringHandler
from .my_slots import MySlotsHandler
from .user_conf import ConfirmBaristaHandler


class AdminHandler:
    """Обработчик административных команд."""

    def __init__(self) -> None:
        """Инициализация."""
        self.create_user_handler = CreateUserHandler()
        self.create_cafe_handler = CreateCafeHandler()
        self.edit_cafe_handler = EditCafeHandler()
        self.create_shift_handler = CreateShiftHandler()
        self.edit_shift_handler = EditShiftHandler()
        self.employment_conf_handler = EmpoymentConfirmHandler()
        self.monitoring_handler = MonitoringHandler()
        self.user_conf_handler = ConfirmBaristaHandler()
        self.edit_user_handler = EditUserHandler()
        self.barista_slot_handler = BaristaSlotsHandler()
        self.my_slots_handler = MySlotsHandler()
        self.going_handler = GoingHandler()
        self.change_booking_handler = ChangeBookingHandler()

    async def start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Обработка команды /start."""
        await show_start_menu(update, context)

    def setup_handlers(self, application: Application) -> None:
        """Регистрирует обработчики."""
        self.create_user_handler.setup_handlers(application)
        self.create_cafe_handler.setup_handlers(application)
        self.edit_cafe_handler.setup_handlers(application)
        self.employment_conf_handler.setup_handlers(application)
        self.create_shift_handler.setup_handlers(application)
        self.edit_shift_handler.setup_handlers(application)
        self.user_conf_handler.setup(application)
        self.edit_user_handler.setup(application)
        self.monitoring_handler.setup_handlers(application)
        self.barista_slot_handler.setup_handlers(application)
        self.my_slots_handler.setup_handlers(application)
        self.change_booking_handler.setup_handlers(application)
        application.add_handler(CommandHandler('start', self.start))
        application.add_handler(CommandHandler('cancel', cancel))
        application.add_handler(self.going_handler.get_conversation_handler())
