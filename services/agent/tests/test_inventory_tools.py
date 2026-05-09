from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.shared.agent import AgentConfig, AgentInDB
from app.models.inventory import (
    InventoryCategoryListResponse,
    InventoryCategorySummary,
    InventoryOverviewResponse,
    InventoryImportResult,
    InventoryLocationListResponse,
    InventoryItemResponse,
    InventoryLocationResponse,
    InventorySearchMatch,
    InventorySearchResponse,
    ResolveInventoryItemResponse,
    StockLevel,
    StockLevelListResponse,
    StockMovementResponse,
)
from app.runtime.inventory import InventoryAgent
from app.runtime.hooks import AgentRunEvent
from app.runtime.tool_context import ToolContext
from app.tools.inventory import (
    build_inventory_import_tools,
    build_inventory_read_tools,
    build_inventory_write_tools,
)
from app.tools.inventory.import_tools import build_inventory_import_tools as build_inventory_import_tools_split
from app.tools.inventory.operations import (
    build_inventory_import_tools as build_inventory_import_tools_ops,
    build_inventory_read_tools as build_inventory_read_tools_ops,
    build_inventory_write_tools as build_inventory_write_tools_ops,
)
from app.tools.inventory.read_tools import build_inventory_read_tools as build_inventory_read_tools_split
from app.tools.inventory.write_tools import build_inventory_write_tools as build_inventory_write_tools_split


def _make_context(business_mock: AsyncMock) -> ToolContext:
    return ToolContext(
        business_client=business_mock,
        companybook_service=MagicMock(),
        knowledge_http=MagicMock(),
    )


async def _invoke_and_capture_error(tool: object, payload: dict[str, object]) -> str:
    try:
        result = await tool.ainvoke(payload)
    except Exception as exc:  # pragma: no cover - exception type depends on LangChain version
        return str(exc)
    return str(result)


