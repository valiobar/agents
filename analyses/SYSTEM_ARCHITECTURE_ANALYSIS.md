# System Architecture Analysis

## 1. Overview

A full-stack architectural audit of the AI Agent Platform covering all six services (Auth, Gateway, Agent, Business, Knowledge, Orchestrator), the Next.js frontend, Docker Compose configuration, and cross-service boundaries. The analysis identifies architecture violations, files that need splitting, inconsistencies, leftover refactoring artifacts, and maintainability concerns.

**Key areas under review:**

| Area | Key files/services |
|------|--------------------|
| Agent Service | `services/agent/app/` — models, tools, runtime, clients, services, routes, repositories |
| Business Service | `services/business/app/` — company, partner, financial, inventory domains |
| API Gateway | `gateway/app/routes/proxy.py` |
| Frontend | `frontend/src/` — FSD layers (app, widgets, features, entities, shared) |
| Infrastructure | `docker-compose.dev.yml`, dependency files |

**Docs consulted:** `docs/architecture/overview.md`, `docs/architecture/dependency-graph.md`, `docs/services/agent/architecture.md`, `docs/services/agent/data-flow.md`, `docs/services/business/architecture.md`, `docs/services/gateway/architecture.md`, `docs/frontend/architecture.md`, `docs/data-models/agent.md`, `docs/data-models/business.md`, `docs/api/README.md`.

---

## 2. Architecture Context

The platform uses a microservice architecture with 6 application services behind an API Gateway, MongoDB, Redis, and ChromaDB. Communication is HTTP-based. The documented layering rule for every service is `routes/ → services/ → repositories/ → models/`, with Agent adding `runtime/ → tools/ → clients/`. The frontend uses Feature-Sliced Design (FSD) with strict top-down imports: `app/ → widgets/ → features/ → entities/ → shared/`.

The system is mid-refactor: the Business Service split from Agent is active, and Agent's models and tools have been reorganized from monolith files into domain packages. Several compatibility shim files remain from this transition.

---

## 3. Findings

### Architecture Violations

#### Finding 1: FSD Violation — `shared/store/` imports from `entities/`

**Problem:** Two Zustand stores in `shared/` import types directly from `entities/`, violating the FSD rule that `shared/` (Layer 2) must never depend on `entities/` (Layer 3).

**Impact:** Breaks the strict top-down dependency graph. If `entities/invoice/model/types.ts` changes, `shared/store/` — which should be the most stable layer — must also change.

**Evidence:**

```
// frontend/src/shared/store/invoice-filters-store.ts:3
import type { InvoiceStatus } from "@/entities/invoice/model/types";

// frontend/src/shared/store/expense-filters-store.ts:3
import type { ExpenseCategory } from "@/entities/expense/model/types";
```

**Recommendation:** Move `InvoiceStatus` and `ExpenseCategory` type definitions to `shared/lib/types.ts` or `shared/model/domain-types.ts`, then have both `entities/` and `shared/store/` import from `shared/`. Alternatively, use plain string literal types in the stores and keep the branded types in entities.

---

#### Finding 2: FSD Violation — Feature-to-Feature Import

**Problem:** `features/send-message/model/receipt-expense-schema.ts` imports directly from `features/record-expense/model/schema.ts`. This violates the strict rule that features must never import from other features.

**Impact:** Creates a hidden coupling between two independent feature slices. Changes to the expense form schema now ripple into the chat-based receipt confirmation flow.

**Evidence:**

```
// frontend/src/features/send-message/model/receipt-expense-schema.ts:4
import { expenseCategorySchema } from "@/features/record-expense/model/schema";
```

**Recommendation:** Extract the shared `expenseCategorySchema` Zod schema into `shared/model/expense-categories.ts` or `entities/expense/model/schema.ts`. Both features then import from the lower layer.

---

#### Finding 3: Agent Service Retains `financial_utils.py` in Repositories

**Problem:** `services/agent/app/repositories/financial_utils.py` (82 lines) contains money quantization, BSON Decimal128 conversion, date-to-datetime helpers, and exchange rate constants. After the Business Service split, Agent should not own financial calculation logic — Business owns money arithmetic and persistence.

**Impact:** Duplicate financial logic across services. If exchange rates or rounding rules change, two files must be updated. The file also provides BSON conversion helpers that suggest Agent once wrote financial data directly to MongoDB.

**Evidence:**

```
// services/agent/app/repositories/financial_utils.py:12-16
EUR_TO_BGN_RATE = Decimal("1.95583000")
EXCHANGE_RATES_TO_BGN: dict[str, Decimal] = {
    "BGN": Decimal("1"),
    "EUR": EUR_TO_BGN_RATE,
}
```

