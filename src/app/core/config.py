
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки подключения к базе данных."""

    app_title: str = 'Управление сменами в кофейнях'
    description: str = 'API для управления сменами бариста в сети кофеен'
    version: str = '1.0.0'

    postgres_user: str = 'django_user'
    postgres_password: str = 'mysecretpassword'
    postgres_db: str = 'django'
    postgres_port: str = '5433'
    redis_pass: str = 'mystrongpassword'

    bot_token: str

    secret: str = 'SECRET'
    superuser_password: str = 'admin123'
    superuser_telegram_id: str = '123456789'
    superuser_phone: str = '+79991234567'
    superuser_name: str = 'Администратор'

    # False - работа в докере
    # True - режим для разработки
    DEBUG: bool = False

    @property
    def database_url(self) -> str:
        """Формирует URL подключения к базе."""
        db = (
            'postgresql+asyncpg://'
            f'{self.postgres_user}:{self.postgres_password}@'
        )
        db_host = f'localhost:{self.postgres_port}' if self.DEBUG else 'db'
        return db + db_host + f'/{self.postgres_db}'

    class Config:
        """Конфигурация Pydantic Settings."""

        env_file = '../.env'


settings = Settings()
