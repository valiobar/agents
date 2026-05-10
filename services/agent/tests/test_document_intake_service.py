from __future__ import annotations

from asyncio import sleep
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from unittest import IsolatedAsyncioTestCase

from starlette.datastructures import UploadFile

from app.models.document_intake import (
    ConfirmInventoryImportForExpenseRequest,
    DocumentClassification,
    DocumentIntakeDraftResponse,
)
from app.models.financial import ExpenseResponse
from app.models.financial.receipt import (
    ConfirmExtractedExpenseRequest,
    ExpenseDraft,
    ExtractedExpenseItem,
    ExtractedPartnerDraft,
    PartnerUpsertResult,
)
from app.models.inventory import (
    InventoryImportPreviewResponse,
    InventoryImportResult,
    SupplierInvoiceLineCandidate,
)
from app.models.inventory.base import ImportPreviewStatus
from app.models.inventory.import_previews import InventoryImportPreviewLineData
from app.models.shared.document import DocumentResponse
from app.services.document_intake_service import DocumentIntakeService, create_document_workflow_registry
from app.services.receipt_service import ReceiptService


def _document(*, company_id: str = "company-1", filename: str = "upload.pdf") -> DocumentResponse:
    now = datetime.now(UTC)
    return DocumentResponse(
        id="doc-1",
        company_id=company_id,
        filename=filename,
        content_type="application/pdf",
        size_bytes=128,
        status="ready",
        chunk_count=0,
        created_at=now,
        updated_at=now,
    )


def _draft(
    *,
    source_document_type: str,
    source_document_id: str,
    items: list[ExtractedExpenseItem] | None = None,
    vendor_partner: ExtractedPartnerDraft | None = None,
) -> ExpenseDraft:
    return ExpenseDraft(
        counterparty="Vendor Ltd" if source_document_type == "invoice" else "Office Store",
        expense_date=date(2026, 5, 1),
        amount=Decimal("42.00"),
        currency="EUR",
        category="office",
        description=None,
        deductible=True,
        deductible_rate=Decimal("1.0"),
        source_document_type=source_document_type,  # type: ignore[arg-type]
        source_document_id=source_document_id,
        source_document_number="INV-42" if source_document_type == "invoice" else "R-42",
        vendor_partner=vendor_partner,
        items=items,
        confidence=0.9,
        warnings=[],
    )


def _extraction(
    *,
    document_type: str,
    draft: ExpenseDraft | None,
    document: DocumentResponse | None,
) -> DocumentIntakeDraftResponse:
    return DocumentIntakeDraftResponse(
        classification=DocumentClassification(
            document_type=document_type,  # type: ignore[arg-type]
            confidence=0.9,
            warnings=[],
        ),
        document=document,
        draft=draft,
        extracted_text="ok",
        provider="mock",
        model="mock-1",
        extracted_at=datetime.now(UTC),
    )


def _preview(*, preview_id: str = "preview-1", status: ImportPreviewStatus = "draft") -> InventoryImportPreviewResponse:
    return InventoryImportPreviewResponse(
        id=preview_id,
        user_id="user-1",
        company_id="company-1",
        document_id="doc-1",
        source_type="supplier_invoice_upload",
        status=status,
        lines=[
            InventoryImportPreviewLineData(
                candidate=SupplierInvoiceLineCandidate(
                    description="Widget",
                    sku="SKU-1",
                    barcode=None,
                    quantity=Decimal("5"),
                    unit="pcs",
                    unit_price=Decimal("10.00"),
                ),
                matched_item_id=None,
                proposed_item=None,
                location_id="loc-1",
                receipt_quantity=Decimal("5"),
                warnings=[],
            )
        ],
    )


class _FakeAgentRepo:
    async def get_by_id(self, user_id: str, agent_id: str):
        await sleep(0)
        return type("Agent", (), {"id": agent_id, "user_id": user_id, "company_id": "company-1"})()


class _FakeKnowledgeClient:
    def __init__(self, extraction: DocumentIntakeDraftResponse) -> None:
        self.extraction = extraction

    async def create_document_intake_draft(self, **_kwargs) -> DocumentIntakeDraftResponse:
        await sleep(0)
        return self.extraction