class InventoryReadToolTests(unittest.IsolatedAsyncioTestCase):
    def test_inventory_builder_exports_resolve_to_split_modules(self) -> None:
        self.assertIs(build_inventory_read_tools, build_inventory_read_tools_split)
        self.assertIs(build_inventory_read_tools, build_inventory_read_tools_ops)
        self.assertIs(build_inventory_write_tools, build_inventory_write_tools_split)
        self.assertIs(build_inventory_write_tools, build_inventory_write_tools_ops)
        self.assertIs(build_inventory_import_tools, build_inventory_import_tools_split)
        self.assertIs(build_inventory_import_tools, build_inventory_import_tools_ops)

    async def test_search_inventory_stock_delegates_to_client(self) -> None:
        mock_client = AsyncMock()
        mock_client.search_inventory.return_value = InventorySearchResponse(
            query="iphones",
            normalized_query="iphones",
            matches=[
                InventorySearchMatch(
                    item_id="item-1",
                    name="iPhone 15",
                    sku="IP15",
                    unit="pcs",
                    confidence=0.95,
                    match_reason="text",
                    available_quantity=10,
                )
            ],
            total_available_quantity=10,
            message=None,
        )
        context = _make_context(mock_client)
        tools = build_inventory_read_tools("user-1", "company-1", context)
        search_tool = next(tool for tool in tools if tool.name == "search_inventory_stock")

        result = await search_tool.ainvoke({"query": "iphones"})

        mock_client.search_inventory.assert_awaited_once()
        payload = json.loads(result)
        self.assertEqual(payload["matches"][0]["name"], "iPhone 15")

    async def test_search_inventory_stock_blocks_duplicate_query_in_same_turn(self) -> None:
        mock_client = AsyncMock()
        mock_client.search_inventory.return_value = InventorySearchResponse(
            query="iphones",
            normalized_query="iphones",
            matches=[],
            total_available_quantity=None,
            message="No inventory items matched this query.",
        )
        context = _make_context(mock_client)
        tools = build_inventory_read_tools("user-1", "company-1", context, repeated_search_queries=set())
        search_tool = next(tool for tool in tools if tool.name == "search_inventory_stock")

        first_result = await search_tool.ainvoke({"query": "iPhones"})
        second_result = await search_tool.ainvoke({"query": " iphones  "})

        self.assertIn('"normalized_query": "iphones"', first_result)
        self.assertIn("already used in this turn", second_result)
        mock_client.search_inventory.assert_awaited_once()

    async def test_resolve_inventory_item_delegates_to_client(self) -> None:
        mock_client = AsyncMock()
        mock_client.resolve_inventory_item.return_value = ResolveInventoryItemResponse(
            query="SKU-001",
            normalized_query="sku-001",
            exact_match=InventorySearchMatch(
                item_id="item-1",
                name="Widget",
                sku="SKU-001",
                unit="pcs",
                confidence=1.0,
                match_reason="sku",
            ),
            candidates=[],
            message=None,
        )
        context = _make_context(mock_client)
        tools = build_inventory_read_tools("user-1", "company-1", context)
        resolve_tool = next(tool for tool in tools if tool.name == "resolve_inventory_item")

        result = await resolve_tool.ainvoke({"query": "SKU-001"})

        payload = json.loads(result)
        self.assertEqual(payload["exact_match"]["item_id"], "item-1")
        mock_client.resolve_inventory_item.assert_awaited_once()

    async def test_search_inventory_stock_rejects_blank_query(self) -> None:
        mock_client = AsyncMock()
        context = _make_context(mock_client)
        tools = build_inventory_read_tools("user-1", "company-1", context)
        search_tool = next(tool for tool in tools if tool.name == "search_inventory_stock")

        result = await search_tool.ainvoke({"query": ""})

        self.assertIn("requires a non-empty query", result)
        mock_client.search_inventory.assert_not_awaited()

    async def test_get_stock_levels_filters_by_min_available_quantity(self) -> None:
        mock_client = AsyncMock()
        mock_client.get_stock_levels.return_value = StockLevelListResponse(
            total_stock_level_count=1,
            unique_item_count=1,
            returned_count=1,
            offset=0,
            limit=50,
            truncated=False,
            next_offset=None,
            levels=[
                StockLevel(
                    item_id="item-2",
                    item_name="High stock item",
                    item_sku="HIGH",
                    location_id="loc-1",
                    location_name="Default",
                    available_quantity=50,
                    unit="pcs",
                )
            ],
        )
        context = _make_context(mock_client)
        tools = build_inventory_read_tools("user-1", "company-1", context)
        stock_tool = next(tool for tool in tools if tool.name == "get_stock_levels")

        result = await stock_tool.ainvoke({"min_available_quantity": 45})

        payload = json.loads(result)
        self.assertEqual(payload["total_stock_level_count"], 1)
        self.assertEqual(payload["unique_item_count"], 1)
        self.assertFalse(payload["truncated"])
        self.assertEqual([level["item_name"] for level in payload["levels"]], ["High stock item"])
        call_kwargs = mock_client.get_stock_levels.await_args.kwargs
        self.assertEqual(call_kwargs["min_available_quantity"], 45)
        self.assertEqual(call_kwargs["limit"], 50)

    async def test_get_stock_levels_caps_large_results(self) -> None:
        mock_client = AsyncMock()
        mock_client.get_stock_levels.return_value = StockLevelListResponse(
            total_stock_level_count=5,
            unique_item_count=5,
            returned_count=2,
            offset=0,
            limit=2,
            truncated=True,
            next_offset=2,
            levels=[
                StockLevel(
                    item_id="item-4",
                    item_name="Item 4",
                    item_sku="SKU-4",
                    location_id="loc-1",
                    location_name="Default",
                    available_quantity=4,
                    unit="pcs",
                ),
                StockLevel(
                    item_id="item-3",
                    item_name="Item 3",
                    item_sku="SKU-3",
                    location_id="loc-1",
                    location_name="Default",
                    available_quantity=3,
                    unit="pcs",
                ),
            ],
        )
        context = _make_context(mock_client)
        tools = build_inventory_read_tools("user-1", "company-1", context)
        stock_tool = next(tool for tool in tools if tool.name == "get_stock_levels")

        result = await stock_tool.ainvoke({"limit": 2})

        payload = json.loads(result)
        self.assertEqual(payload["total_stock_level_count"], 5)
        self.assertEqual(payload["unique_item_count"], 5)
        self.assertEqual(payload["returned_count"], 2)
        self.assertTrue(payload["truncated"])
        self.assertEqual([level["available_quantity"] for level in payload["levels"]], ["4", "3"])

    async def test_list_inventory_categories_returns_facet_payload(self) -> None:
        mock_client = AsyncMock()
        mock_client.list_inventory_categories.return_value = InventoryCategoryListResponse(
            total_category_count=2,
            uncategorized_item_count=1,
            categories=[
                InventoryCategorySummary(category="beverages", item_count=3, active_item_count=2),
                InventoryCategorySummary(category="snacks", item_count=1, active_item_count=1),
            ],
        )
        context = _make_context(mock_client)
        tools = build_inventory_read_tools("user-1", "company-1", context)
        categories_tool = next(tool for tool in tools if tool.name == "list_inventory_categories")

        result = await categories_tool.ainvoke({})

        payload = json.loads(result)
        self.assertEqual(payload["total_category_count"], 2)
        self.assertEqual(payload["uncategorized_item_count"], 1)
        self.assertEqual(payload["categories"][0]["category"], "beverages")
        mock_client.list_inventory_categories.assert_awaited_once()

    async def test_get_inventory_overview_returns_totals(self) -> None:
        mock_client = AsyncMock()
        mock_client.get_inventory_overview.return_value = InventoryOverviewResponse(
            total_item_count=12,
            active_item_count=10,
            inactive_item_count=2,
            category_count=4,
            location_count=3,
            low_stock_count=2,
            negative_stock_count=1,
        )
        context = _make_context(mock_client)
        tools = build_inventory_read_tools("user-1", "company-1", context)
        overview_tool = next(tool for tool in tools if tool.name == "get_inventory_overview")

        result = await overview_tool.ainvoke({})

        payload = json.loads(result)
        self.assertEqual(payload["total_item_count"], 12)
        self.assertEqual(payload["low_stock_count"], 2)
        mock_client.get_inventory_overview.assert_awaited_once()

    async def test_read_tool_rejects_extra_fields(self) -> None:
        mock_client = AsyncMock()
        context = _make_context(mock_client)
        tools = build_inventory_read_tools("user-1", "company-1", context)
        stock_tool = next(tool for tool in tools if tool.name == "get_stock_levels")

        error_text = await _invoke_and_capture_error(stock_tool, {"unexpected": "value"})

        self.assertTrue("unexpected" in error_text.lower() or "extra" in error_text.lower())
        mock_client.get_stock_levels.assert_not_awaited()


class InventoryWriteToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_item_requires_confirmation(self) -> None:
        mock_client = AsyncMock()
        context = _make_context(mock_client)
        tools = build_inventory_write_tools("user-1", "company-1", context)
        create_tool = next(tool for tool in tools if tool.name == "create_inventory_item")

        result = await create_tool.ainvoke(
            {
                "sku": "SKU-001",
                "name": "Widget",
                "unit": "pcs",
                "confirmed": False,
            }
        )

        self.assertIn("Confirmation required", result)
        mock_client.create_inventory_item.assert_not_awaited()

    async def test_create_item_persists_when_confirmed(self) -> None:
        mock_client = AsyncMock()
        mock_client.create_inventory_item.return_value = InventoryItemResponse(
            id="item-1",
            user_id="user-1",
            company_id="company-1",
            sku="SKU-001",
            name="Widget",
            unit="pcs",
        )
        context = _make_context(mock_client)
        tools = build_inventory_write_tools("user-1", "company-1", context)
        create_tool = next(tool for tool in tools if tool.name == "create_inventory_item")

        result = await create_tool.ainvoke(
            {
                "sku": "SKU-001",
                "name": "Widget",
                "unit": "pcs",
                "confirmed": True,
            }
        )

        mock_client.create_inventory_item.assert_awaited_once()
        self.assertIn("SKU-001", result)

    async def test_record_movement_requires_confirmation(self) -> None:
        mock_client = AsyncMock()
        context = _make_context(mock_client)
        tools = build_inventory_write_tools("user-1", "company-1", context)
        movement_tool = next(tool for tool in tools if tool.name == "record_stock_movement")

        result = await movement_tool.ainvoke(
            {
                "item_id": "item-1",
                "location_id": "loc-1",
                "movement_type": "receipt",
                "quantity_delta": "10",
                "confirmed": False,
            }
        )

        self.assertIn("Confirmation required", result)
        mock_client.create_stock_movement.assert_not_awaited()

    async def test_record_movement_persists_when_confirmed(self) -> None:
        mock_client = AsyncMock()
        mock_client.create_stock_movement.return_value = StockMovementResponse(
            id="move-1",
            user_id="user-1",
            company_id="company-1",
            item_id="item-1",
            location_id="loc-1",
            movement_type="receipt",
            quantity_delta="10",
        )
        context = _make_context(mock_client)
        tools = build_inventory_write_tools("user-1", "company-1", context)
        movement_tool = next(tool for tool in tools if tool.name == "record_stock_movement")

        result = await movement_tool.ainvoke(
            {
                "item_id": "item-1",
                "location_id": "loc-1",
                "movement_type": "receipt",
                "quantity_delta": "10",
                "confirmed": True,
            }
        )

        mock_client.create_stock_movement.assert_awaited_once()
        self.assertIn("move-1", result)

    async def test_record_movement_uses_default_location_when_location_missing(self) -> None:
        mock_client = AsyncMock()
        mock_client.list_inventory_locations.return_value = InventoryLocationListResponse(
            total_count=2,
            returned_count=2,
            offset=0,
            limit=100,
            truncated=False,
            next_offset=None,
            locations=[
                InventoryLocationResponse(
                    id="loc-1",
                    user_id="user-1",
                    company_id="company-1",
                    name="Secondary",
                    is_default=False,
                ),
                InventoryLocationResponse(
                    id="loc-default",
                    user_id="user-1",
                    company_id="company-1",
                    name="Default",
                    is_default=True,
                ),
            ],
        )
        mock_client.create_stock_movement.return_value = StockMovementResponse(
            id="move-1",
            user_id="user-1",
            company_id="company-1",
            item_id="item-1",
            location_id="loc-default",
            movement_type="receipt",
            quantity_delta="10",
        )
        context = _make_context(mock_client)
        tools = build_inventory_write_tools("user-1", "company-1", context)
        movement_tool = next(tool for tool in tools if tool.name == "record_stock_movement")

        await movement_tool.ainvoke(
            {
                "item_id": "item-1",
                "movement_type": "receipt",
                "quantity_delta": "10",
                "confirmed": True,
            }
        )

        mock_client.list_inventory_locations.assert_awaited_once()
        mock_client.create_stock_movement.assert_awaited_once()
        payload = mock_client.create_stock_movement.await_args.args[1]
        self.assertEqual(payload.location_id, "loc-default")

    async def test_record_movement_returns_error_when_locations_missing(self) -> None:
        mock_client = AsyncMock()
        mock_client.list_inventory_locations.return_value = InventoryLocationListResponse(
            total_count=0,
            returned_count=0,
            offset=0,
            limit=100,
            truncated=False,
            next_offset=None,
            locations=[],
        )
        context = _make_context(mock_client)
        tools = build_inventory_write_tools("user-1", "company-1", context)
        movement_tool = next(tool for tool in tools if tool.name == "record_stock_movement")

        result = await movement_tool.ainvoke(
            {
                "item_id": "item-1",
                "movement_type": "receipt",
                "quantity_delta": "10",
                "confirmed": True,
            }
        )

        self.assertIn("No inventory locations found", result)
        mock_client.create_stock_movement.assert_not_awaited()

    async def test_write_tool_rejects_extra_fields(self) -> None:
        mock_client = AsyncMock()
        context = _make_context(mock_client)
        tools = build_inventory_write_tools("user-1", "company-1", context)
        create_tool = next(tool for tool in tools if tool.name == "create_inventory_item")

        error_text = await _invoke_and_capture_error(
            create_tool,
            {
                "sku": "SKU-001",
                "name": "Widget",
                "unit": "pcs",
                "confirmed": False,
                "unexpected": "value",
            },
        )

        self.assertTrue("unexpected" in error_text.lower() or "extra" in error_text.lower())
        mock_client.create_inventory_item.assert_not_awaited()


class InventoryImportToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_confirm_import_preview_requires_confirmation(self) -> None:
        mock_client = AsyncMock()
        context = _make_context(mock_client)
        tools = build_inventory_import_tools("user-1", "company-1", context)
        confirm_tool = next(tool for tool in tools if tool.name == "confirm_import_preview")

        result = await confirm_tool.ainvoke({"preview_id": "preview-1", "confirmed": False})

        self.assertIn("Confirmation required", result)
        mock_client.confirm_import_preview.assert_not_awaited()

    async def test_confirm_import_preview_persists_when_confirmed(self) -> None:
        mock_client = AsyncMock()
        mock_client.confirm_import_preview.return_value = InventoryImportResult(
            preview_id="preview-1",
            items_created=2,
            items_updated=1,
            movements_created=3,
        )
        context = _make_context(mock_client)
        tools = build_inventory_import_tools("user-1", "company-1", context)
        confirm_tool = next(tool for tool in tools if tool.name == "confirm_import_preview")

        result = await confirm_tool.ainvoke({"preview_id": "preview-1", "confirmed": True})

        mock_client.confirm_import_preview.assert_awaited_once()
        payload = json.loads(result)
        self.assertEqual(payload["items_created"], 2)

    async def test_import_tool_rejects_extra_fields(self) -> None:
        mock_client = AsyncMock()
        context = _make_context(mock_client)
        tools = build_inventory_import_tools("user-1", "company-1", context)
        confirm_tool = next(tool for tool in tools if tool.name == "confirm_import_preview")

        error_text = await _invoke_and_capture_error(
            confirm_tool,
            {"preview_id": "preview-1", "confirmed": True, "unexpected": "value"},
        )

        self.assertTrue("unexpected" in error_text.lower() or "extra" in error_text.lower())
        mock_client.confirm_import_preview.assert_not_awaited()


