# Agent Service Architecture

## Current State

The Agent Service owns agent instances, chat runtime orchestration, conversation history, agent-specific tool sets, and deterministic review workflows that sit in front of Business-owned writes. The Accountant Agent provides `rag_search`, `calculator`, `date_helper`, Business-backed company/partner tools, Business-backed `query_invoices`, `query_expenses`, `get_financial_summary`, `create_invoice`, `record_expense`, and CompanyBook partner lookup tools. The Inventory Agent provides `search_inventory_stock`, `list_inventory_items`, `get_stock_levels`, `list_low_stock_items`, `get_stock_movements`, `list_inventory_locations`, `create_inventory_item`, `update_inventory_item`, `record_stock_movement`, import preview tools, `rag_search` (inventory-scoped), `calculator`, `date_helper`, and company resolution tools for unassigned agents. The Router Agent classifies each chat turn and delegates to accountant, inventory, or a no-tool general fallback while keeping the same `/agents/{id}/chat` SSE endpoint.

## Implemented Responsibilities

- User-scoped Agent CRUD.
- Accountant Agent runtime.
- Inventory Agent runtime.
- Router Agent runtime with LangGraph classification/delegation.
- SSE chat streaming.
- MongoDB conversation persistence.
- Raw LLM usage ledger persistence in the Agent-owned `usage_events` collection.
- LLM provider selection for OpenAI, Anthropic, DeepSeek, and Ollama.
- LangChain `AgentExecutor` execution for model-requested tools.
- Runtime lifecycle hooks for controlled agent-specific input/tool/event/chunk/final-output transformations.
- Development-only agent loop logging with provider-reported token metadata tracing when available.
- RAG access through the Knowledge Base Service `POST /retrieve` endpoint.
- Document intake workflow orchestration via `POST /agents/{agent_id}/document-intake`.
- Safe arithmetic calculations through a restricted calculator tool.
- Business HTTP access for company validation, partner lookup/write, invoice and expense query/write, inventory workflows, and financial summary aggregation.
- Structured financial query and write tools over Business Service contracts.
- CompanyBook.BG partner lookup tools that search Bulgarian companies, import a selected UIC into the scoped partner workflow through Business, and leave invoice creation on the existing `create_invoice` tool path.
- Agent-owned sales invoice inventory workflow endpoints that resolve partner/inventory candidates, build an editable invoice draft, and persist the final draft through Business only after explicit confirmation.

## Layers

```text
routes/ -> services/ -> repositories/ -> models/
                     \-> runtime/ -> tools/ -> clients/
```

| Layer | Responsibility |
|-------|----------------|
| `routes/` | HTTP endpoints, request/response models, dependency injection |
| `services/` | Agent-specific rules, user scoping, orchestration |
| `repositories/` | Agent-owned MongoDB access only |
| `models/` | Pydantic schemas |
| `runtime/` | Base agent strategy, concrete agents, registry, provider factory |
| `tools/` | LangChain tool adapters over local utilities and service-to-service contracts |
| `clients/` | Internal HTTP adapters for services Agent consumes |

## Concrete Modules

```text
routes/
  agents.py
  conversations.py
clients/
  business/
    __init__.py
    base.py
    companies.py
    partners.py
    financial.py
    inventory.py
services/
  agent_service.py
  chat_service.py
  document_intake_service.py
  sales_invoice_workflow_graph.py
  sales_invoice_workflow_service.py
  workflows/
    base.py
  document_workflows/
    base.py
    receipt.py
    supplier_invoice.py
    unknown.py
  conversation_service.py
  companybook_service.py
repositories/
  agent_repo.py
  conversation_repo.py
  usage_repo.py
models/
  sales_invoice_workflow.py
  document_intake.py
  agent.py
  chat.py
  conversation.py
  usage.py
  company.py
  financial.py
  partner.py
  companybook.py
  inventory.py
runtime/
  base_agent.py
  accountant.py
  inventory.py
  router.py
  hooks.py
  loop_logging.py
  registry.py
  tool_context.py
  usage.py
  providers/
    factory.py
    openai.py
    anthropic.py
    deepseek.py
    ollama.py
tools/
  rag.py
  calculator.py
  dates.py
  financial.py
  companybook.py
  inventory.py
```

## Main Patterns

