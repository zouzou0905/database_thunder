"""Middleware that writes unhandled exceptions to the error_logs table."""
from __future__ import annotations

import traceback

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.pool import get_pool


class ErrorCaptureMiddleware(BaseHTTPMiddleware):
    """Catch unhandled exceptions and persist structured error data.

    Inserted early in the middleware stack so errors from any router or
    dependency are captured.  Only 5xx (unhandled) exceptions are logged;
    expected HTTPException (4xx) responses are passed through unchanged.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            await self._persist_error(request, exc)
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )

    async def _persist_error(self, request: Request, exc: Exception) -> None:
        try:
            body: str | None = None
            try:
                raw = await request.body()
                if raw:
                    body = raw.decode("utf-8", errors="replace")[:2000]
            except Exception:
                pass

            client_ip: str | None = None
            if request.client:
                client_ip = request.client.host

            user_agent: str | None = (request.headers.get("user-agent", "") or "")[:500]

            user_account: str | None = None
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                try:
                    from app.core.security import decode_access_token

                    payload = decode_access_token(auth_header[7:])
                    if payload:
                        user_account = payload.get("account")
                except Exception:
                    pass

            pool = get_pool()
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO error_logs
                            (level, source, endpoint, method, status_code,
                             message, traceback, request_body,
                             user_agent, client_ip, user_account)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        [
                            "ERROR",
                            "backend",
                            str(request.url.path),
                            request.method,
                            500,
                            str(exc)[:2000],
                            traceback.format_exc()[:10000],
                            body,
                            user_agent,
                            client_ip,
                            user_account,
                        ],
                    )
                conn.commit()
        except Exception:
            pass  # never let error logging itself cause failures
