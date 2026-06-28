# nail-manager-web

Веб-приложение для записи к мастеру маникюра.

## Стек
- FastAPI + Uvicorn
- SQLite (aiosqlite)
- Jinja2
- Chat-бот (DeepSeek API)

## Запуск

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## Docker

```bash
docker compose up -d --build
```
