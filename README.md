# nail-manager-web

Веб-приложение для записи к мастеру маникюра с AI-чат-ботом.

## Стек

- FastAPI + Uvicorn
- SQLite (aiosqlite)
- Jinja2
- Chat-бот (DeepSeek API через polza.ai)

## Функционал

- Клиентская часть: выбор услуги → календарь → слоты → форма записи
- AI чат-бот: консультация по услугам, ценам, записи
- Админ-панель: управление расписанием, просмотр записей, лидов

## Запуск (локально)

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

## Docker

```bash
docker compose up -d --build
```

Логи:
```bash
docker compose logs -f
```

## Деплой на VPS

```bash
ssh root@YOUR_VPS_IP
cd ~
git clone https://github.com/AlinaGntv/nail-manager-web.git nail-manager
cd nail-manager
```

Создать `.env`:
```bash
nano .env
```

Содержимое `.env`:
```
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=deepseek/deepseek-v4-flash
OPENAI_BASE_URL=https://polza.ai/api/v1

MASTER_NAME=Анна
WORK_HOURS=пн-сб 10:00-20:00
STUDIO_ADDRESS=г. Москва, ул. Примерная, 10, кабинет 5
MANICURE_PRICE=от 1500 руб.
PEDICURE_PRICE=от 2200 руб.
GEL_POLISH_PRICE=от 2000 руб.
NAIL_EXTENSION_PRICE=от 3500 руб.
```

Запуск:
```bash
docker compose up -d --build
```

Обновление:
```bash
cd ~/nail-manager
git pull
docker compose up -d --build
```

## Админ-панель

URL: `/admin/login`
Пароль: `nail2026`

## Порт

Приложение работает на порту `8001`.

## Структура проекта

```
app/
├── main.py          # FastAPI app, lifespan
├── auth.py          # Middleware авторизации админки
├── database.py      # SQLAlchemy async engine
├── models.py        # Модели: Schedule, Booking, Lead
├── routes/
│   ├── client.py    # Клиентские роуты + chat API
│   └── admin.py     # Админ роуты
├── templates/       # Jinja2 шаблоны
└── static/          # CSS, изображения
```
