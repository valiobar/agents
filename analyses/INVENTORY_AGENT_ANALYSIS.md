# Inventory Agent Analysis

## 1. Overview

This analysis reviews the Inventory Agent end-to-end: the agent runtime, LangChain tools, Business Service inventory APIs, MongoDB access patterns, and supporting docs. It focuses on why inventory chat behavior feels unreliable for normal business questions such as "list all categories", why searches can appear stuck, and what tools/API contracts should be added next.

Key files reviewed:

- `docs/architecture/overview.md`
- `docs/architecture/dependency-graph.md`
- `docs/services/agent/README.md`
- `docs/services/agent/architecture.md`
- `docs/services/agent/data-flow.md`
- `docs/services/business/README.md`
- `docs/services/business/architecture.md`
- `docs/services/business/data-flow.md`
- `docs/agents/inventory.md`
- `docs/data-models/agent.md`
- `docs/data-models/business.md`
- `services/agent/app/runtime/inventory.py`
- `services/agent/app/tools/inventory/read_tools.py`
- `services/agent/app/tools/inventory/write_tools.py`
- `services/agent/app/tools/inventory/import_tools.py`
- `services/agent/app/clients/business/inventory.py`
- `services/agent/app/runtime/base_agent.py`
- `services/agent/app/runtime/loop_logging.py`
- `services/agent/app/services/chat_service.py`
- `services/business/app/inventory/models.py`
- `services/business/app/inventory/routes/inventory_items.py`
- `services/business/app/inventory/routes/inventory_levels.py`
- `services/business/app/inventory/routes/inventory_search.py`
- `services/business/app/inventory/services/inventory_service.py`
- `services/business/app/inventory/services/inventory_search_service.py`
- `services/business/app/inventory/repositories/inventory_item_repo.py`
- `services/business/app/inventory/repositories/stock_movement_repo.py`
- `services/business/app/utils/db.py`
- `services/agent/tests/test_inventory_tools.py`

## 2. Architecture Context

The intended boundary is sound: the Agent Service owns chat runtime, tool orchestration, conversation persistence, and LLM provider behavior; the Business Service owns inventory data, validation, stock movement persistence, item search, stock-level derivation, and indexes.

The docs explicitly say Agent tools should call Business over HTTP through `BusinessClient`, not through copied repositories or direct MongoDB access. The current Inventory Agent generally follows that rule. `InventoryAgent.get_tools()` builds read/write/import tools and injects a Business-backed `ToolContext`; the tools call `context.business_client`; Business routes delegate to services, and services delegate to repositories.

The weak point is the semantic contract between the user, the LLM, and the tool set. The available tools are mostly low-level CRUD/query primitives: list items, search item text, get stock levels, list movements, list locations, and import preview operations. They do not cover common inventory reporting intents such as categories, inventory overview, stock by category, reorder report, stock valuation, stale items, negative stock, or top movers. The LLM is therefore forced to answer high-level questions by guessing from limited item lists or by choosing a nearby but wrong tool.

## 3. Findings

### Bugs

#### 1. Category and overview questions have no dedicated API or tool

**Problem:** The Inventory Agent cannot answer "list all categories" reliably because neither Agent nor Business exposes a category/facet endpoint. `list_inventory_items` can filter by one exact category, but it cannot return all categories or counts.

**Impact:** The model infers categories from a capped item list, which is exactly the wrong behavior for the screenshot case. If the first page contains only `peripherals`, the assistant can incorrectly claim every item belongs to that category.

**Evidence:**

```89:101:services/agent/app/tools/inventory/read_tools.py
class ListInventoryItemsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    category: str | None = Field(default=None, max_length=120, description="Exact category filter.")
    sku: str | None = Field(default=None, max_length=64, description="Exact SKU filter.")
    barcode: str | None = Field(default=None, max_length=128, description="Exact barcode filter.")
    is_active: bool | None = Field(default=None, description="Filter active/inactive items.")
    limit: int = Field(default=50, ge=1, le=100)
```

