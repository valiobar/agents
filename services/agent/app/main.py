from contextlib import asynccontextmanager
import logging

import httpx
from fastapi import FastAPI

from app.config import settings
from app.routes import agents, conversations
from app.utils.db import close_db, connect_db


def _configure_logging() -> None:
    level = logging.INFO if settings.is_development else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(name)s: %(message)s",
    )
    logging.getLogger("app").setLevel(level)


_configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    app.state.business_http = httpx.AsyncClient(
        base_url=settings.business_service_url,
        timeout=settings.business_timeout_seconds,
    )
    try:
        yield
    finally:
        await app.state.business_http.aclose()
        close_db()


app = FastAPI(title="Agent Service", version="1.0.0", lifespan=lifespan)
app.include_router(agents.router)
app.include_router(conversations.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "agent"}
