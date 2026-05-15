from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.shared.agent import AgentConfig, AgentInDB
from app.models.shared.conversation import MessageSchema
from app.runtime.router import (
    RouterAgent,
    RouterDecision,
    SalesInvoiceClassifierPrefill,
    SalesInvoicePrefillLine,
    _format_history_snippet,
    _resolve_sales_invoice_workflow_prefill,
)
from app.runtime.workflow_suggestion import infer_sales_invoice_prefill, message_mentions_stock_backed_invoice
from app.runtime.usage import LLMUsageEvent


def fake_router_agent(*, company_id: str | None = None) -> AgentInDB:
    now = datetime.now(UTC)
    return AgentInDB(
        id="router-1",
        user_id="user-1",
        name="Router",
        description=None,
        agent_type="router",
        company_id=company_id,
        config=AgentConfig(provider="openai", model="gpt-4.1-mini", temperature=0.1),
        created_at=now,
        updated_at=now,
    )


def fake_message(role: str, content: str) -> MessageSchema:
    return MessageSchema(role=role, content=content, created_at=datetime.now(UTC))


def fake_usage_event(*, agent_id: str) -> LLMUsageEvent:
    now = datetime.now(UTC)
    return LLMUsageEvent(
        user_id="user-1",
        agent_id=agent_id,
        provider="openai",
        model="gpt-4.1-mini",
        run_id="child-run",
        llm_call_index=1,
        input_tokens=4,
        output_tokens=2,
        total_tokens=6,
        stream_chunks=1,
        stream_chars=6,
        started_at=now,
        completed_at=now,
        duration_ms=12,
    )


class FakeRuntime:
    def __init__(self, *, tokens: list[str], usage_events: list[LLMUsageEvent] | None = None) -> None:
        self.tokens = tokens
        self._usage_events = list(usage_events or [])

    async def run(self, message: str, history: list[MessageSchema]):
        for token in self.tokens:
            yield token

    def consume_usage_events(self) -> list[LLMUsageEvent]:
        events = self._usage_events
        self._usage_events = []
        return events