```29:48:services/business/app/inventory/routes/inventory_items.py
@router.get("", response_model=list[InventoryItemResponse])
async def list_items(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    company_id: Annotated[str, Query(min_length=1)],
    category: str | None = None,
    is_active: bool | None = None,
    sku: str | None = None,
    barcode: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    filters = InventoryItemFilters(
        company_id=company_id,
        category=category,
        is_active=is_active,
        sku=sku,
        barcode=barcode,
    )
    return await service.list_items(user_id, filters, limit, offset)
```

**Recommendation:** Add a Business endpoint and Agent tool:

- `GET /inventory/categories?company_id=...`
- Agent tool: `list_inventory_categories`
- Response shape:

```json
{
  "total_category_count": 3,
  "uncategorized_item_count": 2,
  "categories": [
    {"category": "peripherals", "item_count": 12, "active_item_count": 11},
    {"category": "phones", "item_count": 8, "active_item_count": 8}
  ]
}
```

Use Mongo aggregation grouped by `category`, scoped by `user_id + company_id`. This should be the first fix because it directly addresses a visible user failure.

#### 2. Stock-level tools can be slow because filtering and limits happen after full Business aggregation

**Problem:** The Agent tool exposes `limit`, `min_available_quantity`, and `max_available_quantity`, but Business does not accept these filters. The agent fetches all stock levels, filters in Python, sorts them, and only then caps output.

**Impact:** On larger inventories, the tool can look stuck. The LLM waits for Business to aggregate every stock level and for Agent to process all rows, even if the user asked for only the top 20 or a threshold count.

**Evidence:**

```207:226:services/agent/app/tools/inventory/read_tools.py
async def get_stock_levels(**kwargs) -> str:
    args = GetStockLevelsArgs.model_validate(kwargs)

    async def run(target_company_id: str) -> str:
        try:
            levels = await context.business_client.get_stock_levels(
                user_id,
                company_id=target_company_id,
                item_id=args.item_id,
                location_id=args.location_id,
                below_reorder_point=args.below_reorder_point,
            )
        except BusinessClientError as exc:
            return exc.message
        levels = _filter_stock_levels(
            levels,
            min_available_quantity=args.min_available_quantity,
            max_available_quantity=args.max_available_quantity,
        )
        return _json(_stock_levels_payload(levels, args.limit))
```

```14:29:services/business/app/inventory/routes/inventory_levels.py
@router.get("", response_model=list[StockLevel])
async def get_stock_levels(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    company_id: Annotated[str, Query(min_length=1)],
    item_id: str | None = None,
    location_id: str | None = None,
    below_reorder_point: bool = False,
):
    filters = StockLevelFilters(
        company_id=company_id,
        item_id=item_id,
        location_id=location_id,
        below_reorder_point=below_reorder_point,
    )
    return await service.get_stock_levels(user_id, filters)
```

**Recommendation:** Move stock-level filtering, sort, limit, and count metadata into Business:

- Extend `StockLevelFilters` with `min_available_quantity`, `max_available_quantity`, `limit`, `offset`, and maybe `sort_by`.
- Return a `StockLevelListResponse`, not a raw list:

```json
{
  "total_stock_level_count": 350,
  "unique_item_count": 140,
  "returned_count": 50,
  "truncated": true,
  "levels": []
}
```

The Agent tool should only forward arguments and format the already bounded response.

### Performance Issues

#### 3. Stock-level expansion has N+1 item and location reads

**Problem:** After aggregating stock movements, `InventoryService.get_stock_levels()` loads every referenced item and location one by one.

**Impact:** With many items/locations, a single stock-level question triggers many sequential MongoDB calls. This is likely one reason the agent often feels stuck during broad inventory queries.

**Evidence:**

```231:254:services/business/app/inventory/services/inventory_service.py
async def get_stock_levels(self, user_id: str, filters: StockLevelFilters) -> list[StockLevel]:
    await self.company_service.require_company(user_id, filters.company_id)
    raw_levels = await self.movement_repo.aggregate_levels_by_location(
        user_id=user_id,
        company_id=filters.company_id,
        item_id=filters.item_id,
        location_id=filters.location_id,
    )
    if not raw_levels:
        return []

    item_ids = list({str(level["item_id"]) for level in raw_levels})
    location_ids = list({str(level["location_id"]) for level in raw_levels})

    items_map = await self._load_items_map(user_id, filters.company_id, item_ids)
    locations_map = await self._load_locations_map(user_id, filters.company_id, location_ids)
```