class _FakeBusinessClient:
    def __init__(self) -> None:
        self.import_preview_create_calls = 0
        self.import_preview_confirm_calls = 0
        self.import_preview_get_calls = 0
        self.partner_upsert_calls = 0
        self.create_expense_calls = 0
        self.created_statuses: list[str] = []

    async def company_exists(self, user_id: str, company_id: str) -> bool:
        await sleep(0)
        return True

    async def create_import_preview(self, user_id: str, payload) -> InventoryImportPreviewResponse:
        await sleep(0)
        self.import_preview_create_calls += 1
        return _preview()

    async def confirm_import_preview(self, user_id: str, preview_id: str) -> InventoryImportResult:
        await sleep(0)
        self.import_preview_confirm_calls += 1
        return InventoryImportResult(
            preview_id=preview_id,
            items_created=1,
            items_updated=0,
            movements_created=1,
        )

    async def get_import_preview(self, user_id: str, preview_id: str) -> InventoryImportPreviewResponse:
        await sleep(0)
        self.import_preview_get_calls += 1
        return _preview(preview_id=preview_id, status="confirmed")

    async def find_or_create_supplier_partner(
        self,
        *,
        user_id: str,
        company_id: str,
        vendor: ExtractedPartnerDraft,
    ) -> PartnerUpsertResult:
        await sleep(0)
        self.partner_upsert_calls += 1
        return PartnerUpsertResult(status="matched", partner=None)

    async def create_expense(self, user_id: str, payload) -> ExpenseResponse:
        await sleep(0)
        self.create_expense_calls += 1
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
            source_document_number=payload.source_document_number,
            items=None,
            deductible_amount=payload.amount or Decimal("1.00"),
            created_at=now,
            updated_at=now,
        )


def _file_upload() -> UploadFile:
    return UploadFile(file=BytesIO(b"fake-pdf"), filename="upload.pdf")


