from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

WORKSPACE_HEADER = "X-Workspace-Id"

# Endpoints exentos del header (públicos o previos a autenticación).
DEFAULT_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/api/v1/health",
    "/api/v1/auth/login",
    "/docs",
    "/redoc",
    "/openapi.json",
)


class WorkspaceIdMiddleware(BaseHTTPMiddleware):
    """Enforces ROG-A3: multi-tenant workspace_id en TODA request autenticada.

    Returns 400 si la request va a un endpoint no-exento y falta el header
    X-Workspace-Id. La validación de que el workspace del header coincida
    con el workspace del JWT se hace en auth.deps.get_current_user.
    """

    def __init__(
        self,
        app: ASGIApp,
        exempt_prefixes: Iterable[str] = DEFAULT_EXEMPT_PREFIXES,
    ) -> None:
        super().__init__(app)
        self._exempt_prefixes = tuple(exempt_prefixes)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable],
    ):
        # CORS preflight: el browser NUNCA envía X-Workspace-Id en OPTIONS.
        # Si bloqueamos aquí, el preflight muere antes de llegar al CORSMiddleware
        # y el browser ve un 400 sin headers Access-Control-Allow-Origin.
        # Pasamos el OPTIONS sin validar; el CORSMiddleware lo responde correctamente.
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(prefix) for prefix in self._exempt_prefixes):
            return await call_next(request)

        if not request.headers.get(WORKSPACE_HEADER):
            return JSONResponse(
                status_code=400,
                content={
                    "detail": f"Header {WORKSPACE_HEADER} requerido (ROG-A3)",
                    "code": "workspace_header_missing",
                },
            )
        return await call_next(request)