```301:325:services/business/app/inventory/services/inventory_service.py
async def _load_items_map(
    self,
    user_id: str,
    company_id: str,
    item_ids: list[str],
) -> dict[str, InventoryItemInDB]:
    items_map: dict[str, InventoryItemInDB] = {}
    for item_id in item_ids:
        item = await self.item_repo.get_by_id(user_id, company_id, item_id)
        if item:
            items_map[item_id] = item
    return items_map

async def _load_locations_map(
    self,
    user_id: str,
    company_id: str,
    location_ids: list[str],
) -> dict[str, InventoryLocationInDB]:
    locations_map: dict[str, InventoryLocationInDB] = {}
    for location_id in location_ids:
        location = await self.location_repo.get_by_id(user_id, company_id, location_id)
        if location:
            locations_map[location_id] = location
    return locations_map
```

**Recommendation:** Add repository batch methods using `$in`:

- `InventoryItemRepository.get_many_by_ids(user_id, company_id, item_ids)`
- `InventoryLocationRepository.get_many_by_ids(user_id, company_id, location_ids)`

Then replace the loops with two queries. For larger deployments, consider doing the joins inside one aggregation pipeline with `$lookup`, but the batch method is the low-risk first step.

#### 4. Search fallback uses unindexed regex patterns that can degrade under load

**Problem:** `find_identifier_prefix_matches()` builds regex filters for `sku`, `name`, and `search_text`. Prefix regexes on indexed fields may be tolerable for `sku` and `name`, but token regex over `search_text` can become expensive as the collection grows.

**Impact:** Broad or repeated searches can get slower over time. This is especially risky because the LLM may retry similar searches when it receives empty or confusing results.

**Evidence:**

```349:388:services/business/app/inventory/repositories/inventory_item_repo.py
async def find_identifier_prefix_matches(
    self,
    base: dict,
    normalized: str,
    limit: int,
) -> list[InventorySearchMatch]:
    if not normalized:
        return []

    escaped = re.escape(normalized)
    or_filters: list[dict] = [
        {"sku": {_MONGO_REGEX: f"^{escaped}", _MONGO_OPTIONS: "i"}},
        {"name": {_MONGO_REGEX: f"^{escaped}", _MONGO_OPTIONS: "i"}},
        {
            "search_text": {
                _MONGO_REGEX: _search_text_token_prefix_regex(normalized),
                _MONGO_OPTIONS: "i",
            }
        }
    ]
```

**Recommendation:** Keep exact SKU/barcode lookup, but upgrade search to a clearer two-path design:

- `resolve_inventory_item` for exact or prefix identifiers, returning one or a small candidate set.
- `search_inventory_items_text` for item-name/alias search with bounded output and explicit no-match behavior.

If MongoDB Atlas Search is not available, precompute `search_tokens` and indexed prefix fields for common lookup tokens. If Atlas Search is available, move fuzzy/token ranking there.

### Missing Best Practices

#### 5. Tool outputs lack result metadata, so the model confuses "returned rows" with "all rows"

**Problem:** `list_inventory_items`, `list_low_stock_items`, `get_stock_movements`, and `list_inventory_locations` return raw arrays with no `total_count`, `returned_count`, `truncated`, or `next_offset`. `get_stock_levels` is better, but its counts are produced after full in-memory processing.

**Impact:** The assistant can overstate what it knows. For example, a 50-row item list can be treated as the full inventory. The user then receives confident but wrong answers.

**Evidence:**

```187:203:services/agent/app/tools/inventory/read_tools.py
async def list_inventory_items(**kwargs) -> str:
    args = ListInventoryItemsArgs.model_validate(kwargs)

    async def run(target_company_id: str) -> str:
        try:
            items = await context.business_client.list_inventory_items(
                user_id,
                company_id=target_company_id,
                category=args.category,
                sku=args.sku,
                barcode=args.barcode,
                is_active=args.is_active,
                limit=args.limit,
            )
        except BusinessClientError as exc:
            return exc.message
        return _json([item.model_dump(mode="json") for item in items])
```

**Recommendation:** Standardize list tool responses:

