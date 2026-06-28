import os
import re
import time as _time
import httpx
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Booking, Schedule, ScheduleException


# ─── Chat Rate Limiter ─────────────────────────────────────

class RateLimiter:
    def __init__(self, max_per_minute: int = 10, cooldown_sec: float = 2.0):
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._last_msg: dict[str, float] = {}
        self._blocked: dict[str, float] = {}
        self.max_per_minute = max_per_minute
        self.cooldown_sec = cooldown_sec

    def _get_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def check(self, request: Request) -> str | None:
        ip = self._get_ip(request)
        now = _time.time()

        if ip in self._blocked and now < self._blocked[ip]:
            return "Слишком много запросов. Подождите немного."

        self._hits[ip] = [t for t in self._hits[ip] if now - t < 60]
        if len(self._hits[ip]) >= self.max_per_minute:
            self._blocked[ip] = now + 120
            return "Превышен лимит сообщений. Попробуйте через 2 минуты."

        if ip in self._last_msg and now - self._last_msg[ip] < self.cooldown_sec:
            return "Слишком быстро! Подождите пару секунд."

        self._hits[ip].append(now)
        self._last_msg[ip] = now
        return None

limiter = RateLimiter(max_per_minute=10, cooldown_sec=2.0)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

SERVICES = [
    {"name": "Маникюр", "duration": 90, "price": "от 1500 руб.", "icon": "💅", "desc": "Классический или аппаратный маникюр"},
    {"name": "Педикюр", "duration": 120, "price": "от 2200 руб.", "icon": "🦶", "desc": "Комфортный педикюр с заботой"},
    {"name": "Покрытие гель-лак", "duration": 120, "price": "от 2000 руб.", "icon": "✨", "desc": "Стойкое покрытие до 3 недель"},
    {"name": "Наращивание", "duration": 180, "price": "от 3500 руб.", "icon": "💅", "desc": "Любая длина и форма"},
]

RUSSIAN_HOLIDAYS = [(1,1),(1,2),(1,3),(1,4),(1,5),(1,6),(1,7),(1,8),(2,23),(3,8),(5,1),(5,9),(6,12),(11,4)]


def _is_holiday(d: date) -> bool:
    return (d.month, d.day) in RUSSIAN_HOLIDAYS


async def _get_free_slots(target_date: date, duration_minutes: int) -> list[dict]:
    """Calculate free slots for a date."""
    if _is_holiday(target_date):
        return []

    async with SessionLocal() as s:
        exc = (await s.execute(
            select(ScheduleException).where(ScheduleException.date == target_date)
        )).scalar_one_or_none()

        if exc and exc.is_day_off:
            return []

        if exc and exc.start_time and exc.end_time:
            day_start, day_end = exc.start_time, exc.end_time
        else:
            sched = (await s.execute(
                select(Schedule).where(Schedule.day_of_week == target_date.weekday(), Schedule.is_active == True)
            )).scalar_one_or_none()
            if not sched:
                return []
            day_start, day_end = sched.start_time, sched.end_time

        bookings = (await s.execute(
            select(Booking).where(Booking.date == target_date, Booking.status == "confirmed")
        )).scalars().all()

    duration = timedelta(minutes=duration_minutes)
    buffer = timedelta(minutes=30)
    slots = []
    current = datetime.combine(target_date, day_start)
    end_dt = datetime.combine(target_date, day_end)

    while current + duration <= end_dt:
        slot_end = current + duration
        is_free = all(
            not (b.start_time < slot_end.time() and b.end_time > current.time())
            for b in bookings
        )
        if is_free:
            slots.append({
                "start": current.time(),
                "end": slot_end.time(),
                "label": f"{current.strftime('%H:%M')}–{slot_end.strftime('%H:%M')}",
            })
        current += duration + buffer

    return slots


@router.get("/", response_class=HTMLResponse)
async def book_service(request: Request):
    return templates.TemplateResponse("client/index.html", {
        "request": request,
        "services": SERVICES,
    })


@router.get("/book/{service_name}", response_class=HTMLResponse)
async def book_date(request: Request, service_name: str):
    service = next((s for s in SERVICES if s["name"] == service_name), None)
    if not service:
        return RedirectResponse("/", status_code=303)

    today = date.today()
    days = []
    for i in range(14):
        d = today + timedelta(days=i)
        if d.weekday() < 7:
            days.append(d)

    return templates.TemplateResponse("client/calendar.html", {
        "request": request,
        "service": service,
        "days": days,
        "today": today,
    })


