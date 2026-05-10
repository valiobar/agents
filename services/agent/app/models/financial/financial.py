from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from app.models.common import ListEnvelope

CurrencyCode = Literal["BGN", "EUR", "USD"]
InvoiceStatus = Literal["draft", "sent", "paid", "overdue", "cancelled"]
PaymentMethod = Literal["bank_transfer", "cash", "card", "other"]
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
ExpenseSourceDocumentType = Literal["invoice", "receipt"]
SummaryGroupBy = Literal["category", "counterparty", "month"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MoneyModel(BaseModel):
    @field_serializer("*", when_used="json")
    def serialize_decimal(self, value, _info):
        if isinstance(value, Decimal):
            return str(value)
        return value


class InvoicePartyInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    registration_number: str = Field(min_length=1, max_length=64)
    vat_number: str | None = Field(default=None, max_length=64)
    city: str = Field(min_length=1, max_length=120)
    country: str = Field(default="Bulgaria", min_length=1, max_length=120)
    address: str = Field(min_length=1, max_length=500)
    accountable_person: str = Field(min_length=1, max_length=200)
    logo_data_url: str | None = None


class InvoicePartySnapshot(InvoicePartyInput):
    email: str | None = None
    phone: str | None = None

    @classmethod
    def from_partner(cls, partner: object) -> "InvoicePartySnapshot":
        data = partner.model_dump(mode="python") if hasattr(partner, "model_dump") else dict(partner)  # type: ignore[arg-type]
        return cls(
            name=data["name"],
            registration_number=data["registration_number"],
            vat_number=data.get("vat_number"),
            city=data["city"],
            country=data.get("country") or "Bulgaria",
            address=data["address"],
            accountable_person=data["accountable_person"],
            email=data.get("email"),
            phone=data.get("phone"),
            logo_data_url=data.get("logo_data_url"),
        )


class InvoiceItemCreate(MoneyModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0)
    unit_label: str = Field(default="бр.", min_length=1, max_length=32)
    unit_price: Decimal = Field(ge=0)
    vat_rate: Decimal = Field(default=Decimal("0.20"), ge=0, le=1)
    category: str | None = Field(default=None, max_length=120)
    inventory_item_id: str | None = Field(default=None, max_length=64)
    inventory_location_id: str | None = Field(default=None, max_length=64)
    stock_quantity: Decimal | None = Field(default=None, gt=0)


class InvoiceItem(InvoiceItemCreate):
    subtotal: Decimal
    vat_amount: Decimal
    total: Decimal


class InvoiceCreate(MoneyModel):
    company_id: str = Field(min_length=1, max_length=64)
    partner_id: str | None = Field(default=None, max_length=64)
    recipient: InvoicePartyInput | None = None
    counterparty: str | None = Field(default=None, max_length=200)
    issue_date: date
    tax_event_date: date
    due_date: date | None = None
    place_of_supply: str = Field(default="Bulgaria", min_length=1, max_length=120)
    payment_method: PaymentMethod = "bank_transfer"
    bank_name: str | None = Field(default=None, max_length=120)
    bank_bic: str | None = Field(default=None, max_length=32)
    bank_iban: str | None = Field(default=None, max_length=64)
    amount_in_words: str | None = Field(default=None, max_length=500)
    currency: CurrencyCode = "EUR"
    items: list[InvoiceItemCreate] = Field(min_length=1)
    vat_reason: str | None = Field(default=None, max_length=500)
    recipient_name: str | None = Field(default=None, max_length=200)
    compiler_name: str | None = Field(default=None, max_length=200)
    original_label: str = Field(default="ОРИГИНАЛ", max_length=64)
    status: InvoiceStatus = "draft"
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def due_date_not_before_issue_date(self):
        if self.due_date and self.due_date < self.issue_date:
            raise ValueError("due_date cannot be before issue_date")
        if self.tax_event_date < self.issue_date:
            raise ValueError("tax_event_date cannot be before issue_date")
        if not self.partner_id and not self.recipient:
            raise ValueError("partner_id or recipient is required")
        return self


class InvoiceResponse(MoneyModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    company_id: str | None = None
    partner_id: str | None = None
    invoice_number: str
    counterparty: str | None = None
    supplier_snapshot: InvoicePartySnapshot | None = None
    recipient_snapshot: InvoicePartySnapshot | None = None
    issue_date: date
    tax_event_date: date | None = None
    due_date: date | None
    place_of_supply: str | None = None
    payment_method: PaymentMethod | None = None
    bank_name: str | None = None
    bank_bic: str | None = None
    bank_iban: str | None = None
    amount_in_words: str | None = None
    currency: CurrencyCode
    items: list[InvoiceItem]
    subtotal: Decimal
    vat_total: Decimal
    total: Decimal
    status: InvoiceStatus
    vat_reason: str | None = None
    recipient_name: str | None = None
    compiler_name: str | None = None
    original_label: str | None = None
    notes: str | None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class InvoiceFilters(BaseModel):
    company_id: str | None = None
    partner_id: str | None = None
    status: InvoiceStatus | None = None
    date_from: date | None = None
    date_to: date | None = None
    counterparty: str | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    category: str | None = None


class ExpenseItemCreate(MoneyModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    category: ExpenseCategory | None = None


class ExpenseItem(ExpenseItemCreate):
    total: Decimal


class ExpenseCreate(MoneyModel):
    company_id: str = Field(min_length=1, max_length=64)
    partner_id: str | None = Field(default=None, max_length=64)
    counterparty: str = Field(min_length=1, max_length=200)
    expense_date: date
    amount: Decimal | None = Field(default=None, gt=0)
    currency: CurrencyCode = "EUR"
    category: ExpenseCategory
    description: str | None = Field(default=None, max_length=1000)
    deductible: bool = True
    deductible_rate: Decimal = Field(default=Decimal("1.0"), ge=0, le=1)
    source_document_type: ExpenseSourceDocumentType | None = None
    source_document_id: str | None = None
    source_document_number: str | None = Field(default=None, max_length=120)
    items: list[ExpenseItemCreate] | None = None

    @model_validator(mode="after")
    def amount_or_items_required(self):
        if self.amount is None and not self.items:
            raise ValueError("Either amount or items must be provided")
        return self


class ExpenseResponse(ExpenseCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    amount: Decimal
    items: list[ExpenseItem] | None = None
    deductible_amount: Decimal
    created_at: datetime
    updated_at: datetime


class ExpenseFilters(BaseModel):
    company_id: str
    partner_id: str | None = None
    category: ExpenseCategory | None = None
    counterparty: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    deductible: bool | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None


class FinancialSummaryRequest(BaseModel):
    company_id: str | None = None
    partner_id: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    group_by: SummaryGroupBy | None = None
    include_invoices: bool = True
    include_expenses: bool = True


class FinancialSummaryCurrencyTotals(MoneyModel):
    currency: CurrencyCode
    invoice_total: Decimal = Decimal("0")
    expense_total: Decimal = Decimal("0")
    deductible_expense_total: Decimal = Decimal("0")
    net_total: Decimal = Decimal("0")


class FinancialSummaryBucket(MoneyModel):
    key: str
    invoice_total: Decimal = Decimal("0")
    expense_total: Decimal = Decimal("0")
    deductible_expense_total: Decimal = Decimal("0")
    totals_by_currency: list[FinancialSummaryCurrencyTotals] = Field(default_factory=list)


class FinancialSummaryResponse(MoneyModel):
    currency: CurrencyCode = "EUR"
    exchange_rates_to_eur: dict[str, Decimal] = Field(default_factory=dict)
    invoice_total: Decimal
    expense_total: Decimal
    deductible_expense_total: Decimal
    net_total: Decimal
    buckets: list[FinancialSummaryBucket] = Field(default_factory=list)
    totals_by_currency: list[FinancialSummaryCurrencyTotals] = Field(default_factory=list)
    unsupported_currencies: list[str] = Field(default_factory=list)


InvoiceListResponse = ListEnvelope[InvoiceResponse]
ExpenseListResponse = ListEnvelope[ExpenseResponse]
