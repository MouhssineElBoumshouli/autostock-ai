"""Blocks fake requests from other websites (CSRF).

Browsers always say which site a request comes from (the Origin header).
Any request that changes data must come from our own website: an address in APP_URL, or the very
address the request was sent to (a shop PC's address changes when the internet box restarts).
"""

from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import APP_URLS

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def is_our_website(origin: str | None, host: str | None) -> bool:
    if not origin:
        return False
    if origin.lower() in APP_URLS:
        return True
    # Same address = our own page. Still safe: the browser writes Origin itself and a page can't
    # change it, so another site's page always shows its own address, never ours. A script outside
    # a browser can write any Origin, but it has nobody's login cookie (only their browser does).
    return host is not None and urlsplit(origin).netloc.lower() == host.lower()


class OriginCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin, host = request.headers.get("origin"), request.headers.get("host")
        if request.method not in SAFE_METHODS and not is_our_website(origin, host):
            return JSONResponse({"detail": "This request did not come from the AutoStock website."}, 403)
        return await call_next(request)