```json
{
  "total_count": 124,
  "returned_count": 50,
  "limit": 50,
  "offset": 0,
  "truncated": true,
  "items": []
}
```

Business should own `total_count` because only Business can count accurately without transferring all data. The agent prompt should explicitly say: if `truncated=true`, do not claim the list is complete.

#### 6. Empty search results do not give the LLM enough guidance to stop retrying

**Problem:** Search returns a valid empty response, but it does not include normalized query, suggestions, or an instruction that the search was exhausted. The agent prompt only says not to call `search_inventory_stock` with an empty query.

**Impact:** An LLM can loop through variants of the same search until `MAX_AGENT_ITERATIONS` is reached, making the chat feel stuck.

**Evidence:**

```42:53:services/business/app/inventory/services/inventory_search_service.py
filtered_matches = [match for match in matches if match.confidence >= payload.min_confidence]

total_available_quantity: Decimal | None = None
if payload.include_stock and filtered_matches:
    total_available_quantity = sum(
        (match.available_quantity or Decimal("0")) for match in filtered_matches
    )

return InventorySearchResponse(
    matches=filtered_matches,
    total_available_quantity=total_available_quantity,
)
```

```140:144:services/agent/app/runtime/base_agent.py
executor = AgentExecutor(
    agent=agent,
    tools=tools,
    max_iterations=settings.max_agent_iterations,
)
```

**Recommendation:** Add a small per-turn search retry guard for inventory search, similar in spirit to the RAG repeat guard described in docs. At minimum, return tool text like:

```json
{
  "matches": [],
  "query": "iphoness",
  "normalized_query": "iphoness",
  "message": "No inventory items matched this query. Do not retry the same or near-identical query; ask the user for SKU/barcode or use list_inventory_items for exact filters."
}
```

For better behavior, implement `InventoryAgent.prepare_run_input()` or tool-local memory to block repeated near-identical `search_inventory_stock` calls within one turn.

#### 7. Most tool argument schemas still allow silent extra fields

**Problem:** `SearchInventoryStockArgs` and `ListInventoryItemsArgs` now forbid unknown fields, but write/import/stock-level/movement/location schemas still use Pydantic defaults, which ignore extra arguments.

**Impact:** If the model passes wrong fields, the tool may ignore them and proceed with a broader operation than intended. This is bad for correctness and dangerous for write workflows, even though writes require confirmation.

**Evidence:**

```21:41:services/agent/app/tools/inventory/write_tools.py
class CreateInventoryItemArgs(BaseModel):
    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=120)
    barcode: str | None = Field(default=None, max_length=128)
    aliases: list[str] = Field(default_factory=list)
    unit: str = Field(min_length=1, max_length=32)
    selling_price: Decimal | None = Field(default=None, ge=0)
    reorder_point: Decimal | None = Field(default=None, ge=0)
    target_stock_level: Decimal | None = Field(default=None, ge=0)
    supplier_partner_id: str | None = Field(default=None, max_length=64)
    confirmed: bool = Field(
        default=False,
        description="Must be true only after the user explicitly confirms item creation.",
    )
```

**Recommendation:** Add `model_config = ConfigDict(extra="forbid")` to all inventory tool argument models. This makes wrong tool calls fail loudly and gives the model a chance to correct itself instead of silently broadening reads or draft writes.

### Inconsistencies

#### 8. Inventory documentation overpromises "category search" compared with the real tool behavior

**Problem:** The docs say inventory supports search by "category", but the implemented free-text search and exact category list are different behaviors. A user asking for categories needs a category facet; a user asking for items in one category needs exact filtering; a user asking "find chargers" needs text search. These are currently blurred.

**Impact:** Tool names and docs can mislead future maintainers and the model prompt. This creates the exact class of wrong answers seen in the UI.

**Evidence:**

```21:24:docs/agents/inventory.md
## Supported Workflows

- Search inventory items by natural language, SKU, barcode, category, or alias.
- Check current stock levels per item and location.
```

```66:70:services/agent/app/runtime/inventory.py
"Use search_inventory_stock for natural-language item queries like 'how many iPhones "
"do we have?', 'find iPhones', or SKU/barcode/name lookups where the user gives search text. "
"Use list_inventory_items only for structured listing with exact filters such as category, "
"SKU, barcode, or active status. "
"Use get_stock_levels to check current quantities. "
```

