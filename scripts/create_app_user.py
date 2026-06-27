from __future__ import annotations

import argparse
from getpass import getpass

import psycopg

from common import get_database_url


def hash_password(password: str) -> str:
    # Keep this script independent from backend import paths.
    import base64
    import hashlib
    import secrets

    iterations = 260_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    salt_text = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    digest_text = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"pbkdf2_sha256${iterations}${salt_text}${digest_text}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update an application user.")
    parser.add_argument("--account", required=True, help="Login account, not email-dependent.")
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--role", default="operator", choices=["admin", "manager", "operator", "viewer"])
    parser.add_argument("--password", help="Omit to prompt securely.")
    args = parser.parse_args()

    password = args.password or getpass("Password: ")
    password_hash = hash_password(password)
    database_url = get_database_url()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app_users (account, display_name, password_hash, role)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (account)
                DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    password_hash = EXCLUDED.password_hash,
                    role = EXCLUDED.role,
                    is_active = TRUE,
                    updated_at = NOW()
                RETURNING id, account, display_name, role
                """,
                [args.account, args.display_name, password_hash, args.role],
            )
            user = cur.fetchone()
        conn.commit()

    print(f"User ready: id={user[0]} account={user[1]} display_name={user[2]} role={user[3]}")


if __name__ == "__main__":
    main()
