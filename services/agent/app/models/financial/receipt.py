from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models.financial.financial import ExpenseCreate, ExpenseResponse
from app.models.financial.partner import PartnerResponse
from app.models.shared.document import DocumentResponse

ExpenseSourceDocumentType = Literal["invoice", "receipt"]
ExpenseDraftRequestSourceDocumentType = Literal["auto", "invoice", "receipt"]
ExpenseCategory = Literal[
    "office",
    "travel",
    "meals",
    "software",
    "rent",
    "utilities",
    "professional_services",
    "tax",
    "payroll",
    "other",
]
CurrencyCode = Literal["BGN", "EUR", "USD"]


class ExtractedExpenseItem(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Decimal = Field(ge=0)
    unit_label: str | None = Field(default=None, max_length=32)
    sku: str | None = Field(default=None, max_length=120)
    barcode: str | None = Field(default=None, max_length=120)
    vat_rate: Decimal | None = Field(default=None, ge=0, le=1)
    category: ExpenseCategory | None = None


class ExtractedPartnerDraft(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    registration_number: str | None = Field(default=None, max_length=64)
    vat_number: str | None = Field(default=None, max_length=64)
    city: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default="Bulgaria", max_length=120)
    address: str | None = Field(default=None, max_length=500)
    accountable_person: str | None = Field(default=None, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=64)
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class ExpenseDraft(BaseModel):
    counterparty: str = Field(min_length=1, max_length=200)
    expense_date: date
    amount: Decimal | None = Field(default=None, gt=0)
    currency: CurrencyCode = "EUR"
    category: ExpenseCategory
    description: str | None = Field(default=None, max_length=1000)
    deductible: bool = True
    deductible_rate: Decimal = Field(default=Decimal("1.0"), ge=0, le=1)
    source_document_type: ExpenseSourceDocumentType
    source_document_id: str
    source_document_number: str | None = Field(default=None, max_length=120)
    vendor_partner: ExtractedPartnerDraft | None = None
    items: list[ExtractedExpenseItem] | None = None
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class ExpenseDraftResponse(BaseModel):
    document: DocumentResponse
    draft: ExpenseDraft
    extracted_text: str | None = None
    provider: str
    model: str
    extracted_at: datetime


class PartnerUpsertResult(BaseModel):
    status: Literal["matched", "created", "skipped"]
    partner: PartnerResponse | None = None
    warnings: list[str] = Field(default_factory=list)


class ConfirmExtractedExpenseRequest(ExpenseCreate):
    confirmed: bool = False
    vendor_partner: ExtractedPartnerDraft | None = None


class ConfirmExtractedExpenseResponse(BaseModel):
    expense: ExpenseResponse
    vendor_partner: PartnerUpsertResult | None = None
