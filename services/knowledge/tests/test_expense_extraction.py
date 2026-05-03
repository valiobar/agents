from __future__ import annotations

import sys
import unittest
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock
from asyncio import sleep

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.expense_extraction import ExpenseDraft, ExtractedExpenseItem
from app.services.expense_extraction_provider import _build_openai_upload_part, _sanitize_draft
from app.services.expense_extraction_service import ExpenseExtractionService


class FakeProvider:
    def __init__(self) -> None:
        self.last_extracted_text: str | None = None

    async def extract_draft(
        self,
        *,
        filename: str,
        content_type: str,
        content: bytes,
        extracted_text: str | None,
        source_document_type: str,
        source_document_id: str,
    ) -> ExpenseDraft:
        await sleep(0)
        self.last_extracted_text = extracted_text
        return ExpenseDraft(
            counterparty="Office Store",
            expense_date=date(2026, 4, 27),
            amount=Decimal("24.00"),
            currency="EUR",
            category="office",
            description=None,
            deductible=True,
            deductible_rate=Decimal("1.0"),
            source_document_type=source_document_type,  # type: ignore[arg-type]
            source_document_id=source_document_id,
            source_document_number="R-839201",
            vendor_partner=None,
            items=None,
            confidence=0.9,
            warnings=[],
        )


class ExpenseExtractionServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_openai_upload_part_uses_input_image_for_supported_images(self) -> None:
        part = _build_openai_upload_part(
            filename="receipt.jpg",
            content_type="image/jpg",
            content=b"fake image",
        )

        self.assertEqual(part["type"], "input_image")
        self.assertTrue(part["image_url"].startswith("data:image/jpeg;base64,"))
        self.assertNotIn("mime_type", part)

    def test_openai_upload_part_uses_data_url_file_payload(self) -> None:
        part = _build_openai_upload_part(
            filename="receipt.pdf",
            content_type="application/pdf",
            content=b"fake pdf",
        )

        self.assertEqual(part["type"], "input_file")
        self.assertEqual(part["filename"], "receipt.pdf")
        self.assertTrue(part["file_data"].startswith("data:application/pdf;base64,"))
        self.assertNotIn("mime_type", part)

    def test_openai_upload_part_rejects_unsupported_images(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Unsupported receipt image type"):
            _build_openai_upload_part(
                filename="receipt.heic",
                content_type="image/heic",
                content=b"fake heic",
            )

    def test_expense_draft_accepts_percent_rates_from_llm_output(self) -> None:
        draft = ExpenseDraft(
            counterparty="Office Store",
            expense_date=date(2026, 4, 27),
            amount=Decimal("24.00"),
            currency="EUR",
            category="office",
            deductible=True,
            deductible_rate=100,
            source_document_type="receipt",
            source_document_id="doc-1",
            items=[
                ExtractedExpenseItem(
                    description="Notebook",
                    quantity=Decimal("1"),
                    unit_price=Decimal("20.00"),
                    vat_rate=20,
                )
            ],
            confidence=0.9,
        )

        self.assertEqual(draft.deductible_rate, Decimal("1"))
        assert draft.items is not None
        self.assertEqual(draft.items[0].vat_rate, Decimal("0.2"))

    def test_sanitize_draft_defaults_missing_counterparty(self) -> None:
        data = _sanitize_draft(
            {
                "expense_date": "2026-03-01",
                "amount": "12.50",
                "currency": "EUR",
                "category": "meals",
                "deductible": True,
                "deductible_rate": "1.0",
                "source_document_type": "receipt",
                "confidence": 0.95,
                "warnings": [],
            }
        )

        draft = ExpenseDraft.model_validate(data)

        self.assertEqual(draft.counterparty, "Unknown counterparty")
        self.assertIn("Counterparty was missing", draft.warnings[0])

    def test_sanitize_draft_infers_counterparty_from_vendor_partner(self) -> None:
        data = _sanitize_draft(
            {
                "counterparty": "",
                "expense_date": "2026-03-01",
                "amount": "12.50",
                "currency": "EUR",
                "category": "professional_services",
                "deductible": True,
                "deductible_rate": "1.0",
                "source_document_type": "invoice",
                "vendor_partner": {
                    "name": "Consulting Ltd",
                    "registration_number": None,
                    "vat_number": None,
                    "city": None,
                    "country": "Bulgaria",
                    "address": None,
                    "accountable_person": None,
                    "email": None,
                    "phone": None,
                    "confidence": 0.9,
                    "warnings": [],
                },
                "confidence": 0.95,
                "warnings": [],
            }
        )

        draft = ExpenseDraft.model_validate(data)

        self.assertEqual(draft.counterparty, "Consulting Ltd")

    async def test_extract_loads_text_for_supported_types_and_passes_to_provider(self) -> None:
        provider = FakeProvider()
        service = ExpenseExtractionService(provider=provider, provider_name="mock", model="mock-1")

        # Patch module-level load_document used by ExpenseExtractionService.
        import app.services.expense_extraction_service as module

        module.load_document = AsyncMock(  # type: ignore[assignment]
            return_value=[type("Page", (), {"text": "Line 1"})(), type("Page", (), {"text": "Line 2"})()]
        )

        result = await service.extract(
            filename="receipt.txt",
            content_type="text/plain",
            content=b"ignored",
            source_document_type="receipt",
            source_document_id="doc-1",
        )

        self.assertEqual(provider.last_extracted_text, "Line 1\n\nLine 2")
        self.assertEqual(result.draft.source_document_id, "doc-1")
        self.assertEqual(result.draft.source_document_type, "receipt")
        self.assertEqual(result.provider, "mock")
        self.assertEqual(result.model, "mock-1")


if __name__ == "__main__":
    unittest.main()

