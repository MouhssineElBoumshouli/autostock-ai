from fastapi import FastAPI

from app.api import auth, health, setup, users
from app.origin_check import OriginCheckMiddleware

app = FastAPI(title="AutoStock AI", docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(OriginCheckMiddleware)

app.include_router(health.router)
app.include_router(setup.router)
app.include_router(auth.router)
app.include_router(users.router)