**Recommendation:** Update docs and prompt once new tools exist:

- "Use `list_inventory_categories` for all category/facet/count questions."
- "Use `list_inventory_items` for exact item listing filters."
- "Use `search_inventory_stock` only for item lookup by text or identifier."

### Missing Best Practices

#### 9. Runtime observability is useful in logs but not enough for product debugging

**Problem:** Development logs show tool events, but the UI only receives final tokens and a specific `inventory_movement_draft` event. For debugging LLM tool choice, users have to inspect service logs.

**Impact:** It is hard to answer "why did the agent say this?" from the UI. This slows iteration on prompts and tools.

**Evidence:**

```81:101:services/agent/app/runtime/loop_logging.py
def run_start(self, message: str, history_count: int, tool_names: list[str]) -> None:
    if settings.is_development:
        logger.info(
            "[agent.start] %s/%s user=%s history=%d tools=%s\n    input: %s",
            self.agent.agent_type,
            self.agent.id,
            self.user_id,
            history_count,
            tool_names,
            preview_log_value(message),
        )

def executor_ready(self) -> None:
    if settings.is_development:
        logger.info(
            "[agent.ready ] %s/%s user=%s max_iterations=%d",
            self.agent.agent_type,
            self.agent.id,
            self.user_id,
            settings.max_agent_iterations,
        )
```

```203:210:services/agent/app/services/chat_service.py
route_payload = self._route_metadata_payload(runtime)
if route_payload is not None:
    yield sse("route", route_payload)

for ui_event_name, ui_payload in runtime.consume_ui_events():
    yield sse(ui_event_name, ui_payload)

yield sse("done", {"conversation_id": conversation.id})
```

**Recommendation:** Add optional development-only `tool_trace` SSE events or a persisted debug trace for the last turn. Keep it disabled by default. Include tool name, sanitized args, duration, and truncated output size, not full sensitive payloads.

## 4. What Works Well

### 1. Service boundaries are mostly correct

**Pattern:** Agent tools call Business through `BusinessClient`, and Business owns validation/persistence.

```190:203:services/agent/app/tools/inventory/read_tools.py
try:
    items = await context.business_client.list_inventory_items(
        user_id,
        company_id=target_company_id,
        category=args.category,
        sku=args.sku,
        barcode=args.barcode,
        is_active=args.is_active,
        limit=args.limit,
    )
except BusinessClientError as exc:
    return exc.message
return _json([item.model_dump(mode="json") for item in items])
```

**Why it works:** The chat tool path and public REST API path share Business validation and data ownership. This avoids duplicate business logic in Agent.

**Where else to apply:** New tools such as `list_inventory_categories`, `get_inventory_overview`, and `get_reorder_report` should be thin Agent wrappers over Business endpoints, not Agent-side MongoDB queries.

### 2. Write tools use confirmation drafts before persistence

**Pattern:** Inventory writes return a draft until `confirmed=true`.

```112:123:services/agent/app/tools/inventory/write_tools.py
if not args.confirmed:
    return _json(
        {
            "message": "Confirmation required. Present this item draft and ask the user to confirm.",
            "item_draft": payload.model_dump(mode="json"),
        }
    )
try:
    item = await context.business_client.create_inventory_item(user_id, payload)
except BusinessClientError as exc:
    return exc.message
return _json(item.model_dump(mode="json"))
```

**Why it works:** It reduces accidental writes from model guesses and gives the user a clear review step.

**Where else to apply:** Any future inventory write workflow, such as bulk import confirmation, transfer between locations, or reorder draft generation, should keep the same draft-then-confirm pattern.

### 3. Business indexing covers key inventory lookup paths

**Pattern:** Startup creates indexes for SKU uniqueness, barcode lookup, category filtering, aliases, text search, movements, and source idempotency.

```67:95:services/business/app/utils/db.py
await db["inventory_items"].create_index(
    [("user_id", ASCENDING), ("company_id", ASCENDING), ("sku", ASCENDING)],
    unique=True,
)
await db["inventory_items"].create_index(
    [("user_id", ASCENDING), ("company_id", ASCENDING), ("barcode", ASCENDING)],
    sparse=True,
)
await db["inventory_items"].create_index(
    [("user_id", ASCENDING), ("company_id", ASCENDING), ("is_active", ASCENDING), ("name", ASCENDING)]
)
await db["inventory_items"].create_index(
    [("user_id", ASCENDING), ("company_id", ASCENDING), ("category", ASCENDING)]
)
```