- **Layered architecture:** routes never touch MongoDB or service clients directly.
- **Repository pattern:** Agent-owned MongoDB access is isolated, including immutable raw usage events.
- **Strategy pattern:** each agent type implements the shared `BaseAgent` contract. Router uses the same registry contract but overrides `run()` for graph execution.
- **Hook contract:** concrete agents may override optional `BaseAgent` lifecycle hooks without replacing the shared event loop.
- **Registry pattern:** `create_agent_runtime()` maps `agent_type` to a concrete runtime class.
- **Factory pattern:** `LLMProviderFactory` creates provider wrappers for OpenAI, Anthropic, DeepSeek, and Ollama.
- **Client adapter pattern:** `BusinessClient` wraps Business Service HTTP calls and translates HTTP failures into tool/service-safe errors.
- **Thin tools:** LangChain tools adapt stable contracts. `rag_search` calls Knowledge Base over HTTP; `calculator` and `date_helper` run locally; financial, CompanyBook, and inventory tools call Business through `BusinessClient`, never Business repositories directly.
- **Workflow shell:** Company-bound workflows reuse `require_company_scoped_agent()` and `map_business_client_error()` from `services/workflows/base.py` so Agent-owned review endpoints enforce the same scope and downstream error behavior.

## Runtime Contract

The chat service loads the agent, creates the configured provider, resolves the runtime from the registry, then creates or validates the conversation and streams chunks from `BaseAgent.run()`. For router agents, `ChatService` also resolves compatible child runtimes before conversation creation. New conversations are created only after provider and runtime setup succeeds. Conversations store the agent's current `company_id`; an existing `conversation_id` is accepted only when it belongs to the same user, agent, and company scope.

`BaseAgent.run()` creates a LangChain `AgentExecutor` for each turn. The executor receives the user input and recent chat history, executes model-requested tool calls, feeds tool results back to the model, and emits final user-facing chunks for SSE `token` events. If the provider does not produce streaming chunks, the runtime returns the executor's final output once.

`RouterAgent.run()` uses a LangGraph shape of `router -> accountant | inventory | general`. The classifier returns a structured route decision with `route`, `reason`, and `confidence`. If the predicted specialist runtime is unavailable, the executed route becomes `general` while the predicted route is preserved for metadata. Router general fallback uses the router LLM with no tools.

Concrete runtimes may override optional hooks defined by `BaseAgent`: `prepare_run_input()`, `prepare_tools()`, `on_run_start()`, `on_event()`, `on_chunk()`, `on_run_end()`, and `on_run_error()`. Hooks receive typed run-local objects from `runtime/hooks.py` and share one metadata dict for the turn. Hooks may mutate runtime inputs, tools, events, streamed text, final fallback output, metadata, and runtime usage event lists. They must not emit SSE, append messages, call FastAPI dependencies, or write repositories directly.

When the Agent Service runs with `AGENT_ENV=development`, `BaseAgent.run()` also logs LangChain agent start/ready, tool start/end/error, LLM start/first-token/stream/end/slow/error, and heartbeat events to the service console. These logs include bounded previews of tool inputs and outputs for debugging local tool behavior. Provider token tracing is best-effort and depends on LangChain/provider metadata fields. Production defaults keep debug logging quiet except warnings/errors such as slow or failed model calls, and the runtime does not expose logs through SSE or conversation persistence.

After a successful runtime run, `ChatService` drains `runtime.consume_usage_events()`. It persists filtered provider-reported token facts to `usage_events` only after conversation messages are saved. Usage persistence failures are logged but do not change an otherwise successful chat into an SSE `error`. The runtime and repository store raw token facts only; they do not calculate billing cost, enforce quotas, or apply model prices.

If the runtime exposes `route_metadata`, `ChatService` emits an optional `route` SSE event after message and usage persistence and before `done`. If a router turn also exposes a valid `workflow_suggestion`, `ChatService` emits it after `route` and before `done`. These metadata events are not written into persisted conversation messages and must not start a write workflow without explicit frontend/user action.

Three agent types are currently valid: `"accountant"`, `"inventory"`, and `"router"`. The Accountant Agent can list and resolve companies, query invoices, query expenses, summarize financial records, search/create partners, search CompanyBook.BG for Bulgarian companies, import a selected registry company as a partner, create invoices, and record expenses. The Inventory Agent can search inventory items, check stock levels, list low-stock items, view movement history, create/update items, record stock movements, and review/confirm/cancel supplier invoice import previews. The Router Agent delegates finance and inventory turns to compatible specialist runtimes and handles general turns with a no-tool fallback. Accountant and inventory write tools require explicit user confirmation before `confirmed=true` is sent to the tool.

