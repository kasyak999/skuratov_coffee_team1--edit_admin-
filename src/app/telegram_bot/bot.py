from telegram.ext import Application

from app.core.config import settings
from app.telegram_bot.handlers.admin import AdminHandler


def setup_handlers(application: Application) -> None:
    """Настройка всех обработчиков."""
    AdminHandler().setup_handlers(application)


def main() -> None:
    """Запуск бота."""
    application = Application.builder().token(settings.bot_token).build()

    setup_handlers(application)
    application.run_polling()


if __name__ == '__main__':
    main()
