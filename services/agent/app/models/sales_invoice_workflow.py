from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator

from app.models.financial import (
    CurrencyCode,
    InvoiceCreate,
    InvoicePartyInput,
    InvoiceResponse,
    PartnerMatchCandidate,
)
from app.models.inventory import InventorySearchMatch, StockLevel


class RequestedSalesInvoiceLine(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    query: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0)
    unit_label: str | None = Field(default=None, max_length=32)
    unit_price: Decimal | None = Field(default=None, ge=0)
    vat_rate: Decimal | None = Field(default=None, ge=0, le=1)
    category: str | None = Field(default=None, max_length=120)


class CreateSalesInvoiceInventoryPreviewRequest(BaseModel):
    partner_query: str | None = Field(default=None, max_length=200)
    recipient: InvoicePartyInput | None = None
    issue_date: date | None = None
    tax_event_date: date | None = None
    due_date: date | None = None
    currency: CurrencyCode = "EUR"
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[RequestedSalesInvoiceLine] = Field(min_length=1)

    @model_validator(mode="after")
    def partner_or_recipient_required(self) -> "CreateSalesInvoiceInventoryPreviewRequest":
        if not self.partner_query and not self.recipient:
            raise ValueError("partner_query or recipient is required")
        return self


class ResolvedSalesInvoiceInventoryLine(BaseModel):
    line_index: int = Field(ge=0)
    requested: RequestedSalesInvoiceLine
    selected_item_id: str | None = None
    selected_location_id: str | None = None
    candidates: list[InventorySearchMatch] = Field(default_factory=list)
    stock_levels: list[StockLevel] = Field(default_factory=list)
    available_quantity: Decimal | None = None
    warnings: list[str] = Field(default_factory=list)


class SalesInvoiceInventoryReviewResponse(BaseModel):
    type: Literal["sales_invoice_inventory_review"] = "sales_invoice_inventory_review"
    company_id: str
    partner_query: str | None = None
    recipient: InvoicePartyInput | None = None
    partner_candidates: list[PartnerMatchCandidate] = Field(default_factory=list)
    lines: list[ResolvedSalesInvoiceInventoryLine]
    warnings: list[str] = Field(default_factory=list)


class ConfirmedSalesInvoiceInventoryLine(BaseModel):
    line_index: int = Field(ge=0)
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0)
    unit_label: str = Field(min_length=1, max_length=32)
    unit_price: Decimal = Field(ge=0)
    vat_rate: Decimal = Field(ge=0, le=1)
    category: str | None = Field(default=None, max_length=120)
    inventory_item_id: str = Field(min_length=1)
    inventory_location_id: str = Field(min_length=1)
    stock_quantity: Decimal | None = Field(default=None, gt=0)


class ConfirmSalesInvoiceInventoryRequest(BaseModel):
    source_preview: CreateSalesInvoiceInventoryPreviewRequest
    selected_partner_id: str | None = None
    recipient: InvoicePartyInput | None = None
    lines: list[ConfirmedSalesInvoiceInventoryLine] = Field(min_length=1)


class SalesInvoiceReviewResponse(BaseModel):
    type: Literal["sales_invoice_review"] = "sales_invoice_review"
    company_id: str
    invoice_draft: InvoiceCreate
    inventory_warnings: list[str] = Field(default_factory=list)
    partner_warnings: list[str] = Field(default_factory=list)


class ConfirmSalesInvoiceRequest(BaseModel):
    invoice_draft: InvoiceCreate
    confirmed: bool = False


class SalesInvoiceCreatedResponse(BaseModel):
    type: Literal["sales_invoice_created"] = "sales_invoice_created"
    invoice: InvoiceResponse
    warnings: list[str] = Field(default_factory=list)


SalesInvoiceWorkflowResponse = Annotated[
    Union[
        SalesInvoiceInventoryReviewResponse,
        SalesInvoiceReviewResponse,
        SalesInvoiceCreatedResponse,
    ],
    Field(discriminator="type"),
]