**Why it works:** It supports the current structured filters and protects important uniqueness invariants.

**Where else to apply:** Add matching indexes if new tools filter by supplier, stale movement date, negative stock, or category summary fields.

### 4. Search has a sensible layered fallback for exact IDs before text search

**Pattern:** Search first checks exact SKU/barcode/alias before falling back to text and prefix matching.

```321:347:services/business/app/inventory/repositories/inventory_item_repo.py
exact = await self.find_exact_identifier_or_alias(user_id, company_id, query)
if exact:
    return exact[:limit]

base = {"user_id": user_id, "company_id": company_id, "is_active": True}
normalized = normalize_text(query)
prefix = await self.find_identifier_prefix_matches(base, normalized, limit)
if prefix:
    return prefix

docs = (
    await self.collection.find(
        {**base, "$text": {"$search": normalized}},
        {"score": {_MONGO_META: "textScore"}},
    )
```

**Why it works:** Exact identifiers should beat fuzzy search, and the repository isolates the search algorithm from route/service code.

**Where else to apply:** Keep this resolver concept, but split it into an explicit `resolve_inventory_item` tool for write workflows that need IDs.

## 5. Summary - Priority Matrix

| # | Concern | Severity | Effort |
|---|---------|----------|--------|
| 1 | No category/facet tool, causing wrong answers to "list categories" | **High** | Medium |
| 2 | Stock-level limits and threshold filters happen after full retrieval | **High** | Medium |
| 3 | Stock-level expansion uses N+1 item/location reads | **High** | Medium |
| 4 | Search fallback regex can degrade as data grows | **Medium** | Medium |
| 5 | List tools lack total/truncation metadata | **Medium** | Medium |
| 6 | Empty search results do not prevent repeated near-identical searches | **Medium** | Low |
| 7 | Most inventory tool schemas still ignore extra fields | **Medium** | Low |
| 8 | Docs/prompt blur category search vs category listing vs item lookup | **Low** | Low |
| 9 | Tool-choice observability is log-only, not product-visible | **Low** | Medium |

## 6. Suggested Implementation Order

1. **Fix the visible category failure first**: add `list_inventory_categories` in Business and Agent. Update the Inventory Agent prompt and docs to use it for category/facet questions. This addresses Finding 1 and Finding 8.

2. **Make broad reads bounded and honest**: change Business list/level endpoints to return metadata (`total_count`, `returned_count`, `truncated`, `offset`, `limit`) and update Agent tools to preserve that metadata. This addresses Finding 2 and Finding 5.

3. **Remove the stock-level performance trap**: batch-load item and location maps, then push threshold filters/limits into Business. This addresses Finding 2 and Finding 3.

4. **Add high-value business reporting tools**:
   - `get_inventory_overview`: total items, active/inactive count, category count, location count, low-stock count, negative-stock count.
   - `get_reorder_report`: below reorder point, target stock, suggested reorder quantity, supplier id/name where available.
   - `list_stock_by_category`: category totals and stock quantities.
   - `list_negative_stock_items`: items/locations where available quantity is below zero.
   - `get_inventory_item_details`: one item with stock by location and recent movements.
   - `resolve_inventory_item`: exact SKU/barcode/name/alias resolver for write flows needing IDs.
   - `get_inventory_movement_summary`: receipts/issues/adjustments grouped by date range, item, or movement type.

5. **Improve search behavior**: return explicit no-match guidance and add a per-turn guard against repeated near-identical `search_inventory_stock` calls. Then evaluate whether to add Atlas Search or precomputed token fields for better fuzzy matching. This addresses Finding 4 and Finding 6.

6. **Harden tool schemas**: add `ConfigDict(extra="forbid")` to all inventory tool argument models. This addresses Finding 7.

7. **Add optional debug traces**: expose sanitized tool trace data in development so tool selection is visible without reading service logs. This addresses Finding 9.