Currently imported only by `services/agent/app/scripts/seed_test_data.py`.

**Recommendation:** Remove `financial_utils.py` from Agent. If the seed script needs these helpers, it should call Business APIs or import from a shared test utilities module. Exchange rates should only live in Business.

---

#### Finding 18: Agent `models/shared/usage.py` Imports From `runtime/` — Layer Inversion

**Problem:** `services/agent/app/models/shared/usage.py` imports `LLMUsageEvent` from `app.runtime.usage`. Models are the lowest layer in the Agent Service architecture (`routes/ → services/ → repositories/ → models/`), but `runtime/` sits above services. This is a layer inversion.

**Impact:** The models layer depends on the runtime layer, which means model changes can cascade into runtime and vice versa. Models should be importable by any layer without pulling in higher-level dependencies.

**Evidence:**

```python
# services/agent/app/models/shared/usage.py (lines 8-9)
from app.runtime.usage import LLMUsageEvent
```

The `from_runtime_event` factory method on `UsageEventCreate` directly references the runtime type.

**Recommendation:** Move `LLMUsageEvent` to `models/shared/usage.py` or a shared types module, then have `runtime/usage.py` import from models instead of the other way around. Alternatively, define a protocol/interface in models and have the runtime type implement it.

---

#### Finding 19: Agent `utils/db.py` Creates Indexes for Business-Owned Collections

**Problem:** `services/agent/app/utils/db.py` creates indexes on `invoices`, `expenses`, `companies`, and `partners` collections during Agent Service startup. These collections are owned by the Business Service per the architecture docs.

**Impact:** Two services race to create indexes on the same collections. If Business changes its index strategy, Agent's startup would need updating too. This violates the "each service owns its collections" boundary.

**Evidence:** Agent's `connect_db()` creates indexes on `invoices` (multiple), `expenses`, `companies`, and `partners` — all Business-owned collections. It even has a `drop_index` try/except for a legacy invoice index.

**Recommendation:** Remove all non-Agent indexes from Agent's `utils/db.py`. Only `agents`, `conversations`, and `usage_events` indexes should remain. Business Service's `utils/db.py` already handles its own collection indexes.

---

#### Finding 20: N+1 Query Patterns in Business `inventory_service.py`

**Problem:** `InventoryService._load_items_map` and `_load_locations_map` loop through IDs and call `get_by_id` one at a time:

**Impact:** For stock level enrichment and import previews with many items, this generates N sequential MongoDB queries instead of one batched `$in` query.

**Evidence:**

```python
# services/business/app/inventory/services/inventory_service.py:301-312
async def _load_items_map(self, user_id, company_id, item_ids):
    items_map = {}
    for item_id in item_ids:
        item = await self.item_repo.get_by_id(user_id, company_id, item_id)
        if item:
            items_map[item_id] = item
    return items_map
```

Same pattern in `_load_locations_map`. Also, `issue_for_invoice` processes lines sequentially and `inventory_import_service.confirm_preview` confirms lines one-by-one.

**Recommendation:** Add batch `get_by_ids(user_id, company_id, ids: list[str])` methods to `InventoryItemRepository` and `InventoryLocationRepository` using `{"_id": {"$in": [...]}}`. Replace the sequential loops with single batched queries.

---

#### Finding 21: `/financial-summary` Missing From Gateway `SERVICE_MAP`

**Problem:** Business Service mounts `/financial-summary` as an endpoint, and the docs describe it as an internal route. However, it is not listed in the gateway's `SERVICE_MAP`, so any request to `GET /financial-summary` through the gateway returns 404.

**Impact:** While Agent calls Business directly on the internal network (bypassing the gateway), this would block any future frontend or external client that needs financial summary data through the public API.

**Evidence:**

```python
# gateway/app/routes/proxy.py:15-22
SERVICE_MAP: dict[str, str] = {
    "/auth": settings.auth_service_url,
    **{prefix: settings.business_service_url for prefix in BUSINESS_DOMAIN_PREFIXES},
    # ... no /financial-summary
}
```

**Recommendation:** Either add `/financial-summary` to `BUSINESS_DOMAIN_PREFIXES` if it should be a public route, or document explicitly that it is internal-only and will never be gateway-routed.

---

#### Finding 22: Duplicated Partner Create-or-Resolve Logic Across Two Tool Files

