from __future__ import annotations

import sys
import unittest
from asyncio import sleep
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.dependencies import (
    get_company_service,
    get_expense_service,
    get_financial_summary_service,
    get_invoice_service,
    get_partner_service,
)
from app.main import app
from app.models.company import CompanyCreate, CompanyInDB
from app.models.financial import (
    ExpenseInDB,
    ExpenseItem,
    FinancialSummaryRequest,
    FinancialSummaryResponse,
    InvoiceInDB,
    InvoiceItem,
)
from app.models.partner import PartnerInDB


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _company(user_id: str = "user-1", company_id: str = "company-1") -> CompanyInDB:
    now = _now()
    return CompanyInDB(
        id=company_id,
        user_id=user_id,
        name="Acme Ltd",
        registration_number="123456789",
        city="Sofia",
        country="Bulgaria",
        address="1 Business St",
        accountable_person="Ivan Ivanov",
        created_at=now,
        updated_at=now,
    )


def _partner(user_id: str = "user-1", company_id: str = "company-1") -> PartnerInDB:
    now = _now()
    return PartnerInDB(
        id="partner-1",
        user_id=user_id,
        company_id=company_id,
        kind="client",
        name="Client Ltd",
        registration_number="987654321",
        city="Plovdiv",
        country="Bulgaria",
        address="2 Client St",
        accountable_person="Petar Petrov",
        created_at=now,
        updated_at=now,
    )


def _invoice(user_id: str = "user-1", company_id: str = "company-1", partner_id: str = "partner-1") -> InvoiceInDB:
    item = InvoiceItem(
        description="Accounting consultation",
        quantity=Decimal("1"),
        unit_label="pcs",
        unit_price=Decimal("100.00"),
        vat_rate=Decimal("0.20"),
        category="services",
        subtotal=Decimal("100.00"),
        vat_amount=Decimal("20.00"),
        total=Decimal("120.00"),
    )
    return InvoiceInDB(
        id="invoice-1",
        user_id=user_id,
        company_id=company_id,
        partner_id=partner_id,
        invoice_number="INV-2026-00001",
        issue_date=date(2026, 4, 27),
        tax_event_date=date(2026, 4, 27),
        due_date=date(2026, 5, 11),
        place_of_supply="Bulgaria",
        payment_method="bank_transfer",
        currency="EUR",
        items=[item],
        subtotal=Decimal("100.00"),
        vat_total=Decimal("20.00"),
        total=Decimal("120.00"),
        status="draft",
        notes=None,
        created_at=_now(),
        updated_at=_now(),
    )


def _expense(user_id: str = "user-1") -> ExpenseInDB:
    item = ExpenseItem(
        description="Paper",
        quantity=Decimal("2"),
        unit_price=Decimal("5.00"),
        category="office",
        total=Decimal("10.00"),
    )
    return ExpenseInDB(
        id="expense-1",
        user_id=user_id,
        counterparty="Office Store",
        expense_date=date(2026, 4, 27),
        amount=Decimal("10.00"),
        currency="EUR",
        category="office",
        description="Office supplies",
        deductible=True,
        deductible_rate=Decimal("1.0"),
        source_document_type="receipt",
        source_document_id=None,
        items=[item],
        deductible_amount=Decimal("10.00"),
        created_at=_now(),
        updated_at=_now(),
    )


class FakeCompanyService:
    def __init__(self) -> None:
        self.created: CompanyInDB | None = None

    async def create_company(self, user_id: str, payload: CompanyCreate) -> CompanyInDB:
        await sleep(0)
        now = _now()
        self.created = CompanyInDB(
            id="company-1",
            user_id=user_id,
            created_at=now,
            updated_at=now,
            **payload.model_dump(mode="python"),
        )
        return self.created

    async def list_companies(self, user_id: str, limit: int, offset: int) -> list[CompanyInDB]:
        await sleep(0)
        return [self.created or _company(user_id)]

    async def require_company(self, user_id: str, company_id: str) -> CompanyInDB:
        await sleep(0)
        return self.created or _company(user_id, company_id)

    async def delete_company(self, user_id: str, company_id: str) -> None:
        await sleep(0)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Company has invoices")