class DocumentIntakeServiceTests(IsolatedAsyncioTestCase):
    async def test_routes_receipt_supplier_and_unknown_branches(self) -> None:
        business = _FakeBusinessClient()
        document = _document()

        receipt_service = DocumentIntakeService(
            _FakeAgentRepo(),
            _FakeKnowledgeClient(
                _extraction(
                    document_type="receipt",
                    draft=_draft(source_document_type="receipt", source_document_id=document.id),
                    document=document,
                )
            ),
            business,
            create_document_workflow_registry(),
        )
        receipt_review = await receipt_service.create_intake(
            user_id="user-1",
            agent_id="agent-1",
            file=_file_upload(),
            requested_type="auto",
        )
        self.assertEqual(receipt_review.type, "receipt_expense_review")

        supplier_with_items_service = DocumentIntakeService(
            _FakeAgentRepo(),
            _FakeKnowledgeClient(
                _extraction(
                    document_type="supplier_invoice",
                    draft=_draft(
                        source_document_type="invoice",
                        source_document_id=document.id,
                        items=[
                            ExtractedExpenseItem(
                                description="Widget",
                                quantity=Decimal("5"),
                                unit_price=Decimal("10.00"),
                                unit_label="pcs",
                                sku="SKU-1",
                                barcode=None,
                                vat_rate=Decimal("0.2"),
                                category="office",
                            )
                        ],
                    ),
                    document=document,
                )
            ),
            business,
            create_document_workflow_registry(),
        )
        supplier_with_items_review = await supplier_with_items_service.create_intake(
            user_id="user-1",
            agent_id="agent-1",
            file=_file_upload(),
            requested_type="auto",
        )
        self.assertEqual(supplier_with_items_review.type, "supplier_invoice_inventory_review")

        supplier_without_items_service = DocumentIntakeService(
            _FakeAgentRepo(),
            _FakeKnowledgeClient(
                _extraction(
                    document_type="supplier_invoice",
                    draft=_draft(
                        source_document_type="invoice",
                        source_document_id=document.id,
                        items=[],
                    ),
                    document=document,
                )
            ),
            business,
            create_document_workflow_registry(),
        )
        supplier_without_items_review = await supplier_without_items_service.create_intake(
            user_id="user-1",
            agent_id="agent-1",
            file=_file_upload(),
            requested_type="auto",
        )
        self.assertEqual(supplier_without_items_review.type, "supplier_invoice_expense_review")

        unknown_service = DocumentIntakeService(
            _FakeAgentRepo(),
            _FakeKnowledgeClient(
                _extraction(
                    document_type="unknown",
                    draft=None,
                    document=document,
                )
            ),
            business,
            create_document_workflow_registry(),
        )
        unknown_review = await unknown_service.create_intake(
            user_id="user-1",
            agent_id="agent-1",
            file=_file_upload(),
            requested_type="auto",
        )
        self.assertEqual(unknown_review.type, "unknown_document_review")
        self.assertEqual(business.import_preview_create_calls, 1)

    async def test_confirm_inventory_import_returns_expense_review_only(self) -> None:
        business = _FakeBusinessClient()
        document = _document()
        draft = _draft(
            source_document_type="invoice",
            source_document_id=document.id,
            items=[],
            vendor_partner=ExtractedPartnerDraft(
                name="Vendor Ltd",
                registration_number="123",
                vat_number=None,
                city="Sofia",
                country="Bulgaria",
                address="Addr",
                accountable_person="Ivan",
                email=None,
                phone=None,
                confidence=0.9,
                warnings=[],
            ),
        )
        service = DocumentIntakeService(
            _FakeAgentRepo(),
            _FakeKnowledgeClient(_extraction(document_type="supplier_invoice", draft=draft, document=document)),
            business,
            create_document_workflow_registry(),
        )

        response = await service.confirm_supplier_invoice_inventory_import(
            user_id="user-1",
            agent_id="agent-1",
            payload=ConfirmInventoryImportForExpenseRequest(preview_id="preview-1", draft=draft),
        )

        self.assertEqual(response.type, "supplier_invoice_expense_review")
        self.assertEqual(business.import_preview_confirm_calls, 1)
        self.assertEqual(business.import_preview_get_calls, 1)
        self.assertEqual(business.create_expense_calls, 0)

    async def test_supplier_invoice_two_stage_confirmation_still_upserts_partner(self) -> None:
        business = _FakeBusinessClient()
        vendor = ExtractedPartnerDraft(
            name="Vendor Ltd",
            registration_number="123",
            vat_number=None,
            city="Sofia",
            country="Bulgaria",
            address="Addr",
            accountable_person="Ivan",
            email=None,
            phone=None,
            confidence=0.9,
            warnings=[],
        )
        draft = _draft(
            source_document_type="invoice",
            source_document_id="doc-1",
            items=[
                ExtractedExpenseItem(
                    description="Widget",
                    quantity=Decimal("2"),
                    unit_price=Decimal("11.00"),
                    unit_label="pcs",
                    sku="SKU-1",
                    barcode=None,
                    vat_rate=Decimal("0.2"),
                    category="office",
                )
            ],
            vendor_partner=vendor,
        )
        intake_service = DocumentIntakeService(
            _FakeAgentRepo(),
            _FakeKnowledgeClient(
                _extraction(
                    document_type="supplier_invoice",
                    draft=draft,
                    document=_document(),
                )
            ),
            business,
            create_document_workflow_registry(),
        )
        intake_review = await intake_service.create_intake(
            user_id="user-1",
            agent_id="agent-1",
            file=_file_upload(),
            requested_type="auto",
        )
        self.assertEqual(intake_review.type, "supplier_invoice_inventory_review")

        inventory_review = await intake_service.confirm_supplier_invoice_inventory_import(
            user_id="user-1",
            agent_id="agent-1",
            payload=ConfirmInventoryImportForExpenseRequest(preview_id="preview-1", draft=draft),
        )
        self.assertEqual(inventory_review.type, "supplier_invoice_expense_review")
        self.assertIsNotNone(inventory_review.draft.vendor_partner)
        self.assertEqual(inventory_review.draft.vendor_partner.name, vendor.name)

        receipt_service = ReceiptService(
            _FakeAgentRepo(),
            _FakeKnowledgeClient(_extraction(document_type="receipt", draft=draft, document=_document())),
            business,
        )
        expense_result = await receipt_service.confirm_expense(
            user_id="user-1",
            agent_id="agent-1",
            payload=ConfirmExtractedExpenseRequest(
                **inventory_review.draft.model_dump(),
                confirmed=True,
            ),
        )
        self.assertEqual(business.partner_upsert_calls, 1)
        self.assertEqual(business.create_expense_calls, 1)
        self.assertIsNotNone(expense_result.vendor_partner)
        self.assertIn(expense_result.vendor_partner.status, {"matched", "created"})
