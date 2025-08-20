## файл .env

```
POSTGRES_USER=postgres_user
POSTGRES_PASSWORD=postgres_password
POSTGRES_DB=postgres_db
DB_HOST=localhost
POSTGRES_PORT=5433
BOT_TOKEN=
```

Команда для проверки версии Python (должна быть Python 3.12.10)

```
python --version
```

Запускаем докер перед началом

```
docker compose up --build -d
```

Команда для автоматического создания файла миграции

```
alembic revision --autogenerate -m "First migration"
```

Выполнить миграции

```
alembic upgrade head
```

Если миграции за одну команду не получается применить:
список всех ревизий и их зависимости:

```
python -m alembic history --verbose
```

миграции по одной:

```
python -m alembic upgrade хэш ревизиии
```

Управление БД через DBeaver

Создать соединение -> PostgreSQL ->

Хост: localhost
Порт: 5433
База данных: postgres_db
Пользователь: postgres_user
Пароль: postgres_password

-> Ок -> Базы данных -> django -> Схемы -> public -> Таблицы

Запуск API приложения, находясь в папке src/ выполните команду

```
uvicorn app.main:app --reload
```

Чтобы открыть swagger, откройте в браузере страничку по адресу

```
http://127.0.0.1:8000/docs
```

Для запуска бота
В телеграмм создать api token через бота @BotFather
скопировать токен и вставить в .env
В бд должен быть админ с вашим telegram_id
telegram_id можно узнать с помощью бота @userinfobot
Добавьте в .env BOT_TOKEN
Запустите bot.py

## Режим разработки

1. в конфиге `DEBUG` False
2. Запускаем файл docker-compose.yml
3. в конфиге `DEBUG` True
4. Запускаем проект

   ```
   uvicorn app.main:app --reload --port 8001
   ```

   и в отдельном терминале селери
   ```
   celery -A app.core.celery_worker worker --loglevel=info
   ```

   Запуск бота
   ```
   python -m app.telegram_bot.bot
   ```

Что бы посмотреть статус выполненых уведомлений:
`http://localhost:5555/flower/` логин и пароль из конфиг файла или env
```
superuser_password: str = 'admin123'  # пароль
superuser_telegram_id: str = '123456789' # логин
```

Телеграм бот **@qwertytes1t_bot**

https://skuratov-team1.rsateam.ru/ -API

https://skuratov-team1.rsateam.ru/flower/ - статус выполнения уведомлений