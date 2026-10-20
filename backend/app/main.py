import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.alerts.run import keep_raising_alerts
from app.api import (
    activity,
    alerts,
    ask,
    auth,
    branches,
    forecasts,
    health,
    imports,
    orders,
    parts,
    purchase_orders,
    settings,
    setup,
    stock,
    suppliers,
    synonyms,
    today,
    users,
)
from app.origin_check import OriginCheckMiddleware
from app.stock_outs import keep_recording_stock_outs


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Work that runs while the server is up: saving stock-out days and stock history, daily alerts."""
    tasks = [asyncio.create_task(keep_recording_stock_outs()), asyncio.create_task(keep_raising_alerts())]
    yield
    for task in tasks:
        task.cancel()


app = FastAPI(title="AutoStock AI", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)

app.add_middleware(OriginCheckMiddleware)

app.include_router(health.router)
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
app.include_router(ask.router)