**Problem:** `services/agent/app/tools/financial/partner_tools.py` and `services/agent/app/tools/financial/companybook.py` both implement a `_create_or_resolve_partner` pattern with 409 conflict resolution. The same registration number matching, search-then-create, and conflict retry logic appears in both files.

**Impact:** Bug fixes to the partner resolution flow must be applied in two places. The pattern is identical but the implementations may diverge over time.

**Evidence:** `partner_tools.py` lines ~114-144 and `companybook.py` lines ~66-96 both implement search by UIC, create partner, catch 409, re-search.

**Recommendation:** Extract a shared `resolve_or_create_partner` helper into `tools/financial/partner_utils.py` or `clients/business/partners.py` and have both tools delegate to it.

---

#### Finding 23: Duplicated `_json` Helpers Across 7+ Tool Files

**Problem:** An identical `_json` helper (`json.dumps(..., default=str)`) is repeated in `read_tools.py`, `write_tools.py`, `import_tools.py`, `company_tools.py`, `financial_tools.py`, `partner_tools.py`, and `companybook.py`.

**Impact:** Trivial code but a code smell — 7 copies of the same function increases maintenance surface unnecessarily.

**Recommendation:** Extract to a shared `tools/tool_utils.py` and import in each tool file.

---

#### Finding 24: `clients/business/partners.py` Contains Domain Logic Beyond HTTP Adaptation

**Problem:** `services/agent/app/clients/business/partners.py` (200 lines) includes in-memory partner matching (`find_matching_supplier_partner` scanning up to 100 partners), partner update building (`_build_supplier_partner_update`), and a `find_or_create_supplier_partner` orchestration method. This is domain/orchestration logic, not pure HTTP client adaptation.

**Impact:** The client adapter pattern calls for thin HTTP wrappers that translate requests/responses. Business matching policy in the client layer means that if Business adds a `/partners/match` endpoint, the client's local logic would need parallel removal.

**Evidence:** `partners.py` lines 133-159: in-memory filtering scan of partner list with substring matching logic.

**Recommendation:** Push matching and upsert logic to either a Business Service endpoint or an Agent service-layer helper. Keep the client as a thin HTTP adapter.

---

#### Finding 25: `loop_logging.py` Does More Than Logging — Usage Accounting + Async Heartbeat

**Problem:** `services/agent/app/runtime/loop_logging.py` (321 lines) is named "loop logging" but maintains `usage_events: list[LLMUsageEvent]`, builds `LLMUsageEvent` from stream/end events, and spawns `asyncio.create_task` for periodic LLM heartbeat monitoring. This is usage accounting and health monitoring, not just logging.

**Impact:** The file name and the file responsibilities are misaligned. A developer looking for usage event collection logic would not think to check `loop_logging.py`.

**Recommendation:** Rename to `loop_observer.py` or split into `loop_logging.py` (pure logging) and `loop_usage_collector.py` (usage event construction + heartbeat).

---

#### Finding 26: Company Delete Does Not Check Inventory — Data Integrity Gap

**Problem:** `CompanyService.delete` checks for Business invoices and partners before allowing company deletion, but does not check for inventory items, locations, stock movements, or import previews tied to that company.

**Impact:** Deleting a company would orphan all inventory data under that company, leaving items and stock movements referencing a non-existent `company_id`.

**Evidence:** `services/business/app/company/services/company_service.py` — delete method validates invoice and partner counts only.

**Recommendation:** Add inventory item count check to company delete validation, similar to the existing invoice and partner checks.

---

#### Finding 27: SSE Parser `JSON.parse` Has No Error Guard

**Problem:** `frontend/src/shared/api/sse.ts` calls `JSON.parse(data)` on SSE event data without a try/catch. Malformed JSON from the server would throw an unhandled exception and break the entire stream consumer.

**Impact:** A single corrupted SSE frame kills the chat stream for the user.

**Evidence:** `shared/api/sse.ts` lines 93-99 — raw `JSON.parse` without error handling.

**Recommendation:** Wrap `JSON.parse` in a try/catch, log the malformed frame, and `continue` to the next event instead of crashing the consumer.

---

#### Finding 28: `receipt.py` Re-Declares Types Already in `financial.py`

**Problem:** `services/agent/app/models/financial/receipt.py` re-declares `ExpenseCategory`, `CurrencyCode`, and `ExpenseSourceDocumentType` literals that already exist in `financial.py` within the same package.

**Impact:** Two sets of the same enum-like types in the same models package. If a new expense category is added, it must be updated in both files.

**Recommendation:** Import these types from `financial.py` in `receipt.py` instead of re-declaring them.

---

