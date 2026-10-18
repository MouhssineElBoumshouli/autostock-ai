"""Blocks fake requests from other websites (CSRF).

Browsers always say which site a request comes from (the Origin header).
Any request that changes data must come from our own website.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import APP_URL

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class OriginCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in SAFE_METHODS and request.headers.get("origin") != APP_URL:
            return JSONResponse({"detail": "This request did not come from the AutoStock website."}, 403)
        return await call_next(request)
