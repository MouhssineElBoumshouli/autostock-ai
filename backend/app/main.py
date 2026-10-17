from fastapi import FastAPI

from app.api import health

app = FastAPI(title="AutoStock AI", docs_url="/api/docs", openapi_url="/api/openapi.json")

app.include_router(health.router)
