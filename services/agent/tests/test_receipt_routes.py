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

from app.dependencies import get_receipt_service
from app.main import app
from app.models.agent import AgentConfig, AgentInDB
from app.models.document import DocumentResponse
from app.models.receipt import ExpenseDraft, ExpenseDraftResponse
from app.services.receipt_service import ReceiptService


@asynccontextmanager
async def _noop_lifespan(_app):
    yield


def _agent(*, user_id: str, agent_id: str, company_id: str | None) -> AgentInDB:
    now = datetime.now(UTC)
    return AgentInDB(
        id=agent_id,
        user_id=user_id,
        name="My Accountant",
        description=None,
        agent_type="accountant",
        company_id=company_id,
        config=AgentConfig(),
        created_at=now,
        updated_at=now,
    )


class FakeAgentRepo:
    def __init__(self, agent: AgentInDB | None) -> None:
        self._agent = agent

    async def get_by_id(self, user_id: str, agent_id: str) -> AgentInDB | None:
        await sleep(0)
        return self._agent if self._agent and self._agent.user_id == user_id and self._agent.id == agent_id else None


class FakeKnowledgeClient:
    def __init__(self) -> None:
        self.last_company_id: str | None = None
        self.last_source_document_type: str | None = None

    async def create_expense_draft(self, *, user_id: str, company_id: str, file, source_document_type: str):
        await sleep(0)
        self.last_company_id = company_id
        self.last_source_document_type = source_document_type
        now = datetime.now(UTC)
        document = DocumentResponse(
            id="doc-1",
            company_id=company_id,
            filename="receipt.png",
            content_type="image/png",
            size_bytes=123,
            status="ready",
            chunk_count=0,
            created_at=now,
            updated_at=now,
        )
        draft = ExpenseDraft(
            counterparty="Office Store",
            expense_date=date(2026, 4, 27),
            amount=Decimal("24.00"),
            currency="EUR",
            category="office",
            description=None,
            deductible=True,
            deductible_rate=Decimal("1.0"),
            source_document_type="receipt" if source_document_type == "auto" else source_document_type,  # type: ignore[arg-type]
            source_document_id=document.id,
            source_document_number="R-839201",
            vendor_partner=None,
            items=None,
            confidence=0.9,
            warnings=[],
        )
        return ExpenseDraftResponse(
            document=document,
            draft=draft,
            extracted_text=None,
            provider="mock",
            model="mock-1",
            extracted_at=now,
        )


class FakeBusinessClient:
    def __init__(self, exists: bool = True) -> None:
        self._exists = exists

    async def company_exists(self, user_id: str, company_id: str) -> bool:
        await sleep(0)
        return self._exists


class ReceiptRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app.router.lifespan_context = _noop_lifespan
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_draft_rejects_missing_agent(self) -> None:
        service = ReceiptService(
            FakeAgentRepo(None),
            FakeKnowledgeClient(),
            FakeBusinessClient(),
        )
        app.dependency_overrides[get_receipt_service] = lambda: service

        response = self.client.post(
            "/agents/agent-1/expense-drafts",
            headers={"x-user-id": "user-1"},
            files={"file": ("receipt.png", b"fake", "image/png")},
            data={"source_document_type": "receipt"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Agent not found")

    def test_draft_rejects_unassigned_agent(self) -> None:
        service = ReceiptService(
            FakeAgentRepo(_agent(user_id="user-1", agent_id="agent-1", company_id=None)),
            FakeKnowledgeClient(),
            FakeBusinessClient(),
        )
        app.dependency_overrides[get_receipt_service] = lambda: service

        response = self.client.post(
            "/agents/agent-1/expense-drafts",
            headers={"x-user-id": "user-1"},
            files={"file": ("receipt.png", b"fake", "image/png")},
            data={"source_document_type": "receipt"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "Receipt workflow requires a company-scoped agent")

    def test_draft_forwards_assigned_company_upload(self) -> None:
        knowledge = FakeKnowledgeClient()
        service = ReceiptService(
            FakeAgentRepo(_agent(user_id="user-1", agent_id="agent-1", company_id="company-1")),
            knowledge,
            FakeBusinessClient(exists=True),
        )
        app.dependency_overrides[get_receipt_service] = lambda: service

        response = self.client.post(
            "/agents/agent-1/expense-drafts",
            headers={"x-user-id": "user-1"},
            files={"file": ("receipt.png", b"fake", "image/png")},
            data={"source_document_type": "auto"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(knowledge.last_company_id, "company-1")
        self.assertEqual(knowledge.last_source_document_type, "auto")
        self.assertEqual(response.json()["draft"]["source_document_number"], "R-839201")


if __name__ == "__main__":
    unittest.main()

