from fastapi import FastAPI

from app.api import activity, auth, health, imports, parts, settings, setup, stock, users
from app.origin_check import OriginCheckMiddleware

app = FastAPI(title="AutoStock AI", docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(OriginCheckMiddleware)

app.include_router(health.router)
app.include_router(setup.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(activity.router)
app.include_router(settings.router)
app.include_router(imports.router)
app.include_router(stock.router)
app.include_router(parts.router)
