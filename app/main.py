from contextlib import asynccontextmanager
from datetime import time
from pathlib import Path
from typing import AsyncIterator

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Schedule
from app.auth import AdminAuthMiddleware, ADMIN_PASSWORD, COOKIE_NAME, COOKIE_MAX_AGE

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_db()
    await _seed_schedule()
    yield


app = FastAPI(title="Nail Manager", lifespan=lifespan)
app.add_middleware(AdminAuthMiddleware)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

from app.routes import admin, client  # noqa
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(client.router, tags=["client"])


@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/admin/login")
async def admin_login_post(request: Request, password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        response = RedirectResponse("/admin/", status_code=303)
        response.set_cookie(
            COOKIE_NAME, ADMIN_PASSWORD,
            max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax",
        )
        return response
    return templates.TemplateResponse("login.html", {
        "request": request, "error": "Неверный пароль"
    })


async def _seed_schedule():
    from sqlalchemy import select as sel
    async with SessionLocal() as session:
        result = await session.execute(sel(Schedule))
        if result.scalars().first():
            return
        for day in range(6):
            session.add(Schedule(
                day_of_week=day,
                start_time=time(10, 0),
                end_time=time(20, 0),
                is_active=True,
            ))
        await session.commit()