class RouterAgentTests(unittest.IsolatedAsyncioTestCase):
    def test_router_decision_validation(self) -> None:
        with self.assertRaises(ValidationError):
            RouterDecision(route="ops", reason="invalid route", confidence=0.9)

        with self.assertRaises(ValidationError):
            RouterDecision(route="general", reason="x", confidence=1.5)

    def test_history_snippet_is_bounded(self) -> None:
        snippet = _format_history_snippet(
            [
                fake_message("user", "first message should be dropped"),
                fake_message("assistant", "second message is very long and should be trimmed"),
                fake_message("user", "third"),
            ],
            max_turns=2,
            max_chars=10,
        )

        self.assertNotIn("first message", snippet)
        self.assertIn("ASSISTANT: second mes ...", snippet)
        self.assertIn("USER: third", snippet)

    def test_router_system_prompt_mentions_workflow_suggestion_rules(self) -> None:
        router = RouterAgent(
            fake_router_agent(company_id="company-1"),
            FakeListChatModel(responses=["unused"]),
            "user-1",
            object(),
        )

        prompt = router.get_system_prompt()
        self.assertIn("sales invoice creation intent with product/goods/service lines", prompt)
        self.assertIn("workflow_suggestion", prompt)
        self.assertIn("does not call workflow endpoints directly", prompt)
        self.assertIn("frontend kickoff requires explicit user confirmation", prompt)

    async def test_router_delegates_inventory_tokens(self) -> None:
        router = RouterAgent(
            fake_router_agent(company_id="company-1"),
            FakeListChatModel(responses=["unused"]),
            "user-1",
            object(),
        )
        router.configure_children(
            accountant_runtime=None,
            inventory_runtime=FakeRuntime(tokens=["Stock", " ok"]),
        )

        with patch(
            "app.runtime.router.classify_route",
            new=AsyncMock(return_value=RouterDecision(route="inventory", reason="stock", confidence=0.95)),
        ):
            tokens: list[str] = []
            async for token in router.run("How many iPhones?", history=[]):
                tokens.append(token)

        self.assertEqual(tokens, ["Stock", " ok"])
        self.assertIsNotNone(router.route_metadata)
        assert router.route_metadata is not None
        self.assertEqual(router.route_metadata.predicted_route, "inventory")
        self.assertEqual(router.route_metadata.executed_route, "inventory")
        self.assertEqual(router.route_metadata.company_scope, "assigned")

    async def test_router_delegates_accountant_tokens(self) -> None:
        router = RouterAgent(
            fake_router_agent(company_id=None),
            FakeListChatModel(responses=["unused"]),
            "user-1",
            object(),
        )
        router.configure_children(
            accountant_runtime=FakeRuntime(tokens=["Invoice", " ready"]),
            inventory_runtime=None,
        )

        with patch(
            "app.runtime.router.classify_route",
            new=AsyncMock(return_value=RouterDecision(route="accountant", reason="invoice", confidence=0.92)),
        ):
            tokens: list[str] = []
            async for token in router.run("Create invoice", history=[]):
                tokens.append(token)

        self.assertEqual(tokens, ["Invoice", " ready"])
        self.assertIsNotNone(router.route_metadata)
        assert router.route_metadata is not None
        self.assertEqual(router.route_metadata.predicted_route, "accountant")
        self.assertEqual(router.route_metadata.executed_route, "accountant")
        self.assertEqual(router.route_metadata.company_scope, "unassigned")

    async def test_missing_child_falls_back_to_general(self) -> None:
        router = RouterAgent(
            fake_router_agent(company_id=None),
            FakeListChatModel(responses=["unused"]),
            "user-1",
            object(),
        )
        router.configure_children(accountant_runtime=None, inventory_runtime=None, fallback_llm=router.llm)

        with patch(
            "app.runtime.router.classify_route",
            new=AsyncMock(return_value=RouterDecision(route="inventory", reason="stock", confidence=0.9)),
        ), patch(
            "app.runtime.router._invoke_general_with_usage",
            new=AsyncMock(return_value="General answer"),
        ):
            answer_tokens: list[str] = []
            async for token in router.run("stock?", history=[]):
                answer_tokens.append(token)
            answer = "".join(answer_tokens)

        self.assertEqual(answer, "General answer")
        self.assertIsNotNone(router.route_metadata)
        assert router.route_metadata is not None
        self.assertEqual(router.route_metadata.predicted_route, "inventory")
        self.assertEqual(router.route_metadata.executed_route, "general")

    def test_message_mentions_stock_backed_invoice(self) -> None:
        self.assertTrue(
            message_mentions_stock_backed_invoice("Create an invoice for 2x SKU-1 from warehouse stock")
        )
        self.assertTrue(
            message_mentions_stock_backed_invoice("create invoice for 10 beers Bernard to Donka Barakova")
        )
        self.assertTrue(
            message_mentions_stock_backed_invoice("направи фактура към Донка Баракова за 10 бири Бернард")
        )
        self.assertFalse(message_mentions_stock_backed_invoice("How many iPhones do we have in stock?"))
        self.assertFalse(message_mentions_stock_backed_invoice("Show me the latest invoice for Acme Corp"))

    def test_infer_sales_invoice_prefill_extracts_partner_and_lines(self) -> None:
        prefill = infer_sales_invoice_prefill("Invoice 2x SKU-1 for Acme Corp")
        self.assertEqual(prefill.get("partner_query"), "Acme Corp")
        self.assertEqual(len(prefill.get("lines", [])), 1)
        self.assertEqual(prefill["lines"][0]["query"], "SKU-1")
        self.assertEqual(prefill["lines"][0]["quantity"], "2")

    def test_infer_sales_invoice_prefill_extracts_bulgarian_partner_and_line(self) -> None:
        prefill = infer_sales_invoice_prefill("направи фактура към Донка Баракова за 10 бири Бернард")
        self.assertEqual(prefill.get("partner_query"), "Донка Баракова")
        self.assertEqual(len(prefill.get("lines", [])), 1)
        self.assertEqual(prefill["lines"][0]["query"], "бири Бернард")
        self.assertEqual(prefill["lines"][0]["quantity"], "10")

    def test_infer_sales_invoice_prefill_extracts_english_partner_after_product_line(self) -> None:
        prefill = infer_sales_invoice_prefill("create invoice for 10 beers Bernard to Donka Barakova")
        self.assertEqual(prefill.get("partner_query"), "Donka Barakova")
        self.assertEqual(len(prefill.get("lines", [])), 1)
        self.assertEqual(prefill["lines"][0]["query"], "beers Bernard")
        self.assertEqual(prefill["lines"][0]["quantity"], "10")

    def test_resolve_sales_invoice_workflow_prefill_requires_high_confidence(self) -> None:
        self.assertIsNone(
            _resolve_sales_invoice_workflow_prefill(
                message="Create invoice for stock items",
                predicted_route="accountant",
                confidence=0.5,
                classifier_prefill=None,
            )
        )

    def test_resolve_sales_invoice_workflow_prefill_uses_classifier_data(self) -> None:
        prefill = _resolve_sales_invoice_workflow_prefill(
            message="Create invoice",
            predicted_route="accountant",
            confidence=0.92,
            classifier_prefill=SalesInvoiceClassifierPrefill(
                partner_query="Acme",
                lines=[SalesInvoicePrefillLine(query="SKU-1", quantity="2")],
            ),
        )
        self.assertIsNotNone(prefill)
        assert prefill is not None
        self.assertEqual(prefill.get("partner_query"), "Acme")
        self.assertEqual(prefill["lines"][0]["query"], "SKU-1")

    def test_resolve_sales_invoice_workflow_prefill_treats_classifier_object_as_intent(self) -> None:
        prefill = _resolve_sales_invoice_workflow_prefill(
            message="Create invoice",
            predicted_route="accountant",
            confidence=0.92,
            classifier_prefill=SalesInvoiceClassifierPrefill(),
        )
        self.assertEqual(prefill, {"lines": []})

    async def test_router_sets_workflow_suggestion_for_stock_backed_invoice(self) -> None:
        router = RouterAgent(
            fake_router_agent(company_id="company-1"),
            FakeListChatModel(responses=["unused"]),
            "user-1",
            object(),
        )
        router.configure_children(
            accountant_runtime=FakeRuntime(tokens=["I can help with that invoice."]),
            inventory_runtime=None,
        )

        with patch(
            "app.runtime.router.classify_route",
            new=AsyncMock(
                return_value=RouterDecision(
                    route="accountant",
                    reason="User asked to invoice stock items.",
                    confidence=0.92,
                    sales_invoice_workflow=SalesInvoiceClassifierPrefill(
                        partner_query="Acme",
                        lines=[SalesInvoicePrefillLine(query="SKU-1", quantity="2")],
                    ),
                )
            ),
        ):
            emitted_tokens: list[str] = []
            async for token in router.run("Create invoice for 2x SKU-1 for Acme", history=[]):
                emitted_tokens.append(token)
        self.assertEqual(emitted_tokens, ["I can help with that invoice."])

        self.assertIsNotNone(router.workflow_suggestion)
        assert router.workflow_suggestion is not None
        self.assertEqual(router.workflow_suggestion["workflow"], "sales_invoice_inventory")
        self.assertEqual(router.workflow_suggestion["confidence"], 0.92)
        self.assertEqual(router.workflow_suggestion["prefill"]["partner_query"], "Acme")

    async def test_router_drains_child_usage_events(self) -> None:
        router = RouterAgent(
            fake_router_agent(company_id="company-1"),
            FakeListChatModel(responses=["unused"]),
            "user-1",
            object(),
        )
        router.configure_children(
            accountant_runtime=None,
            inventory_runtime=FakeRuntime(
                tokens=["done"],
                usage_events=[fake_usage_event(agent_id="delegate-inventory-1")],
            ),
        )

        with patch(
            "app.runtime.router.classify_route",
            new=AsyncMock(return_value=RouterDecision(route="inventory", reason="stock", confidence=0.95)),
        ):
            emitted_tokens: list[str] = []
            async for token in router.run("stock?", history=[]):
                emitted_tokens.append(token)
        self.assertEqual(emitted_tokens, ["done"])

        usage = router.consume_usage_events()
        self.assertEqual(len(usage), 1)
        self.assertEqual(usage[0].agent_id, "delegate-inventory-1")


if __name__ == "__main__":
    unittest.main()