class FakePartnerService:
    async def list_partners(
        self,
        user_id: str,
        company_id: str,
        kind: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> list[PartnerInDB]:
        await sleep(0)
        return [_partner(user_id, company_id)]


class FakeInvoiceService:
    async def create_invoice(self, user_id: str, payload: object) -> InvoiceInDB:
        await sleep(0)
        return _invoice(user_id, getattr(payload, "company_id"), getattr(payload, "partner_id"))

    async def list_invoices(self, user_id: str, filters: object, limit: int, offset: int) -> list[InvoiceInDB]:
        await sleep(0)
        company_id = getattr(filters, "company_id") or "company-1"
        partner_id = getattr(filters, "partner_id") or "partner-1"
        return [_invoice(user_id, company_id, partner_id)]


class FakeExpenseService:
    async def list_expenses(self, user_id: str, filters: object, limit: int, offset: int) -> list[ExpenseInDB]:
        await sleep(0)
        return [_expense(user_id)]


class FakeFinancialSummaryService:
    async def get_summary(self, user_id: str, request: FinancialSummaryRequest) -> FinancialSummaryResponse:
        await sleep(0)
        return FinancialSummaryResponse(
            currency="BGN",
            exchange_rates_to_bgn={"EUR": Decimal("1.95583000")},
            invoice_total=Decimal("156824.04"),
            expense_total=Decimal("19.56"),
            deductible_expense_total=Decimal("9.78"),
            net_total=Decimal("156804.48"),
            buckets=[],
            totals_by_currency=[],
            unsupported_currencies=[],
        )


class BusinessRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.company_service = FakeCompanyService()
        app.dependency_overrides[get_company_service] = lambda: self.company_service
        app.dependency_overrides[get_partner_service] = FakePartnerService
        app.dependency_overrides[get_invoice_service] = FakeInvoiceService
        app.dependency_overrides[get_expense_service] = FakeExpenseService
        app.dependency_overrides[get_financial_summary_service] = FakeFinancialSummaryService
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_business_companies_require_user_id(self) -> None:
        response = self.client.get("/companies")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Missing x-user-id header")

    def test_business_company_lifecycle_and_delete_conflict(self) -> None:
        headers = {"x-user-id": "user-1"}
        created = self.client.post(
            "/companies",
            headers=headers,
            json={
                "name": "Acme Ltd",
                "registration_number": "123456789",
                "city": "Sofia",
                "country": "Bulgaria",
                "address": "1 Business St",
                "accountable_person": "Ivan Ivanov",
            },
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["id"], "company-1")

        listed = self.client.get("/companies", headers=headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["id"], "company-1")

        deleted = self.client.delete("/companies/company-1", headers=headers)
        self.assertEqual(deleted.status_code, 409)
        self.assertEqual(deleted.json()["detail"], "Company has invoices")

    def test_business_partner_list_and_search(self) -> None:
        response = self.client.get(
            "/partners?company_id=company-1&kind=client&query=Client",
            headers={"x-user-id": "user-1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["company_id"], "company-1")
        self.assertEqual(response.json()[0]["name"], "Client Ltd")

    def test_business_invoice_create_and_list(self) -> None:
        headers = {"x-user-id": "user-1"}
        created = self.client.post(
            "/invoices",
            headers=headers,
            json={
                "company_id": "company-1",
                "partner_id": "partner-1",
                "issue_date": "2026-04-27",
                "tax_event_date": "2026-04-27",
                "due_date": "2026-05-11",
                "place_of_supply": "Bulgaria",
                "payment_method": "bank_transfer",
                "currency": "EUR",
                "items": [
                    {
                        "description": "Accounting consultation",
                        "quantity": "1",
                        "unit_label": "pcs",
                        "unit_price": "100.00",
                        "vat_rate": "0.20",
                        "category": "services",
                    }
                ],
            },
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["company_id"], "company-1")

        listed = self.client.get("/invoices?company_id=company-1", headers=headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["id"], "invoice-1")

    def test_business_expense_list(self) -> None:
        response = self.client.get("/expenses?limit=1", headers={"x-user-id": "user-1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], "expense-1")
        self.assertEqual(response.json()[0]["category"], "office")

    def test_financial_summary_route_requires_user_id(self) -> None:
        response = self.client.post(
            "/financial-summary",
            json={"include_invoices": True, "include_expenses": True},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Missing x-user-id header")

    def test_financial_summary_route_returns_summary(self) -> None:
        response = self.client.post(
            "/financial-summary",
            headers={"x-user-id": "user-1"},
            json={"include_invoices": True, "include_expenses": True},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["currency"], "BGN")
        self.assertEqual(response.json()["invoice_total"], "156824.04")


if __name__ == "__main__":
    unittest.main()
