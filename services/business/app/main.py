from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routes import companies, expenses, financial_summary, invoices, partners
from app.utils.db import close_db, connect_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    close_db()


app = FastAPI(title="Business Service", version="1.0.0", lifespan=lifespan)
app.include_router(companies.router)
app.include_router(partners.router)
app.include_router(invoices.router)
app.include_router(expenses.router)
app.include_router(financial_summary.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "business"}
