from datetime import timedelta
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

ADMIN_PASSWORD = "nail2026"
COOKIE_NAME = "nail_admin_auth"
COOKIE_MAX_AGE = 86400 * 7  # 7 days


class AdminAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if not path.startswith("/admin"):
            return await call_next(request)

        if path == "/admin/login":
            return await call_next(request)

        if path.startswith("/admin/login"):
            return await call_next(request)

        auth_cookie = request.cookies.get(COOKIE_NAME)
        if auth_cookie == ADMIN_PASSWORD:
            return await call_next(request)

        if request.method == "POST":
            form = await request.form()
            password = form.get("password", "")
            if password == ADMIN_PASSWORD:
                response = RedirectResponse("/admin/", status_code=303)
                response.set_cookie(
                    COOKIE_NAME, ADMIN_PASSWORD,
                    max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax",
                )
                return response

        return RedirectResponse("/admin/login", status_code=303)
