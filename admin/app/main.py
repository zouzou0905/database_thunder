from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend's app package has priority over admin's app package for
# shared imports like `from app.core.security import ...` used in backend code.
_backend_root = Path(__file__).resolve().parent.parent.parent / "backend"
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from admin.app.core.auth import AuthRequired
from admin.app.core.config import get_admin_settings
from admin.app.pool import close_pool
from admin.app.routes import auth, dashboard, error_logs, users

settings = get_admin_settings()


def create_admin_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        max_age=12 * 3600,
        https_only=False,
    )

    app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

    # Redirect /admin to /admin/ so that url_for works with prefix
    @app.get("/admin", include_in_schema=False)
    def admin_index(request: Request):
        return RedirectResponse(url="/admin/", status_code=302)

    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(users.router)
    app.include_router(error_logs.router)

    @app.exception_handler(AuthRequired)
    def _redirect_to_login(_request: Request, _exc: AuthRequired):
        return RedirectResponse(url="/admin/login", status_code=302)

    @app.on_event("shutdown")
    def _shutdown() -> None:
        close_pool()

    return app


app = create_admin_app()
