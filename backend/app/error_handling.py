"""A bug the code didn't expect to crash: never a stack trace to the person using the app.

Every other problem (a wrong password, a missing field, no permission...) is already a plain
HTTPException with its own message. This only catches what's left: a genuine server-side mistake.
The reference code is the same thing in the response and in the log line, so someone reporting
"error AB12CD" can be found right away with a search of the server's own log.
"""

import logging
import secrets

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

log = logging.getLogger("autostock.error")


def reference_code() -> str:
    return secrets.token_hex(3).upper()


def add_error_handling(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        code = reference_code()
        log.exception("Unhandled error, reference %s, on %s %s", code, request.method, request.url.path)
        return JSONResponse({"detail": f"Something went wrong on our side. Reference: {code}"}, status_code=500)
