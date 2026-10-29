import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.alerts.run import keep_raising_alerts
from app.api import (
    activity,
    alerts,
    ask,
    auth,
    backups,
    branches,
    exports,
    forecasts,
    health,
    imports,
    orders,
    parts,
    purchase_orders,
    settings,
    setup,
    shop_time,
    start_here,
    stock,
    suppliers,
    synonyms,
    today,
    users,
)
from app.config import IS_PRODUCTION, WEBSITE_DIR
from app.error_handling import add_error_handling
from app.origin_check import OriginCheckMiddleware
from app.stock_outs import keep_recording_stock_outs
from app.website import serve_website


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Work that runs while the server is up: saving stock-out days and stock history, daily alerts."""
    tasks = [asyncio.create_task(keep_recording_stock_outs()), asyncio.create_task(keep_raising_alerts())]
    yield
    for task in tasks:
        task.cancel()


# The API's developer pages (/api/docs) only exist while developing.
developer_pages = (
    {"docs_url": None, "redoc_url": None, "openapi_url": None}
    if IS_PRODUCTION
    else {"docs_url": "/api/docs", "openapi_url": "/api/openapi.json"}
)
app = FastAPI(title="AutoStock AI", lifespan=lifespan, **developer_pages)

app.add_middleware(OriginCheckMiddleware)
add_error_handling(app)

app.include_router(health.router)
app.include_router(shop_time.router)
app.include_router(setup.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(activity.router)
app.include_router(settings.router)
app.include_router(synonyms.router)
app.include_router(imports.router)
app.include_router(stock.router)
app.include_router(parts.router)
app.include_router(branches.router)
app.include_router(suppliers.router)
app.include_router(forecasts.router)
app.include_router(orders.router)
app.include_router(purchase_orders.router)
app.include_router(alerts.router)
app.include_router(today.router)
app.include_router(start_here.router)
app.include_router(ask.router)
app.include_router(backups.router)
app.include_router(exports.router)

# Last, so every /api address above wins over the website's pages.
if WEBSITE_DIR:
    serve_website(app, Path(WEBSITE_DIR))