@router.get("/book/{service_name}/slots", response_class=HTMLResponse)
async def book_slots(request: Request, service_name: str, date_str: str):
    service = next((s for s in SERVICES if s["name"] == service_name), None)
    if not service:
        return RedirectResponse("/", status_code=303)

    target_date = date.fromisoformat(date_str)
    slots = await _get_free_slots(target_date, service["duration"])

    return templates.TemplateResponse("client/slots.html", {
        "request": request,
        "service": service,
        "target_date": target_date,
        "slots": slots,
    })


@router.get("/book/{service_name}/form", response_class=HTMLResponse)
async def book_form(request: Request, service_name: str, date_str: str, time_str: str):
    service = next((s for s in SERVICES if s["name"] == service_name), None)
    if not service:
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse("client/form.html", {
        "request": request,
        "service": service,
        "date_str": date_str,
        "time_str": time_str,
    })


@router.post("/book/confirm")
async def book_confirm(
    service: str = Form(...),
    date_str: str = Form(...),
    time_str: str = Form(...),
    client_name: str = Form(...),
    client_phone: str = Form(...),
):
    target_date = date.fromisoformat(date_str)
    sh, sm = map(int, time_str.split(":"))
    start = time(sh, sm)

    svc = next((s for s in SERVICES if s["name"] == service), None)
    duration = timedelta(minutes=svc["duration"]) if svc else timedelta(hours=1, minutes=30)
    end_dt = datetime.combine(target_date, start) + duration
    end = end_dt.time()

    async with SessionLocal() as s:
        s.add(Booking(
            client_name=client_name,
            client_phone=client_phone,
            service=service,
            date=target_date,
            start_time=start,
            end_time=end,
            status="confirmed",
        ))
        await s.commit()

    return RedirectResponse(f"/book/thank-you?name={client_name}&service={service}&date_str={date_str}&time_str={time_str}", status_code=303)


@router.get("/book/thank-you", response_class=HTMLResponse)
async def thank_you(request: Request, name: str = "", service: str = "", date_str: str = "", time_str: str = ""):
    return templates.TemplateResponse("client/thankyou.html", {
        "request": request,
        "name": name,
        "service": service,
        "date_str": date_str,
        "time_str": time_str,
    })


# ─── Chat API ──────────────────────────────────────────────

CHAT_SYSTEM = """Ты — виртуальный помощник Анны, мастера маникюра и педикюра в студии в Москве.
Отвечай кратко, тепло и по делу. Помоги выбрать услугу, подсказать цены и записаться.
Работай на русском языке.

Услуги и цены:
- Маникюр — от 1500 руб., 90 мин
- Педикюр — от 2200 руб., 120 мин
- Покрытие гель-лак — от 2000 руб., 120 мин
- Наращивание — от 3500 руб., 180 мин

Адрес: г. Москва, ул. Примерная, 10, кабинет 5
Режим: пн-сб 10:00-20:00

Клиент может записаться через сайт: http://localhost:8001"""

MAX_MSG_LEN = 500
MAX_CONTEXT = 6

SUSPICIOUS = re.compile(r"(<script|javascript:|onerror=|onclick=|DROP\s+TABLE|;\s*ls|;\s*cat\s)", re.I)


class ChatRequest(BaseModel):
    message: str
    context: list[dict] = []


@router.post("/api/chat")
async def chat_api(req: ChatRequest, request: Request):
    err = limiter.check(request)
    if err:
        return JSONResponse({"reply": err, "rate_limited": True}, status_code=429)

    msg = req.message.strip()
    if not msg:
        return JSONResponse({"reply": "Пустое сообщение."})
    if len(msg) > MAX_MSG_LEN:
        return JSONResponse({"reply": f"Слишком длинное сообщение. Максимум {MAX_MSG_LEN} символов."})
    if SUSPICIOUS.search(msg):
        return JSONResponse({"reply": "Сообщение не прошло фильтр."})

    ctx = req.context[-MAX_CONTEXT:]

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://polza.ai/api/v1")
    model = os.getenv("OPENAI_MODEL", "deepseek/deepseek-v4-flash")

    messages = [{"role": "system", "content": CHAT_SYSTEM}]
    messages.extend(ctx)
    messages.append({"role": "user", "content": msg})

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": messages, "max_tokens": 500, "temperature": 0.7},
            )
            data = resp.json()
            reply = data["choices"][0]["message"]["content"]
            return JSONResponse({"reply": reply})
    except Exception:
        return JSONResponse({"reply": "Извините, временно недоступно. Попробуйте позже."})
