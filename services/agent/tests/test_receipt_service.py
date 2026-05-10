from __future__ import annotations

import unittest
from asyncio import sleep
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
from fastapi import HTTPException

from app.clients.business import BusinessClient, BusinessClientError
from app.models.financial import ExpenseResponse
from app.models.financial.partner import PartnerResponse
from app.models.financial.receipt import (
    ConfirmExtractedExpenseRequest,
    ExtractedPartnerDraft,
    PartnerUpsertResult,
)
from app.services.receipt_service import ReceiptService


class FakeAgentRepo:
    def __init__(self, *, company_id: str | None) -> None:
        self.company_id = company_id

    async def get_by_id(self, user_id: str, agent_id: str):
        await sleep(0)
        if self.company_id is None:
            return type("Agent", (), {"id": agent_id, "user_id": user_id, "company_id": None})()
        return type("Agent", (), {"id": agent_id, "user_id": user_id, "company_id": self.company_id})()


class FakeKnowledgeClient:
    async def create_expense_draft(self, *, user_id: str, company_id: str, file, source_document_type: str):
        await sleep(0)
        raise AssertionError("KnowledgeClient should not be called in confirm tests.")


class FakeBusinessClient:
    def __init__(self) -> None:
        self.last_create_payload = None
        self.partner_called = False

    async def company_exists(self, user_id: str, company_id: str) -> bool:
        await sleep(0)
        return True

    async def find_or_create_supplier_partner(self, *, user_id: str, company_id: str, vendor: ExtractedPartnerDraft):
        await sleep(0)
        self.partner_called = True
        return PartnerUpsertResult(status="matched", partner=None)

    async def create_expense(self, user_id: str, payload):
        await sleep(0)
        self.last_create_payload = payload
        now = datetime.now(UTC)
        return ExpenseResponse(
            id="expense-1",
            user_id=user_id,
            company_id=payload.company_id,
            partner_id=payload.partner_id,
            counterparty=payload.counterparty,
            expense_date=payload.expense_date,
            amount=payload.amount or Decimal("1.00"),
            currency=payload.currency,
            category=payload.category,
            description=payload.description,
            deductible=payload.deductible,
            deductible_rate=payload.deductible_rate,
            source_document_type=payload.source_document_type,
            source_document_id=payload.source_document_id,
            source_document_number=getattr(payload, "source_document_number", None),
            items=None,
            deductible_amount=payload.amount or Decimal("1.00"),
            created_at=now,
            updated_at=now,
        )


class ReceiptServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_confirm_requires_true(self) -> None:
        service = ReceiptService(
            FakeAgentRepo(company_id="company-1"),
            FakeKnowledgeClient(),
            FakeBusinessClient(),
        )
        payload = ConfirmExtractedExpenseRequest(
            counterparty="Office Store",
            expense_date=date(2026, 4, 27),
            amount=Decimal("24.00"),
            category="office",
            source_document_type="receipt",
            source_document_id="doc-1",
            source_document_number="R-839201",
            confirmed=False,
        )
        with self.assertRaises(HTTPException) as raised:
            await service.confirm_expense(user_id="user-1", agent_id="agent-1", payload=payload)
        self.assertEqual(raised.exception.status_code, 400)

    async def test_confirm_preserves_source_document_number_in_business_payload(self) -> None:
        business = FakeBusinessClient()
        service = ReceiptService(
            FakeAgentRepo(company_id="company-1"),
            FakeKnowledgeClient(),
            business,
        )
        payload = ConfirmExtractedExpenseRequest(
            counterparty="Office Store",
            expense_date=date(2026, 4, 27),
            amount=Decimal("24.00"),
            category="office",
            source_document_type="receipt",
            source_document_id="doc-1",
            source_document_number="R-839201",
            confirmed=True,
        )
        result = await service.confirm_expense(user_id="user-1", agent_id="agent-1", payload=payload)
        self.assertEqual(result.expense.source_document_number, "R-839201")
        self.assertIsNotNone(business.last_create_payload)
        self.assertEqual(business.last_create_payload.source_document_number, "R-839201")

    async def test_invoice_confirm_requires_vendor_partner(self) -> None:
        service = ReceiptService(
            FakeAgentRepo(company_id="company-1"),
            FakeKnowledgeClient(),
            FakeBusinessClient(),
        )
        payload = ConfirmExtractedExpenseRequest(
            counterparty="Vendor Ltd",
            expense_date=date(2026, 4, 27),
            amount=Decimal("120.00"),
            category="professional_services",
            source_document_type="invoice",
            source_document_id="doc-1",
            confirmed=True,
            vendor_partner=None,
        )
        with self.assertRaises(HTTPException) as raised:
            await service.confirm_expense(user_id="user-1", agent_id="agent-1", payload=payload)
        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("requires reviewed vendor partner details", raised.exception.detail)

    async def test_invoice_confirm_allows_vendor_partner_with_name_only(self) -> None:
        business = FakeBusinessClient()
        service = ReceiptService(
            FakeAgentRepo(company_id="company-1"),
            FakeKnowledgeClient(),
            business,
        )
        payload = ConfirmExtractedExpenseRequest(
            counterparty="Vendor Ltd",
            expense_date=date(2026, 4, 27),
            amount=Decimal("120.00"),
            category="professional_services",
            source_document_type="invoice",
            source_document_id="doc-1",
            confirmed=True,
            vendor_partner=ExtractedPartnerDraft(name="Vendor Ltd", registration_number=None, confidence=0.7),
        )
        result = await service.confirm_expense(user_id="user-1", agent_id="agent-1", payload=payload)
        self.assertTrue(business.partner_called)
        self.assertEqual(result.vendor_partner.status, "matched")


class SupplierPartnerMatchingTests(unittest.IsolatedAsyncioTestCase):
    async def test_matches_by_registration_or_vat_before_name(self) -> None:
        transport = httpx.MockTransport(lambda _req: httpx.Response(200, json=[]))
        async with httpx.AsyncClient(transport=transport, base_url="http://business:8005") as http:
            client = BusinessClient(http)

            partner_by_name = PartnerResponse(
                id="p-name",
                user_id="user-1",
                company_id="company-1",
                kind="supplier",
                name="Vendor Ltd",
                registration_number="DIFFERENT",
                vat_number=None,
                city="Sofia",
                country="Bulgaria",
                address="Addr",
                accountable_person="Ivan",
                email=None,
                phone=None,
                notes=None,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            partner_by_reg = partner_by_name.model_copy(update={"id": "p-reg", "registration_number": "123"})
            client.list_partners = AsyncMock(return_value=[partner_by_name, partner_by_reg])  # type: ignore[assignment]

            vendor = ExtractedPartnerDraft(
                name="  vendor   ltd ",
                registration_number="123",
                vat_number=None,
                city="Sofia",
                country="Bulgaria",
                address="Addr",
                accountable_person="Ivan",
                confidence=0.9,
                warnings=[],
            )
            matched = await client.find_matching_supplier_partner(user_id="user-1", company_id="company-1", vendor=vendor)
            self.assertIsNotNone(matched)
            self.assertEqual(matched.id, "p-reg")

