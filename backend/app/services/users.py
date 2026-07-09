from __future__ import annotations

from typing import Any

import psycopg

from app.core.security import hash_password, verify_password


PUBLIC_USER_COLUMNS = """
    id,
    account,
    display_name,
    role,
    is_active,
    created_at,
    updated_at
"""


def get_user_by_account(conn: psycopg.Connection, account: str) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {PUBLIC_USER_COLUMNS}, password_hash
            FROM app_users
            WHERE lower(account) = lower(%s)
            LIMIT 1
            """,
            [account],
        )
        return cur.fetchone()


def get_user_by_id(conn: psycopg.Connection, user_id: int) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {PUBLIC_USER_COLUMNS}
            FROM app_users
            WHERE id = %s
            LIMIT 1
            """,
            [user_id],
        )
        return cur.fetchone()


def authenticate_user(conn: psycopg.Connection, account: str, password: str) -> dict[str, Any] | None:
    user = get_user_by_account(conn, account)
    if not user or not user["is_active"]:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {key: value for key, value in user.items() if key != "password_hash"}


def list_users(conn: psycopg.Connection) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {PUBLIC_USER_COLUMNS}
            FROM app_users
            ORDER BY is_active DESC, role, account
            """
        )
        return cur.fetchall()


def create_user(
    conn: psycopg.Connection,
    *,
    account: str,
    display_name: str,
    password: str,
    role: str,
    is_active: bool = True,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO app_users (
                account,
                display_name,
                password_hash,
                role,
                is_active
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING {PUBLIC_USER_COLUMNS}
            """,
            [account.strip().lower(), display_name, hash_password(password), role, is_active],
        )
        user = cur.fetchone()
    conn.commit()
    return user


def update_user(
    conn: psycopg.Connection,
    user_id: int,
    *,
    display_name: str | None = None,
    password: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> dict[str, Any] | None:
    assignments: list[str] = []
    params: list[Any] = []
    if display_name is not None:
        assignments.append("display_name = %s")
        params.append(display_name)
    if password is not None:
        assignments.append("password_hash = %s")
        params.append(hash_password(password))
    if role is not None:
        assignments.append("role = %s")
        params.append(role)
    if is_active is not None:
        assignments.append("is_active = %s")
        params.append(is_active)
    assignments.append("updated_at = NOW()")
    params.append(user_id)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE app_users
            SET {", ".join(assignments)}
            WHERE id = %s
            RETURNING {PUBLIC_USER_COLUMNS}
            """,
            params,
        )
        user = cur.fetchone()
    conn.commit()
    return user


def delete_user(conn: psycopg.Connection, user_id: int) -> bool:
    """Delete an application user and user-owned operational records."""
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM app_users WHERE id = %s", [user_id])
        if not cur.fetchone():
            return False

        cur.execute("DELETE FROM keyword_selection_states WHERE owner_user_id = %s", [user_id])
        cur.execute("DELETE FROM keyword_selection_notes WHERE user_id = %s", [user_id])
        cur.execute("DELETE FROM shared_clipboard_items WHERE created_by = %s", [user_id])
        cur.execute("UPDATE login_history SET user_id = NULL WHERE user_id = %s", [user_id])
        cur.execute("DELETE FROM app_users WHERE id = %s", [user_id])
    conn.commit()
    return True
