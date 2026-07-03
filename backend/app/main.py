from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.clipboard import router as clipboard_router
from app.api.exclusions import router as exclusions_router
from app.api.exports import router as exports_router
from app.api.health import router as health_router
from app.api.holiday_lexicon import router as holiday_lexicon_router
from app.api.holiday_tags import router as holiday_tags_router
from app.api.keyword_compare import router as keyword_compare_router
from app.api.meta import router as meta_router
from app.api.product_selection import router as product_selection_router
from app.api.users import router as users_router
from app.core.config import get_settings
from app.error_capture import ErrorCaptureMiddleware
from app.pool import close_pool, get_pool

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    @app.on_event("startup")
    def _startup() -> None:
        get_pool()  # eagerly initialise the pool

    @app.on_event("shutdown")
    def _shutdown() -> None:
        close_pool()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(ErrorCaptureMiddleware)
    app.include_router(auth_router, prefix="/api")
    app.include_router(clipboard_router, prefix="/api")
    app.include_router(exclusions_router, prefix="/api")
    app.include_router(exports_router, prefix="/api")
    app.include_router(health_router, prefix="/api")
    app.include_router(holiday_lexicon_router, prefix="/api")
    app.include_router(holiday_tags_router, prefix="/api")
    app.include_router(keyword_compare_router, prefix="/api")
    app.include_router(meta_router, prefix="/api")
    app.include_router(product_selection_router, prefix="/api")
    app.include_router(users_router, prefix="/api")
    return app


app = create_app()