### Unnecessary Complexity / Refactoring Artifacts

#### Finding 4: 7 Compatibility Shim Files in Agent Tools

**Problem:** The Agent `tools/` directory contains 7 shim files that only re-export from the new package structure using `from X import *  # noqa: F403`:

| Shim file | Re-exports from |
|-----------|-----------------|
| `tools/financial.py` | `tools/financial/operations.py` |
| `tools/inventory.py` | `tools/inventory/operations.py` |
| `tools/rag.py` | `tools/shared/rag.py` |
| `tools/calculator.py` | `tools/shared/calculator.py` |
| `tools/dates.py` | `tools/shared/dates.py` |
| `tools/companybook.py` | `tools/financial/companybook.py` |
| `tools/__init__.py` | Still references old entry points |

Additionally, `tools/financial/operations.py` and `tools/inventory/operations.py` are themselves re-export shims within the new packages.

**Impact:** 9 total dead-weight files that add confusion about which is the "real" module. New developers will not know whether to import from `tools/financial` or `tools/financial.py`. The `from X import *` pattern also suppresses IDE navigation and linting.

**Evidence:**

```python
# services/agent/app/tools/financial.py (entire file)
from app.tools.financial.operations import *  # noqa: F403

# services/agent/app/tools/inventory.py (entire file)
from app.tools.inventory.operations import *  # noqa: F403
```

**Recommendation:** Update all import sites to reference the new package paths (`tools/financial/`, `tools/shared/`, `tools/inventory/`), then delete the 7 root-level shim files and the 2 internal `operations.py` shim files.

---

#### Finding 5: Old Empty Directories in Business Service

**Problem:** Business Service has leftover empty package directories from before the domain-based split:

- `services/business/app/models/` (only `__init__.py`)
- `services/business/app/repositories/` (only `__init__.py`)
- `services/business/app/services/` (only `__init__.py`)
- `services/business/app/routes/` (only `__pycache__`)

The active code lives in domain packages (`company/`, `partner/`, `financial/`, `inventory/`).

**Impact:** Confusion about where new code should go. A developer might add a service to the root `services/` instead of the domain package.

**Evidence:** Directory listing shows only `__init__.py` and `__pycache__` in these directories with no actual implementation files.

**Recommendation:** Delete these empty legacy directories. They serve no purpose since all domain code moved to `company/`, `partner/`, `financial/`, `inventory/`.

---

### Files That Need Splitting

#### Finding 6: `create-invoice-form.tsx` — 915 Lines

**Problem:** `frontend/src/features/create-invoice/ui/create-invoice-form.tsx` is 915 lines — the largest source file in the frontend. It combines form setup, company selection, partner selection, currency handling, date fields, line item management (add/remove), VAT calculation preview, bank details, Bulgarian PDF metadata fields, inventory linking, and stock-aware status warnings into one component.

**Impact:** Extremely difficult to maintain, test, or extend. Any change to one section (e.g., bank fields) risks breaking another (e.g., line items). The component has at least 6 distinct UI sections mixed together.

**Evidence:**

```
wc -l: 915 lines
Imports entity hooks (companies, inventory, stock levels)
Contains inline constants (STATUSES, CURRENCIES, PAYMENT_METHODS)
Contains helper functions (emptyRecipient, calculateInvoicePreview)
Mixes form setup, field rendering, total calculation, submission logic
```

**Recommendation:** Split into composable sub-components:
1. `invoice-header-fields.tsx` — dates, currency, status, payment method
2. `invoice-party-fields.tsx` — company selector, partner select, inline recipient
3. `invoice-line-items.tsx` — line item array with add/remove, VAT preview, inventory linking
4. `invoice-bank-fields.tsx` — bank name, BIC, IBAN
5. `invoice-metadata-fields.tsx` — Bulgarian PDF labels, notes
6. Keep `create-invoice-form.tsx` as a thin orchestrator (~150 lines)

---

#### Finding 7: `chat-window.tsx` — 473 Lines

**Problem:** `frontend/src/widgets/chat-window/ui/chat-window.tsx` is 473 lines. It handles chat message display, SSE streaming dispatch, conversation history loading, conversation list sidebar, scroll behavior, message input integration, and error state management.

**Impact:** The widget mixes rendering (message list, auto-scroll) with orchestration (SSE stream management, conversation switching). Testing any single concern requires loading the entire 473-line component.

**Evidence:** `wc -l: 473`

**Recommendation:** Extract:
1. `conversation-list.tsx` — history sidebar with conversation summaries
2. `chat-messages.tsx` — message rendering with auto-scroll
3. Keep `chat-window.tsx` as a composition wrapper (~200 lines)

