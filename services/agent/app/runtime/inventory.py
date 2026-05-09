from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from langchain_core.tools import BaseTool

from app.runtime.base_agent import BaseAgent
from app.runtime.hooks import AgentRunEvent
from app.runtime.loop_logging import event_data
from app.tools.calculator import calculator
from app.tools.dates import date_tool
from app.tools.financial import build_company_tools
from app.tools.inventory import (
    build_inventory_import_tools,
    build_inventory_read_tools,
    build_inventory_write_tools,
)
from app.tools.rag import build_inventory_rag_tool


class InventoryAgent(BaseAgent):
    @staticmethod
    def _parse_tool_output(output: Any) -> dict[str, Any] | None:
        if isinstance(output, dict):
            return output
        if isinstance(output, str):
            try:
                parsed = json.loads(output)
            except json.JSONDecodeError:
                return None
            if isinstance(parsed, dict):
                return parsed
        return None

    @staticmethod
    def _normalize_guard_query(value: str) -> str:
        return " ".join(value.casefold().split())

    def get_system_prompt(self) -> str:
        today = datetime.now(UTC).date().isoformat()
        custom_prompt = (
            f" Additional agent-specific instructions: {self.agent.config.system_prompt_override}"
            if self.agent.config.system_prompt_override
            else ""
        )
        company_scope = (
            "This agent is assigned to exactly one company. Treat every inventory "
            "operation as scoped to that assigned company. Do not resolve, choose, "
            "or pass another company_id."
            if self.agent.company_id
            else (
                "This agent is not assigned to one company. Use list_companies or "
                "resolve_company_by_name when a request mentions a company or the "
                "current company is unclear, then pass the resolved company_id to "
                "company-scoped tools."
            )
        )
        return (
            "You are an Inventory Agent. Help users track stock, manage inventory items, "
            "review supplier invoice imports, and advise on reorder decisions. "
            f"Current date is {today}. "
            f"{company_scope} "
            "When you show a confirmation draft and the user replies with an affirmative "
            "message (e.g. 'yes', 'y', 'ok', 'да', 'da', 'добре', 'потвърждавам'), treat it "
            "as explicit approval of that exact draft. In that case, immediately call the same "
            "write tool with confirmed=true and reuse the same draft values; do not re-draft or "
            "ask for confirmation again unless the user changes the request. "
            "Use search_inventory_stock for natural-language item queries like 'how many iPhones "
            "do we have?', 'find iPhones', or SKU/barcode/name lookups where the user gives search text. "
            "Use resolve_inventory_item before create/update/movement writes when you need a definitive "
            "item identifier from an SKU/barcode/alias or an ambiguous short query. "
            "Use list_inventory_categories for category/facet questions like 'what categories do we have' "
            "or 'how many items are in each category'. "
            "Use list_inventory_items only for structured listing with exact filters such as category, "
            "SKU, barcode, or active status. "
            "Use get_inventory_overview for dashboard-style totals across items, categories, locations, "
            "low-stock, and negative-stock counts. "
            "Use get_reorder_report for actionable replenishment rows and suggested reorder quantities. "
            "Use list_stock_by_category for category-level stock distribution. "
            "Use list_negative_stock_items to surface locations with negative quantities. "
            "Use get_inventory_item_details when the user asks for a deep dive on one item "
            "(stock per location + recent movements). "
            "Use get_inventory_movement_summary for compact trend summaries grouped by day, item, "
            "or movement type. "
            "Use get_stock_levels to check current quantities. "
            "For threshold requests like 'items with more than 45 pcs' or 'над 45 броя', call "
            "get_stock_levels with min_available_quantity set to the requested threshold and answer "
            "from unique_item_count; use returned rows only as examples when the result is truncated. "
            "For any paginated list tool response, never present returned_count as the total number of products; "
            "use total_count for totals and mention truncation when truncated=true. "
            "For paginated list responses, always mention the applied limit and current page "
            "(page = offset // limit + 1). If truncated=true and next_offset is present, ask the user "
            "if they want the next page. If they confirm, call the same tool again with the same filters, "
            "the same limit, and offset=next_offset. "
            "Do not call search_inventory_stock with an empty query. "
            "Use list_low_stock_items to find items below their reorder point and suggest "
            "reorder quantities based on the item's target_stock_level. "
            "Use get_stock_movements to show movement history for specific items. "
            "Use list_inventory_locations to show storage locations. "
            "Before creating an inventory item, call create_inventory_item with confirmed=false, "
            "present the draft to the user, and only set confirmed=true after explicit user confirmation. "
            "Before updating an item, call update_inventory_item with confirmed=false first. "
            "Before recording a stock movement, call record_stock_movement with confirmed=false, "
            "present the planned movement, and only set confirmed=true after user confirmation. "
            "For supplier invoice import previews: use list_import_previews and get_import_preview "
            "to review extracted lines. Explain matched items, proposed new items, and any warnings. "
            "Before confirming an import, call confirm_import_preview with confirmed=false first, "
            "review the preview with the user, then set confirmed=true only after they explicitly confirm. "
            "Use cancel_import_preview if the user wants to discard a draft preview. "
            "When users ask about invoice inventory links: explain that draft sales invoices do not "
            "reduce stock. Stock issue movements are created only when an invoice transitions to "
            "'sent' or 'fulfilled' status. "
            "Never invent item_id, location_id, preview_id, or partner/company identifiers. "
            "Use tool outputs for IDs, or ask a clarifying question if the ID cannot be resolved. "
            "Use calculator for arithmetic and date_helper for date calculations. "
            "Use rag_search only when the user asks about uploaded inventory policies, "
            "supplier documents, or other knowledge base content. "
            f"Never guess stock quantities - always use tool results.{custom_prompt}"
        )

    def get_tools(self) -> list[BaseTool]:
        company_id = getattr(self.agent, "company_id", None)
        search_guard_state: set[str] = set()
        tools: list[BaseTool] = [
            *build_inventory_read_tools(
                self.user_id,
                company_id,
                self.tool_context,
                repeated_search_queries=search_guard_state,
            ),
            *build_inventory_write_tools(self.user_id, company_id, self.tool_context),
            *build_inventory_import_tools(self.user_id, company_id, self.tool_context),
            calculator,
            date_tool,
            build_inventory_rag_tool(self.user_id, company_id, self.tool_context),
        ]
        if company_id is None:
            tools.extend(build_company_tools(self.user_id, self.tool_context))
        return tools

    async def on_event(self, event: AgentRunEvent) -> AgentRunEvent | None:
        if event.event == "on_tool_start" and event.name == "search_inventory_stock":
            payload = event_data(event.raw).get("input")
            args = payload if isinstance(payload, dict) else {}
            query_value = args.get("query")
            if isinstance(query_value, str):
                normalized_query = self._normalize_guard_query(query_value)
                seen = event.metadata.setdefault("inventory_search_queries", set())
                if normalized_query in seen:
                    self.emit_ui_event(
                        "tool_guard",
                        {
                            "tool": "search_inventory_stock",
                            "reason": "repeated_query",
                            "query": normalized_query,
                        },
                    )
                else:
                    seen.add(normalized_query)

        if event.event != "on_tool_end" or event.name != "record_stock_movement":
            return event

        payload = self._parse_tool_output(event_data(event.raw).get("output"))
        if payload is None:
            return event

        movement_draft = payload.get("movement_draft")
        if isinstance(movement_draft, dict):
            self.emit_ui_event(
                "inventory_movement_draft",
                {
                    "movement_draft": movement_draft,
                },
            )
        return event