class InventoryAgentRuntimeTests(unittest.TestCase):
    def test_inventory_agent_has_expected_tool_names(self) -> None:
        agent_in_db = AgentInDB(
            id="agent-1",
            user_id="user-1",
            name="Inv Agent",
            description=None,
            agent_type="inventory",
            company_id="company-1",
            config=AgentConfig(),
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        context = _make_context(AsyncMock())
        runtime = InventoryAgent(
            agent=agent_in_db,
            llm=MagicMock(),
            user_id="user-1",
            tool_context=context,
        )

        tools = runtime.get_tools()
        tool_names = {tool.name for tool in tools}

        expected = {
            "get_inventory_overview",
            "get_reorder_report",
            "list_stock_by_category",
            "list_negative_stock_items",
            "get_inventory_item_details",
            "get_inventory_movement_summary",
            "search_inventory_stock",
            "resolve_inventory_item",
            "list_inventory_categories",
            "list_inventory_items",
            "get_stock_levels",
            "list_low_stock_items",
            "get_stock_movements",
            "list_inventory_locations",
            "create_inventory_item",
            "update_inventory_item",
            "record_stock_movement",
            "list_import_previews",
            "get_import_preview",
            "confirm_import_preview",
            "cancel_import_preview",
            "calculator",
            "date_helper",
            "rag_search",
        }
        self.assertTrue(expected.issubset(tool_names), f"Missing: {expected - tool_names}")

    def test_inventory_agent_does_not_include_company_tools_when_assigned(self) -> None:
        agent_in_db = AgentInDB(
            id="agent-1",
            user_id="user-1",
            name="Inv Agent",
            description=None,
            agent_type="inventory",
            company_id="company-1",
            config=AgentConfig(),
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        context = _make_context(AsyncMock())
        runtime = InventoryAgent(
            agent=agent_in_db,
            llm=MagicMock(),
            user_id="user-1",
            tool_context=context,
        )

        tool_names = {tool.name for tool in runtime.get_tools()}
        self.assertNotIn("list_companies", tool_names)
        self.assertNotIn("resolve_company_by_name", tool_names)

    def test_inventory_agent_includes_company_tools_when_unassigned(self) -> None:
        agent_in_db = AgentInDB(
            id="agent-1",
            user_id="user-1",
            name="Inv Agent",
            description=None,
            agent_type="inventory",
            company_id=None,
            config=AgentConfig(),
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        context = _make_context(AsyncMock())
        runtime = InventoryAgent(
            agent=agent_in_db,
            llm=MagicMock(),
            user_id="user-1",
            tool_context=context,
        )

        tool_names = {tool.name for tool in runtime.get_tools()}
        self.assertIn("list_companies", tool_names)
        self.assertIn("resolve_company_by_name", tool_names)

    def test_system_prompt_mentions_confirmation(self) -> None:
        agent_in_db = AgentInDB(
            id="agent-1",
            user_id="user-1",
            name="Inv Agent",
            description=None,
            agent_type="inventory",
            company_id="company-1",
            config=AgentConfig(),
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        context = _make_context(AsyncMock())
        runtime = InventoryAgent(
            agent=agent_in_db,
            llm=MagicMock(),
            user_id="user-1",
            tool_context=context,
        )

        prompt = runtime.get_system_prompt()
        self.assertIn("confirmed=false", prompt)
        self.assertIn("confirmed=true", prompt)
        self.assertIn("stock issue movements", prompt.lower())


class InventoryAgentUiEventTests(unittest.IsolatedAsyncioTestCase):
    async def test_record_stock_movement_draft_emits_ui_event(self) -> None:
        agent_in_db = AgentInDB(
            id="agent-1",
            user_id="user-1",
            name="Inv Agent",
            description=None,
            agent_type="inventory",
            company_id="company-1",
            config=AgentConfig(),
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        context = _make_context(AsyncMock())
        runtime = InventoryAgent(
            agent=agent_in_db,
            llm=MagicMock(),
            user_id="user-1",
            tool_context=context,
        )
        raw_event = {
            "event": "on_tool_end",
            "name": "record_stock_movement",
            "run_id": "run-1",
            "data": {
                "output": json.dumps(
                    {
                        "message": "Confirmation required.",
                        "movement_draft": {
                            "company_id": "company-1",
                            "item_id": "item-1",
                            "location_id": "loc-1",
                            "movement_type": "receipt",
                            "quantity_delta": "10",
                            "reason": "restock",
                        },
                    }
                )
            },
        }

        await runtime.on_event(AgentRunEvent.from_raw(raw_event, {}))
        ui_events = runtime.consume_ui_events()

        self.assertEqual(len(ui_events), 1)
        event_name, payload = ui_events[0]
        self.assertEqual(event_name, "inventory_movement_draft")
        self.assertEqual(payload["movement_draft"]["item_id"], "item-1")


if __name__ == "__main__":
    unittest.main()