---

#### Finding 8: `router.py` Runtime — 442 Lines Mixing Types, Graph, and Execution

**Problem:** `services/agent/app/runtime/router.py` at 442 lines contains Pydantic models (`RouterDecision`, `RouteMetadata`), TypedDict state definitions, LangGraph node functions, graph builder, direct LLM invocation with usage collection, classification message formatting, history formatting, and the `RouterAgent` class itself.

**Impact:** The file is doing 4 distinct jobs: (1) defining data types, (2) building the LangGraph state machine, (3) implementing LLM classification/delegation logic, and (4) defining the agent class. This makes it hard to test classification logic independently from graph construction.

**Evidence:** `wc -l: 442`

**Recommendation:** Split into:
1. `router_types.py` — `RouterDecision`, `RouteMetadata`, `CompanyScope`, `Route`, state TypedDicts
2. `router_graph.py` — graph node functions, graph builder, classification message formatting
3. `router.py` — `RouterAgent` class (~120 lines)

---

#### Finding 9: Business `inventory_service.py` — 435 Lines With 3 Domains

**Problem:** `services/business/app/inventory/services/inventory_service.py` at 435 lines manages inventory items, locations, AND stock movements in a single service class. It owns CRUD for all three entity types plus stock level aggregation.

**Impact:** The service will keep growing as inventory features expand (batch operations, location transfers, etc.). Three distinct domain areas compete for space in one file.

**Evidence:** `wc -l: 435` with methods spanning items (`create_item`, `update_item`, `list_items`), locations (`create_location`, `update_location`, `list_locations`), and movements (`create_movement`, `list_movements`), plus stock level queries.

**Recommendation:** Split into:
1. `inventory_item_service.py` — item CRUD, SKU uniqueness, search text
2. `inventory_location_service.py` — location CRUD, default location
3. `inventory_movement_service.py` — movement recording, idempotency, stock level aggregation
4. Keep a thin `inventory_service.py` facade if cross-domain coordination is needed

---

#### Finding 10: Business `inventory_item_repo.py` — 416 Lines

**Problem:** `services/business/app/inventory/repositories/inventory_item_repo.py` at 416 lines combines standard CRUD operations, search text composition (`_build_search_text`, `normalize_text`), Unicode normalization, multi-layer search logic (SKU/barcode/alias/text/prefix), and regex query building.

**Impact:** The search logic is complex enough to be its own testable module. Mixing search algorithms with basic CRUD makes the file hard to navigate and test in isolation.

**Evidence:** `wc -l: 416` with ~120 lines dedicated to text normalization and multi-stage search fallback.

**Recommendation:** Extract search helpers (`normalize_text`, `_build_search_text`, search query builders) into `inventory_search_helpers.py`, leaving the repository focused on data access.

---

### Performance Concerns

#### Finding 11: Gateway Creates a New `httpx.AsyncClient` Per Non-SSE Request

**Problem:** The gateway proxy creates a fresh `httpx.AsyncClient()` for every non-SSE request using `async with httpx.AsyncClient(timeout=120.0) as client:`. This means no connection pooling across requests.

**Impact:** Each proxied request incurs TCP connection setup overhead. Under load, this creates unnecessary latency and file descriptor pressure. The architecture docs and performance rules explicitly call for connection pooling.

**Evidence:**

```python
# gateway/app/routes/proxy.py:79-85
async with httpx.AsyncClient(timeout=120.0) as client:
    resp = await client.request(
        method=request.method,
        url=target_url,
        headers=headers,
        content=body,
    )
```

SSE requests (line 55) also create a per-request client, though this is more justified since SSE streams are long-lived.

