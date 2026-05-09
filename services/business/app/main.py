from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.company.routes import companies
from app.financial.routes import expenses, financial_summary, invoices
from app.inventory.routes import (
    inventory_categories,
    inventory_import_previews,
    inventory_items,
    inventory_levels,
    inventory_locations,
    inventory_movements,
    inventory_reports,
    inventory_search,
)
from app.partner.routes import partners
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
app.include_router(inventory_items.router)
app.include_router(inventory_categories.router)
app.include_router(inventory_locations.router)
app.include_router(inventory_movements.router)
app.include_router(inventory_levels.router)
app.include_router(inventory_search.router)
app.include_router(inventory_import_previews.router)
app.include_router(inventory_reports.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "business"}