Accountant list/search tools return envelope-shaped payloads (`total_count`, `returned_count`, `offset`, `limit`, `truncated`, `next_offset`, `items`), and prompt guidance requires treating `truncated=true` as incomplete results.

`resolve_partner_by_name` now returns ranked candidates with `match_type`, `score`, and `match_reasons`, which the runtime uses to avoid weak silent partner selection.

Financial summaries expose EUR-denominated top-level totals (`currency="EUR"`, `exchange_rates_to_eur`) while preserving source-currency totals in `totals_by_currency`.

Router child selection is exact-scope and user-scoped. `ChatService` first looks for linked delegate documents via `parent_agent_id` and `delegate_role`, then falls back to the latest same-user, same-company specialist agent for compatibility. The public agent schema does not yet include typed delegate fields or hide delegate documents from list responses; router creation currently does not auto-provision hidden delegates.

## Business Service Boundary

Agent does not mount company, partner, invoice, expense, or financial summary REST routes. The gateway routes those public prefixes to Business Service while `/agents` and `/conversations` continue to route to Agent Service.

Agent consumes Business Service in these places:

- `AgentService` validates non-null `company_id` values during create, update, and company-filtered list operations through `GET /companies/{company_id}/exists`.
- Accountant tools use `BusinessClient` for company listing/resolution, partner lookup/write, invoice and expense query/write, and financial summary calls.
- Inventory tools use `BusinessClient` for inventory item CRUD, stock level queries, movement recording, location listing, inventory search, and import preview lifecycle.
- `DocumentIntakeService` uses `BusinessClient` for supplier invoice import preview create/confirm/get during the two-stage approval flow.
- `SalesInvoiceWorkflowService` uses `BusinessClient` for company scope validation, partner resolution, inventory search/stock validation, and final invoice creation.

`BusinessClient` is backed by a long-lived `httpx.AsyncClient` created during FastAPI lifespan startup. It forwards `x-user-id` on every request and normalizes Business HTTP/transport failures into `BusinessClientError`.

## Document Intake Workflow

The Agent Service owns document-intake orchestration and approval sequencing:

- `POST /agents/{agent_id}/document-intake` accepts multipart `file` plus `requested_type` (`auto`, `invoice`, `receipt`) and returns a discriminated `DocumentIntakeResponse`.
- `POST /agents/{agent_id}/document-intake/supplier-invoice/inventory-imports/confirm` confirms inventory import preview changes and returns `supplier_invoice_expense_review`.
- `POST /agents/{agent_id}/expenses/confirm` remains the only path that records an expense.

`DocumentIntakeResponse` variants:

- `receipt_expense_review`
- `supplier_invoice_inventory_review`
- `supplier_invoice_expense_review`
- `unknown_document_review`

Ownership boundaries are explicit:

- Knowledge classifies/extracts draft data only.
- Agent validates extraction output and routes deterministic workflows.
- Business writes inventory and expenses only when explicit approval endpoints are called.

## Sales Invoice Inventory Workflow

The Agent Service owns a three-step review sequence for inventory-backed customer invoices:

1. `POST /agents/{agent_id}/invoice-workflows/sales-inventory/preview` resolves the scoped company, partner candidates, inventory search candidates, default locations, stock levels, and warnings.
2. `POST /agents/{agent_id}/invoice-workflows/sales-inventory/inventory/confirm` validates the user-selected partner/item/location lines and returns an editable `InvoiceCreate` draft.
3. `POST /agents/{agent_id}/invoice-workflows/sales-inventory/invoice/confirm` requires `confirmed=true` and sends the reviewed draft to Business `POST /invoices`.

The workflow is deterministic LangGraph orchestration, not an LLM write path. Router chat can suggest it with `workflow_suggestion`, and the frontend can start it manually, but preview does not run until the user explicitly starts the workflow. Agent does not create stock movements here; Business creates stock issue movements later when the invoice status transitions from `draft` to `sent`.

## CompanyBook.BG Integration

The Accountant Agent has two external registry tools:

