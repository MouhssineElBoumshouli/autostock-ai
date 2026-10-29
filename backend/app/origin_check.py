"""Blocks fake requests from other websites (CSRF).

Browsers always say which site a request comes from (the Origin header).
Any request that changes data must come from our own website, at one of its addresses (APP_URL).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import APP_URLS

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def is_our_website(origin: str | None) -> bool:
    return origin is not None and origin.lower() in APP_URLS


class OriginCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in SAFE_METHODS and not is_our_website(request.headers.get("origin")):
            return JSONResponse({"detail": "This request did not come from the AutoStock website."}, 403)
        return await call_next(request)