**Recommendation:** Create a long-lived `httpx.AsyncClient` during FastAPI lifespan startup (matching how Agent's `BusinessClient` does it) and reuse it for all non-SSE proxy requests. Configure connection pool limits appropriate for the number of upstream services.

---

#### Finding 12: Business `dependencies.py` Growing DI Graph — 161 Lines

**Problem:** `services/business/app/dependencies.py` at 161 lines is a flat file with 18 factory functions that wire up all repositories, services, and cross-domain dependencies. As inventory grows, this file will become the bottleneck for merge conflicts and comprehension.

**Impact:** Every new domain entity or service requires modifying this single file. The dependency graph is already complex: `InvoiceService` depends on `CompanyService`, `PartnerRepo`, and `InventoryService`.

**Evidence:** `wc -l: 161` with all 8 repositories and 8 services wired in one file.

**Recommendation:** Split DI into per-domain files: `company/dependencies.py`, `financial/dependencies.py`, `inventory/dependencies.py`, `partner/dependencies.py`. Each owns its domain's repo and service factories. Cross-domain wiring (e.g., `InvoiceService` needing `InventoryService`) uses `Depends()` chains across domain dependency files. Keep a thin root `dependencies.py` for shared concerns (`get_user_id`, `get_db`).

---

### Inconsistencies

#### Finding 13: Agent Models Split Into `shared/`, `financial/`, `inventory/` — But Docs Say Flat

**Problem:** The Agent Service architecture doc (`docs/services/agent/architecture.md`) under "Concrete Modules" lists flat model files:

```text
models/
  agent.py
  chat.py
  conversation.py
  usage.py
  company.py
  financial.py
  partner.py
  companybook.py
  inventory.py
```

But the actual structure is:

```text
models/
  __init__.py (103-line re-export barrel)
  shared/
    agent.py, chat.py, conversation.py, document.py, usage.py
  financial/
    __init__.py, company.py, companybook.py, financial.py, partner.py, receipt.py
  inventory/
    __init__.py, base.py, items.py, stock.py, import_previews.py
```

**Impact:** Docs are stale and will mislead anyone reading them before code. The `models/__init__.py` barrel file (103 lines) re-exports everything to maintain the old flat import paths, adding a third layer of indirection.

**Recommendation:** Update `docs/services/agent/architecture.md` "Concrete Modules" to reflect the actual `shared/`, `financial/`, `inventory/` package structure. Simplify or remove the barrel `__init__.py` once all imports are migrated to use direct package paths.

---

#### Finding 14: Agent `tools/__init__.py` Only Exports Financial and Shared — Missing Inventory/CompanyBook

**Problem:** `services/agent/app/tools/__init__.py` only exports `build_company_tools`, `build_financial_tools`, `build_rag_search_tool`, and `calculator`. It does not export inventory tool builders or CompanyBook tools.

**Impact:** Inconsistent public API. Callers importing from `app.tools` get financial and shared tools but must know to import inventory and CompanyBook tools from deeper package paths.

**Evidence:**

```python
# services/agent/app/tools/__init__.py
from app.tools.financial import build_company_tools, build_financial_tools
from app.tools.shared import build_rag_search_tool, calculator

__all__ = [
    "build_rag_search_tool",
    "calculator",
    "build_company_tools",
    "build_financial_tools",
]
```

Missing: `build_inventory_read_tools`, `build_inventory_write_tools`, `build_inventory_import_tools`, `build_companybook_tools`, `build_partner_tools`, `date_tool`, `build_inventory_rag_tool`.

**Recommendation:** Either update `tools/__init__.py` to export all tool builders consistently, or remove the barrel entirely and have each runtime import directly from the specific package (which is the cleaner pattern given the split structure).

---

#### Finding 15: Agent `receipt_service.py` Mixes Orchestration Concerns

**Problem:** `services/agent/app/services/receipt_service.py` (104 lines) orchestrates a receipt-to-expense workflow that spans Agent, Knowledge, and Business services. It validates agent company scope, calls Knowledge for draft extraction, then calls Business for expense creation and partner upsert.

While this is valid as Agent-owned orchestration, the service name and location suggest it's a leftover from before the Business split. The receipt extraction logic conceptually belongs more to a "document processing" workflow than to core Agent CRUD.

**Impact:** The `AgentRepository` dependency for company-scope validation duplicates logic already in other services (`ChatService`, `AgentService`). The file is tightly coupled to Knowledge and Business clients.

**Evidence:**

```python
# services/agent/app/services/receipt_service.py:9
from app.repositories.agent_repo import AgentRepository

class ReceiptService:
    def __init__(self, agent_repo, knowledge_client, business_client): ...
```

**Recommendation:** Extract the company-scope agent validation into a shared helper (already done in `AgentService._require_company`) and reuse it. Consider whether receipt workflows should move to a dedicated feature service or remain in Agent with cleaner naming.

---

### Missing Best Practices

#### Finding 16: Gateway Proxy Forwards All Response Headers Blindly

**Problem:** The gateway proxy returns `headers=dict(resp.headers)` from upstream responses without filtering. This leaks internal service headers (e.g., `server`, `x-process-time`, internal CORS headers) to the client.

**Impact:** Information leakage about internal service technology. Potentially conflicting CORS or cache headers between the gateway and upstream services.

**Evidence:**

```python
# gateway/app/routes/proxy.py:86-90
return Response(
    content=resp.content,
    status_code=resp.status_code,
    headers=dict(resp.headers),
)
```

Same issue for SSE responses at line 72-77.

**Recommendation:** Allowlist response headers to forward (e.g., `content-type`, `cache-control`, `x-request-id`) and strip internal headers. At minimum, strip `server` and `transfer-encoding` (which can conflict with the gateway's own framing).

---

#### Finding 17: No `response_model` on Agent Chat Endpoint (Expected)

**Problem:** The chat SSE endpoint is a streaming response and correctly lacks a `response_model`. However, the `POST /agents/{agent_id}/receipts/draft` and `POST /agents/{agent_id}/receipts/confirm` endpoints in the Agent routes should be verified to have proper response models.

**Impact:** Missing `response_model` means unnecessary fields could be serialized to the client.

**Evidence:** Routes at `services/agent/app/routes/agents.py` — line count 123, need to verify receipt endpoints have `response_model`.

**Recommendation:** Audit all non-streaming Agent endpoints for explicit `response_model` parameters.

---

---

## 4. What Works Well (Positive Patterns)

### Pattern A: Clean Service Boundary Between Agent and Business

**What:** Agent tools call Business through `BusinessClient` over internal HTTP, never through direct MongoDB access. The client adapter normalizes HTTP failures into `BusinessClientError`.

**Why it works:** REST and chat-created records share the same Business validation, calculations, and user scoping. There is no logic duplication between the two entry points.

**Where:** `services/agent/app/clients/business/` (5 files, 574 lines total)

**Where else to apply:** The same pattern should be used for any future Agent-to-Knowledge or Agent-to-Orchestrator tool interactions.

---

### Pattern B: Domain-Based Package Structure in Business Service

**What:** Business Service organizes code into `company/`, `partner/`, `financial/`, `inventory/` domain packages, each with its own `models.py`, `routes/`, `services/`, `repositories/`.

**Why it works:** Each domain is independently navigable. Adding a new domain (e.g., `billing/`) means creating a new package without touching existing code.

**Where:** `services/business/app/company/`, `partner/`, `financial/`, `inventory/`

**Where else to apply:** Agent's models and tools have started this transition but still have compatibility shims.

---

### Pattern C: Thin Gateway With No Business Logic

**What:** The gateway proxy is 90 lines with zero business logic — pure routing, header injection, and SSE pass-through.

**Why it works:** The gateway cannot become a bottleneck for business rule changes. All domain logic stays in the services where it belongs.

**Where:** `gateway/app/routes/proxy.py`

---

### Pattern D: Agent Runtime Strategy Pattern

**What:** `BaseAgent`, `AccountantAgent`, `InventoryAgent`, and `RouterAgent` share a common interface. The registry maps `agent_type` to a concrete class at request time.

**Why it works:** Adding a new agent type is a single file with `get_tools()` and `get_system_prompt()`, plus one line in `registry.py`. The `ChatService` orchestration code doesn't change.

**Where:** `services/agent/app/runtime/base_agent.py`, `registry.py`, `inventory.py`, `router.py`

---

### Pattern E: FSD Widget Composition in Frontend

**What:** Widgets like `inventory-table/`, `low-stock-panel/`, `import-preview-table/` properly compose entity UI components and feature actions without owning business logic.

**Why it works:** The separation means entity display components are reusable across widgets, and features remain independently testable.

**Where:** `frontend/src/widgets/` (most widgets at 78-242 lines are well-sized)

---

### Pattern F: Zustand Stores for Cross-Feature Communication

**What:** `shared/store/chat-store.ts` and `shared/store/notification-store.ts` mediate between features that need to coordinate without importing each other.

**Why it works:** Features write to stores, widgets/features read from them. No feature knows about any other feature. TanStack Query cache invalidation handles server data sync.

**Where:** `frontend/src/shared/store/`

---

---

## 5. Summary — Priority Matrix

| # | Concern | Severity | Effort |
|---|---------|----------|--------|
| 1 | FSD violation: `shared/store/` imports from `entities/` | **Medium** | Low |
| 2 | FSD violation: feature-to-feature import in send-message | **Medium** | Low |
| 3 | Agent retains `financial_utils.py` in repositories after Business split | **Medium** | Low |
| 4 | 7+ compatibility shim files in Agent tools (dead-weight from refactor) | **Medium** | Low |
| 5 | Empty legacy directories in Business Service | **Low** | Low |
| 6 | `create-invoice-form.tsx` at 915 lines needs splitting | **High** | Medium |
| 7 | `chat-window.tsx` at 473 lines needs splitting | **Medium** | Medium |
| 8 | `router.py` at 442 lines mixes types, graph, and agent class | **Medium** | Medium |
| 9 | Business `inventory_service.py` at 435 lines handles 3 domains | **Medium** | Medium |
| 10 | Business `inventory_item_repo.py` at 416 lines mixes search + CRUD | **Medium** | Medium |
| 11 | Gateway creates new `httpx.AsyncClient` per request (no connection pooling) | **High** | Low |
| 12 | Business `dependencies.py` at 161 lines — growing DI bottleneck | **Low** | Medium |
| 13 | Agent architecture docs stale — list flat models, actual structure is packages | **Low** | Low |
| 14 | Agent `tools/__init__.py` barrel is incomplete — missing inventory/partner/dates | **Low** | Low |
| 15 | `receipt_service.py` duplicates company-scope validation pattern | **Low** | Low |
| 16 | Gateway forwards all upstream response headers (information leakage) | **Medium** | Low |
| 17 | Verify `response_model` on all non-streaming Agent endpoints | **Low** | Low |
| 18 | Agent `models/shared/usage.py` imports from `runtime/` — layer inversion | **High** | Low |
| 19 | Agent `utils/db.py` indexes Business-owned collections — ownership violation | **High** | Low |
| 20 | N+1 query patterns in Business `inventory_service.py` (sequential `get_by_id`) | **High** | Medium |
| 21 | `/financial-summary` missing from gateway `SERVICE_MAP` | **Medium** | Low |
| 22 | Duplicated partner create-or-resolve logic across two tool files | **Medium** | Low |
| 23 | Duplicated `_json` helpers across 7+ tool files | **Low** | Low |
| 24 | `clients/business/partners.py` has domain logic beyond HTTP adaptation | **Medium** | Medium |
| 25 | `loop_logging.py` does usage accounting + heartbeat, not just logging | **Medium** | Medium |
| 26 | Company delete does not check inventory — data integrity gap | **High** | Low |
| 27 | SSE parser `JSON.parse` has no error guard | **Medium** | Low |
| 28 | `receipt.py` re-declares types already in `financial.py` | **Low** | Low |

---

## 6. Suggested Implementation Order

### Batch 1 — Quick Wins (High Impact + Low Effort)

- **#11** Gateway connection pooling — create a lifespan-managed `httpx.AsyncClient` to replace per-request clients.
- **#19** Remove Business-owned indexes from Agent's `utils/db.py` — only keep `agents`, `conversations`, `usage_events`.
- **#18** Fix layer inversion — move `LLMUsageEvent` to models or define a protocol in models that runtime implements.
- **#26** Add inventory check to company delete validation in Business `CompanyService`.
- **#1, #2** Fix both FSD import violations — move shared types to `shared/`, break the feature-to-feature import.
- **#27** Add try/catch around `JSON.parse` in `sse.ts` to prevent broken streams from malformed SSE frames.
- **#4** Delete 7 tool shim files and 2 `operations.py` re-exports after updating imports.
- **#3** Remove `financial_utils.py` from Agent repositories.
- **#5** Delete empty legacy Business directories.
- **#16** Add response header allowlist to gateway proxy.
- **#21** Add `/financial-summary` to gateway `SERVICE_MAP` or document it as internal-only.
- **#22** Unify partner create-or-resolve into a shared helper.
- **#23, #28** Extract shared `_json` helper; fix `receipt.py` duplicate type declarations.

### Batch 2 — File Splits (Medium Effort)

- **#6** Split `create-invoice-form.tsx` into 5-6 sub-components.
- **#7** Split `chat-window.tsx` into conversation list + messages + wrapper.
- **#8** Split `router.py` into types, graph, and agent files.
- **#9** Split Business `inventory_service.py` into per-entity services.
- **#10** Extract search helpers from `inventory_item_repo.py`.
- **#20** Add batch `get_by_ids` methods to inventory repos, replace sequential loops.
- **#24** Move partner matching logic from `clients/business/partners.py` to an Agent service helper or a Business endpoint.
- **#25** Rename/split `loop_logging.py` to separate logging from usage collection.

### Batch 3 — Cleanup and Documentation

- **#13** Update Agent architecture docs to match actual package structure.
- **#14** Fix or remove the `tools/__init__.py` barrel.
- **#12** Split Business `dependencies.py` into per-domain DI files.
- **#15** Deduplicate company-scope validation in `receipt_service.py`.
- **#17** Audit Agent endpoints for missing `response_model`.
