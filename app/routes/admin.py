from datetime import date, time, timedelta

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session, SessionLocal
from app.models import Booking, Schedule, ScheduleException

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

DAY_NAMES = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
SERVICE_DURATION = {
    "маникюр": 90,
    "педикюр": 120,
    "покрытие": 120,
    "гель-лак": 120,
    "наращивание": 180,
}


# ─── Dashboard ────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    today = date.today()
    async with SessionLocal() as s:
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        q = select(Booking).where(
            Booking.date >= week_start,
            Booking.date <= week_end,
            Booking.status == "confirmed",
        ).order_by(Booking.date, Booking.start_time)
        bookings = (await s.execute(q)).scalars().all()

    by_day: dict[date, list] = {}
    for b in bookings:
        by_day.setdefault(b.date, []).append(b)

    week = [(week_start + timedelta(days=i)) for i in range(7)]
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "today": today,
        "week": week,
        "by_day": by_day,
        "day_names": DAY_NAMES,
    })


# ─── Schedule ─────────────────────────────────────────────────────

@router.get("/schedule", response_class=HTMLResponse)
async def schedule_page(request: Request):
    today = date.today()
    async with SessionLocal() as s:
        q = select(Schedule).order_by(Schedule.day_of_week)
        schedule = (await s.execute(q)).scalars().all()

        week_start = today - timedelta(days=today.weekday())
        exceptions = {}
        for i in range(14):
            d = week_start + timedelta(days=i)
            qe = select(ScheduleException).where(ScheduleException.date == d)
            exc = (await s.execute(qe)).scalar_one_or_none()
            if exc:
                exceptions[d] = exc

    return templates.TemplateResponse("schedule.html", {
        "request": request,
        "schedule": schedule,
        "day_names": DAY_NAMES,
        "today": today,
        "week_start": week_start,
        "exceptions": exceptions,
        "timedelta": timedelta,
    })


@router.post("/schedule/update")
async def update_schedule(day_of_week: int = Form(...), start: str = Form(...), end: str = Form(...), active: bool = Form(False)):
    sh, sm = map(int, start.split(":"))
    eh, em = map(int, end.split(":"))
    async with SessionLocal() as s:
        q = select(Schedule).where(Schedule.day_of_week == day_of_week)
        sched = (await s.execute(q)).scalar_one_or_none()
        if sched:
            sched.start_time = time(sh, sm)
            sched.end_time = time(eh, em)
            sched.is_active = active
        else:
            s.add(Schedule(day_of_week=day_of_week, start_time=time(sh, sm), end_time=time(eh, em), is_active=active))
        await s.commit()
    return RedirectResponse("/admin/schedule", status_code=303)


@router.post("/schedule/exception")
async def add_exception(exc_date: str = Form(...), start: str = Form(""), end: str = Form(""), is_day_off: bool = Form(False), reason: str = Form("")):
    d = date.fromisoformat(exc_date)
    st = None
    et = None
    if start and end:
        sh, sm = map(int, start.split(":"))
        eh, em = map(int, end.split(":"))
        st = time(sh, sm)
        et = time(eh, em)
    async with SessionLocal() as s:
        q = select(ScheduleException).where(ScheduleException.date == d)
        exc = (await s.execute(q)).scalar_one_or_none()
        if exc:
            exc.start_time = st
            exc.end_time = et
            exc.is_day_off = is_day_off
            exc.reason = reason or None
        else:
            s.add(ScheduleException(date=d, start_time=st, end_time=et, is_day_off=is_day_off, reason=reason or None))
        await s.commit()
    return RedirectResponse("/admin/schedule", status_code=303)


@router.post("/schedule/exception/delete")
async def delete_exception(exc_date: str = Form(...)):
    d = date.fromisoformat(exc_date)
    async with SessionLocal() as s:
        q = select(ScheduleException).where(ScheduleException.date == d)
        exc = (await s.execute(q)).scalar_one_or_none()
        if exc:
            await s.delete(exc)
            await s.commit()
    return RedirectResponse("/admin/schedule", status_code=303)


# ─── Bookings ─────────────────────────────────────────────────────

@router.get("/bookings", response_class=HTMLResponse)
async def bookings_page(request: Request, status: str = "all"):
    async with SessionLocal() as s:
        q = select(Booking).order_by(Booking.date.desc(), Booking.start_time.desc())
        if status != "all":
            q = q.where(Booking.status == status)
        bookings = (await s.execute(q)).scalars().all()
    return templates.TemplateResponse("bookings.html", {
        "request": request,
        "bookings": bookings,
        "current_status": status,
    })


@router.post("/bookings/{booking_id}/status")
async def update_booking_status(booking_id: int, status: str = Form(...)):
    async with SessionLocal() as s:
        q = select(Booking).where(Booking.id == booking_id)
        booking = (await s.execute(q)).scalar_one_or_none()
        if booking:
            booking.status = status
            await s.commit()
    return RedirectResponse("/admin/bookings", status_code=303)


@router.post("/bookings/delete/{booking_id}")
async def delete_booking(booking_id: int):
    async with SessionLocal() as s:
        q = select(Booking).where(Booking.id == booking_id)
        booking = (await s.execute(q)).scalar_one_or_none()
        if booking:
            await s.delete(booking)
            await s.commit()
    return RedirectResponse("/admin/bookings", status_code=303)
