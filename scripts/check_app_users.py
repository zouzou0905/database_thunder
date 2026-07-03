from __future__ import annotations

import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.core.security import verify_password  # noqa: E402
from common import get_database_url  # noqa: E402


def main() -> None:
    database_url = get_database_url()
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, account, display_name, role, is_active, password_hash
                FROM app_users
                ORDER BY id
                """
            )
            for row in cur.fetchall():
                print(
                    "id={id} account={account} display_name={display_name} "
                    "role={role} active={active} admin_123456_valid={valid}".format(
                        id=row[0],
                        account=row[1],
                        display_name=row[2],
                        role=row[3],
                        active=row[4],
                        valid=verify_password("admin_123456", row[5]),
                    )
                )


if __name__ == "__main__":
    main()
