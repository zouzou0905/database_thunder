from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from backend.app.core.config import load_env_file


@dataclass(frozen=True)
class AdminSettings:
    app_name: str
    database_url: str
    session_secret: str
    templates_dir: Path
    static_dir: Path


def get_admin_settings() -> AdminSettings:
    load_env_file()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL not set")

    admin_root = Path(__file__).resolve().parent.parent  # admin/app/

    return AdminSettings(
        app_name=os.environ.get("APP_NAME", "Keyword Trends") + " Admin",
        database_url=database_url,
        session_secret=os.environ.get(
            "ADMIN_SESSION_SECRET", "admin-dev-change-me"
        ),
        templates_dir=admin_root / "templates",
        static_dir=admin_root / "static",
    )
