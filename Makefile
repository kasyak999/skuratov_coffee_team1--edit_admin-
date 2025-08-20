.PHONY: help install install-dev run test lint format clean db-init db-migrate db-upgrade db-downgrade db-reset docker-build docker-up docker-down run-bot run-api

# Переменные
PYTHON = python3
PIP = pip
SRC_DIR = src
VENV = venv
VENV_PYTHON = $(VENV)/bin/python
VENV_PIP = $(VENV)/bin/pip
VENV_ALEMBIC = $(VENV)/bin/alembic
VENV_UVICORN = $(VENV)/bin/uvicorn
VENV_RUFF = $(VENV)/bin/ruff
ALEMBIC = cd $(SRC_DIR) && ../$(VENV_ALEMBIC)

# Цвета для вывода
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[0;33m
BLUE = \033[0;34m
NC = \033[0m # No Color

help: ## Показать справку по командам
	@echo "$(BLUE)Доступные команды:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

install: ## Установить зависимости
	@echo "$(YELLOW)Установка зависимостей...$(NC)"
	$(VENV_PIP) install -r src/requirements.txt

install-dev: ## Установить зависимости для разработки
	@echo "$(YELLOW)Установка dev зависимостей...$(NC)"
	$(VENV_PIP) install -r requirements_style.txt
	$(VENV_PIP) install -r src/requirements.txt

lint: ## Запустить линтер
	@echo "$(YELLOW)Запуск линтера...$(NC)"
	$(VENV_RUFF) check $(SRC_DIR)

format: ## Отформатировать код
	@echo "$(YELLOW)Форматирование кода...$(NC)"
	$(VENV_RUFF) format $(SRC_DIR)
	$(VENV_RUFF) check --fix $(SRC_DIR)

test: ## Запустить тесты
	@echo "$(YELLOW)Запуск тестов...$(NC)"
	cd $(SRC_DIR) && $(PYTHON) -m pytest

clean: ## Очистить временные файлы
	@echo "$(YELLOW)Очистка временных файлов...$(NC)"
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type d -name ".ruff_cache" -delete

# Команды для работы с базой данных
db-init: ## Инициализировать Alembic (только при первом запуске)
	@echo "$(YELLOW)Инициализация Alembic...$(NC)"
	$(ALEMBIC) init alembic

db-migrate: ## Создать новую миграцию
	@echo "$(YELLOW)Создание новой миграции...$(NC)"
	@read -p "Введите название миграции: " name; \
	$(ALEMBIC) revision --autogenerate -m "$$name"

db-upgrade: ## Применить все миграции
	@echo "$(YELLOW)Применение миграций...$(NC)"
	$(ALEMBIC) upgrade head

db-downgrade: ## Откатить последнюю миграцию
	@echo "$(YELLOW)Откат последней миграции...$(NC)"
	$(ALEMBIC) downgrade -1

db-reset: ## Сбросить базу данных и применить все миграции
	@echo "$(RED)ВНИМАНИЕ: Это удалит все данные в базе!$(NC)"
	@read -p "Вы уверены? (y/N): " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		echo "$(YELLOW)Сброс базы данных...$(NC)"; \
		$(ALEMBIC) downgrade base; \
		$(ALEMBIC) upgrade head; \
		echo "$(GREEN)База данных сброшена и миграции применены$(NC)"; \
	else \
		echo "$(BLUE)Операция отменена$(NC)"; \
	fi

db-history: ## Показать историю миграций
	@echo "$(YELLOW)История миграций:$(NC)"
	$(ALEMBIC) history

db-current: ## Показать текущую версию схемы
	@echo "$(YELLOW)Текущая версия схемы:$(NC)"
	$(ALEMBIC) current

db-stamp: ## Отметить базу данных как находящуюся на определенной ревизии
	@echo "$(YELLOW)Отметка базы данных...$(NC)"
	@read -p "Введите ревизию: " revision; \
	$(ALEMBIC) stamp "$$revision"

# Команды для Docker
docker-build: ## Собрать Docker образы
	@echo "$(YELLOW)Сборка Docker образов...$(NC)"
	docker-compose build

docker-up: ## Запустить контейнеры
	@echo "$(YELLOW)Запуск контейнеров...$(NC)"
	docker-compose up -d

docker-down: ## Остановить контейнеры
	@echo "$(YELLOW)Остановка контейнеров...$(NC)"
	docker-compose down

docker-logs: ## Показать логи контейнеров
	@echo "$(YELLOW)Логи контейнеров:$(NC)"
	docker-compose logs -f

# Команды для разработки
dev-setup: install-dev db-upgrade ## Настроить среду разработки
	@echo "$(GREEN)Среда разработки настроена!$(NC)"

dev-reset: clean db-reset ## Полный сброс среды разработки
	@echo "$(GREEN)Среда разработки сброшена!$(NC)"

# Команда для автоматического применения всех миграций по порядку
db-migrate-all: ## Применить все миграции автоматически
	@echo "$(YELLOW)Проверка статуса миграций...$(NC)"
	@if $(ALEMBIC) current | grep -q "head"; then \
		echo "$(GREEN)Все миграции уже применены$(NC)"; \
	else \
		echo "$(YELLOW)Применение всех миграций...$(NC)"; \
		$(ALEMBIC) upgrade head; \
		echo "$(GREEN)Все миграции применены!$(NC)"; \
	fi

# Команды для запуска приложений
run: ## Запустить приложение (алиас для run-api)
	@echo "$(YELLOW)Запуск FastAPI сервера...$(NC)"
	cd $(SRC_DIR) && ../$(VENV_PYTHON) -m app.main

run-api: ## Запустить FastAPI сервер
	@echo "$(YELLOW)Запуск FastAPI сервера на http://127.0.0.1:8002$(NC)"
	@echo "$(BLUE)Документация доступна на http://127.0.0.1:8002/docs$(NC)"
	cd $(SRC_DIR) && ../$(VENV_UVICORN) app.main:app --reload --host 127.0.0.1 --port 8002

run-bot: ## Запустить Telegram бота
	@echo "$(YELLOW)Запуск Telegram бота...$(NC)"
	@echo "$(BLUE)Убедитесь, что BOT_TOKEN указан в .env файле$(NC)"
	cd $(SRC_DIR) && ../$(VENV_PYTHON) -m app.telegram_bot.bot

run-both: ## Запустить API и бота в фоновом режиме
	@echo "$(YELLOW)Запуск FastAPI сервера в фоновом режиме...$(NC)"
	cd $(SRC_DIR) && ../$(VENV_UVICORN) app.main:app --host 127.0.0.1 --port 8002 > ../logs/api.log 2>&1 &
	@echo "$(YELLOW)Запуск Telegram бота...$(NC)"
	cd $(SRC_DIR) && ../$(VENV_PYTHON) -m app.telegram_bot.bot

stop-services: ## Остановить все сервисы
	@echo "$(YELLOW)Остановка сервисов...$(NC)"
	pkill -f "uvicorn app.main:app" || true
	pkill -f "python.*telegram_bot.bot" || true
	@echo "$(GREEN)Сервисы остановлены$(NC)"