| Tool | Purpose | Writes data |
|------|---------|-------------|
| `search_companybook_companies` | Calls `GET /companies/search` with a trimmed name or UIC query and returns candidate companies for user selection. | No |
| `import_companybook_partner` | Calls `GET /companies/{uic}?with_data=true`, maps the selected company into `PartnerCreate`, and creates or reuses a scoped partner. | Yes, only through Business Service |

Required configuration:

| Env var | Default | Notes |
|---------|---------|-------|
| `COMPANYBOOK_API_KEY` | empty | Optional at startup. Tool calls return a user-safe configuration error when missing. |
| `COMPANYBOOK_BASE_URL` | `https://api.companybook.bg/api` | Base URL for CompanyBook.BG API calls. |
| `COMPANYBOOK_TIMEOUT_SECONDS` | `10.0` | Per-request timeout for search and detail calls. |

The integration does not store raw CompanyBook financial data or documents. It persists only the user-selected partner fields required by the existing partner model. Partner imports first search Business partners by exact UIC, then create through Business Service; duplicate-key races are resolved by searching the partner by UIC again. If CompanyBook omits required invoice recipient fields (`city`, `address`, `accountable_person`, etc.), the tool returns `missing_fields` and `partner_draft` so the agent asks the user only for the missing details.

`search_companybook_companies` returns the same pagination envelope fields as local search/list tools (`total_count`, `returned_count`, `offset`, `limit`, `truncated`, `next_offset`, `items`) plus `"source": "companybook"` for provenance.

CompanyBook calls are made from Agent Service tool execution, not from the frontend or gateway. Gateway rate limiting still limits the chat request stream, but CompanyBook API quota behavior is owned by CompanyBook; HTTP `429` responses are normalized into a user-facing "try again later" message.

## Provider Factory

Provider names are stored per agent in `config.provider`.

| Provider | Wrapper | Required configuration |
|----------|---------|------------------------|
| `openai` | `OpenAIProvider` | `OPENAI_API_KEY`, optional `OPENAI_CHAT_MODEL` |
| `anthropic` | `AnthropicProvider` | `ANTHROPIC_API_KEY`, optional `ANTHROPIC_CHAT_MODEL` |
| `deepseek` | `DeepSeekProvider` | `DEEPSEEK_API_KEY`, optional `DEEPSEEK_CHAT_MODEL` |
| `ollama` | `OllamaProvider` | Local Ollama at `OLLAMA_BASE_URL`, optional `OLLAMA_CHAT_MODEL` |

Missing external-provider API keys fail during chat setup and are returned as SSE `error` events.

## Agent-Owned Collections

| Collection | Owner | Purpose | Key indexes |
|------------|-------|---------|-------------|
| `agents` | Agent Service | User-created agent configurations. | `user_id + created_at`, `user_id + name`, `user_id + agent_type + company_id + created_at`, `user_id + company_id + created_at` |
| `conversations` | Agent Service | User/assistant message history and conversation scope. | `user_id + agent_id + updated_at`, `user_id + agent_id + company_id + updated_at`, `user_id + created_at` |
| `usage_events` | Agent Service | Immutable raw LLM usage facts for completed provider calls. | `user_id + created_at`, `user_id + provider + model + created_at`, `conversation_id + created_at`, `agent_id + created_at`, unique `idempotency_key` |

`usage_events` records provider, model, optional LangChain `run_id`, LLM call index, token counts when reported, streaming chunk/character counts, started/completed timestamps, duration, and `source="agent_runtime"`. It is a raw ledger for future billing or analytics jobs, not a user-facing API contract.

## Restrictions

- Every route must be `async def`.
- Every endpoint must define Pydantic request/response models, except streaming responses.
- All user data must be scoped by `x-user-id`.
- Do not call ChromaDB directly; use Knowledge Base Service for RAG.
- Add MongoDB indexes for Agent-owned user, agent, and conversation filters.
- Add MongoDB indexes for new Agent-owned usage queries and idempotency keys.
- Do not reintroduce Business-owned repositories, routes, or services into Agent.
- Financial and partner tool code must call `BusinessClient`, not MongoDB repositories, so REST and chat behavior stay consistent with Business Service.
- Keep runtime hooks side-effect scoped: no direct SSE emission, repository writes, or FastAPI dependency access from `BaseAgent` subclasses.
- Do not estimate token counts or compute billing cost in the runtime. Persist only provider-reported token metadata and apply prices in future billing/reporting code.
