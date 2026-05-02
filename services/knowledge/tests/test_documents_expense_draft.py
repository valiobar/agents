from __future__ import annotations

import sys
import unittest
from contextlib import asynccontextmanager
from asyncio import sleep
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.dependencies import get_document_service
from app.errors import UnsupportedDocumentTypeError, UploadTooLargeError
from app.main import app
from app.models.document import DocumentInDB, DocumentResponse, DocumentStatus, DocumentUpdate
from app.models.expense_extraction import ExpenseDraft, ExpenseDraftResponse
from app.services.document_service import DocumentService
from app.services.expense_extraction_service import ExpenseExtractionResult, ExpenseExtractionService
from app.services.ingestion_service import IngestionService


@asynccontextmanager
async def _noop_lifespan(_app):
    yield


class FakeBusinessServiceClient:
    async def require_company(self, user_id: str, company_id: str) -> None:
        await sleep(0)
        return None


class FakeVectorStore:
    def user_collection_name(self, user_id: str) -> str:
        return f"user_{user_id}"

    async def delete_by_document(self, collection_name: str, document_id: str) -> None:
        await sleep(0)
        return None


class FakeEmbeddings:
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        await sleep(0)
        return [[0.0] * 3 for _ in texts]


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.created: list[DocumentInDB] = []
        self.updates: list[tuple[str, DocumentUpdate]] = []

    async def create(self, *, user_id: str, document) -> DocumentInDB:
        await sleep(0)
        doc = DocumentInDB(
            id=f"doc-{len(self.created) + 1}",
            user_id=user_id,
            company_id=document.company_id,
            filename=document.filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            status=DocumentStatus.PROCESSING,
            chunk_count=0,
            content_hash=document.content_hash,
            error_message=None,
            metadata=document.metadata or {},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.created.append(doc)
        return doc

    async def update(self, document_id: str, user_id: str, update: DocumentUpdate) -> DocumentInDB | None:
        await sleep(0)
        self.updates.append((document_id, update))
        for idx, doc in enumerate(self.created):
            if doc.id == document_id and doc.user_id == user_id:
                new_doc = doc.model_copy(
                    update=update.model_dump(exclude_none=True, mode="python")
                    | {"updated_at": datetime.now(UTC)}
                )
                self.created[idx] = new_doc
                return new_doc
        return None

    async def get_by_id(self, *, document_id: str, user_id: str) -> DocumentInDB | None:
        await sleep(0)
        return next((d for d in self.created if d.id == document_id and d.user_id == user_id), None)

    async def list_by_user_company(self, *, user_id: str, company_id: str, limit: int, offset: int):
        await sleep(0)
        return []

    async def find_by_hash(self, user_id: str, company_id: str, content_hash: str) -> DocumentInDB | None:
        await sleep(0)
        return None


class FakeExpenseExtractionProvider:
    def __init__(self, *, draft: ExpenseDraft | None = None, raises: Exception | None = None) -> None:
        self._draft = draft
        self._raises = raises

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
        if self._raises:
            raise self._raises
        assert self._draft is not None
        update = {"source_document_id": source_document_id}
        if source_document_type != "auto":
            update["source_document_type"] = source_document_type
        return self._draft.model_copy(update=update)


class KnowledgeExpenseDraftRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app.router.lifespan_context = _noop_lifespan
        self.repo = FakeDocumentRepository()
        self.ingestion = IngestionService(
            self.repo,
            FakeVectorStore(),
            FakeEmbeddings(),
            FakeBusinessServiceClient(),
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_creates_document_and_returns_draft_with_source_document_number(self) -> None:
        draft = ExpenseDraft(
            counterparty="Office Store",
            expense_date=date(2026, 4, 27),
            amount=Decimal("24.00"),
            currency="EUR",
            category="office",
            description=None,
            deductible=True,
            deductible_rate=Decimal("1.0"),
            source_document_type="receipt",
            source_document_id="doc-1",
            source_document_number="R-839201",
            vendor_partner=None,
            items=None,
            confidence=0.92,
            warnings=[],
        )
        extraction = ExpenseExtractionService(
            provider=FakeExpenseExtractionProvider(draft=draft),
            provider_name="mock",
            model="mock-1",
        )
        service = DocumentService(
            self.repo,
            self.ingestion,
            FakeVectorStore(),
            FakeBusinessServiceClient(),
            extraction,
        )
        app.dependency_overrides[get_document_service] = lambda: service

        response = self.client.post(
            "/documents/expense-draft",
            headers={"x-user-id": "user-1"},
            files={"file": ("receipt.png", b"fake", "image/png")},
            data={"company_id": "company-1", "source_document_type": "auto"},
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["document"]["id"])
        self.assertEqual(body["draft"]["source_document_id"], body["document"]["id"])
        self.assertEqual(body["draft"]["source_document_type"], "receipt")
        self.assertEqual(body["draft"]["source_document_number"], "R-839201")

    def test_rejects_unsupported_content_type(self) -> None:
        original_allowed = list(settings.allowed_content_types)
        try:
            settings.allowed_content_types = ["image/png"]
            service = DocumentService(
                self.repo,
                self.ingestion,
                FakeVectorStore(),
                FakeBusinessServiceClient(),
                ExpenseExtractionService(
                    provider=FakeExpenseExtractionProvider(
                        raises=RuntimeError("should not be called"),
                    ),
                    provider_name="mock",
                    model="mock-1",
                ),
            )
            app.dependency_overrides[get_document_service] = lambda: service

            response = self.client.post(
                "/documents/expense-draft",
                headers={"x-user-id": "user-1"},
                files={"file": ("receipt.bin", b"fake", "application/octet-stream")},
                data={"company_id": "company-1", "source_document_type": "receipt"},
            )
            self.assertEqual(response.status_code, 415)
            self.assertIn("Unsupported document type", response.json()["detail"])
        finally:
            settings.allowed_content_types = original_allowed

    def test_rejects_oversized_file(self) -> None:
        original_max = settings.max_upload_size_bytes
        try:
            settings.max_upload_size_bytes = 3
            service = DocumentService(
                self.repo,
                self.ingestion,
                FakeVectorStore(),
                FakeBusinessServiceClient(),
                ExpenseExtractionService(
                    provider=FakeExpenseExtractionProvider(raises=RuntimeError("should not be called")),
                    provider_name="mock",
                    model="mock-1",
                ),
            )
            app.dependency_overrides[get_document_service] = lambda: service

            response = self.client.post(
                "/documents/expense-draft",
                headers={"x-user-id": "user-1"},
                files={"file": ("receipt.png", b"toolong", "image/png")},
                data={"company_id": "company-1", "source_document_type": "receipt"},
            )
            self.assertEqual(response.status_code, 413)
            self.assertEqual(response.json()["detail"], "Uploaded file exceeds maximum allowed size")
        finally:
            settings.max_upload_size_bytes = original_max

    def test_marks_extraction_failures_as_failed_metadata(self) -> None:
        extraction_error = RuntimeError("provider blew up")
        extraction = ExpenseExtractionService(
            provider=FakeExpenseExtractionProvider(raises=extraction_error),
            provider_name="mock",
            model="mock-1",
        )
        service = DocumentService(
            self.repo,
            self.ingestion,
            FakeVectorStore(),
            FakeBusinessServiceClient(),
            extraction,
        )
        app.dependency_overrides[get_document_service] = lambda: service

        response = self.client.post(
            "/documents/expense-draft",
            headers={"x-user-id": "user-1"},
            files={"file": ("receipt.png", b"fake", "image/png")},
            data={"company_id": "company-1", "source_document_type": "receipt"},
        )
        self.assertEqual(response.status_code, 500)
        self.assertTrue(self.repo.created)
        self.assertTrue(self.repo.updates)

        updated = self.repo.created[0]
        self.assertEqual(updated.status, DocumentStatus.FAILED)
        self.assertEqual(updated.metadata.get("source_document_type"), "receipt")
        extraction_meta = updated.metadata.get("extraction") or {}
        tasks = extraction_meta.get("tasks") or {}
        self.assertEqual(tasks.get("expense", {}).get("status"), "failed")


if __name__ == "__main__":
    unittest.main()

