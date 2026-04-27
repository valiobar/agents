from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_invoice_service, get_user_id
from app.models.financial import InvoiceCreate, InvoiceFilters, InvoiceResponse, InvoiceStatus, InvoiceUpdate
from app.services.invoice_service import InvoiceService

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: InvoiceCreate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
):
    invoice = await service.create_invoice(user_id, payload)
    return InvoiceResponse.model_validate(invoice)


@router.get("", response_model=list[InvoiceResponse])
async def list_invoices(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
    company_id: str | None = None,
    partner_id: str | None = None,
    status_filter: Annotated[InvoiceStatus | None, Query(alias="status")] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    counterparty: str | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    category: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    filters = InvoiceFilters(
        company_id=company_id,
        partner_id=partner_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        counterparty=counterparty,
        amount_min=amount_min,
        amount_max=amount_max,
        category=category,
    )
    invoices = await service.list_invoices(user_id, filters, limit, offset)
    return [InvoiceResponse.model_validate(i) for i in invoices]


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
):
    invoice = await service.get_invoice(user_id, invoice_id)
    return InvoiceResponse.model_validate(invoice)


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: str,
    payload: InvoiceUpdate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
):
    invoice = await service.update_invoice(user_id, invoice_id, payload)
    return InvoiceResponse.model_validate(invoice)

