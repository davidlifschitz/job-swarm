from __future__ import annotations

from jwt import InvalidTokenError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from ml_job_swarm.cloud_auth import is_cloud_service_request
from ml_job_swarm.supabase_auth import SupabaseAuthConfig, validate_access_token

ACCESS_TOKEN_COOKIE = "sb-access-token"
PUBLIC_PATHS = frozenset({"/healthz", "/auth/login", "/auth/callback", "/auth/logout"})
PUBLIC_PREFIXES = ("/static",)


def _extract_bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    if authorization.casefold().startswith("bearer "):
        token = authorization[7:].strip()
        return token or None
    cookie = request.cookies.get(ACCESS_TOKEN_COOKIE, "").strip()
    return cookie or None


def unauthorized_html_response(request: Request) -> Response:
    next_path = request.url.path
    if request.url.query:
        next_path = f"{next_path}?{request.url.query}"
    return RedirectResponse(url=f"/auth/login?next={next_path}", status_code=303)


def unauthorized_api_response() -> Response:
    from starlette.responses import JSONResponse

    return JSONResponse(status_code=401, content={"detail": "unauthorized"})


class SupabaseAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, config: SupabaseAuthConfig) -> None:
        super().__init__(app)
        self.config = config

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
            return await call_next(request)

        token = _extract_bearer_token(request)
        if not token:
            if path.startswith("/api/cloud/") and is_cloud_service_request(request):
                request.state.cloud_service_auth = True
                return await call_next(request)
            return (
                unauthorized_api_response()
                if path.startswith("/api/")
                else unauthorized_html_response(request)
            )

        try:
            claims = validate_access_token(token, self.config)
        except InvalidTokenError:
            return (
                unauthorized_api_response()
                if path.startswith("/api/")
                else unauthorized_html_response(request)
            )

        request.state.user_id = claims["sub"]
        request.state.auth_claims = claims
        return await call_next(request)