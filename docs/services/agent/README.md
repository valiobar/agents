# Agent Service

## Current State

The Agent Service owns user-created agents, MongoDB-backed conversation persistence, Accountant, Inventory, and Router runtimes, multi-provider LLM factory, RAG search, calculator/date tooling, Business-backed financial, partner, and inventory LangChain tools, and SSE chat streaming through the API Gateway.

## Responsibility

The Agent Service owns user-created agents and persisted chat history. It receives authenticated user context from the gateway through `x-user-id`; it does not decode JWTs directly.

### Business Split Baseline

The Business Service split is active. Public `/companies`, `/partners`, `/invoices`, `/expenses`, and `/inventory/*` URLs exist at the gateway, but the gateway routes those prefixes to Business Service. Agent exposes only agent lifecycle, chat, conversation history, document-intake orchestration endpoints, receipt-draft compatibility endpoints, and health endpoints.

Runtime guardrails:

- Keep Agent chat and SSE behavior on `/agents` unchanged.
- Treat company, partner, invoice, expense, and financial summary data as Business-owned.
- Access Business from Agent only through the long-lived `BusinessClient` HTTP adapter.
- Verify the split with gateway health, Business health, gateway `GET /companies`, and an Agent chat flow that invokes `query_expenses`.

Implemented responsibilities:

- Agent lifecycle operations: create, list, get, update, and delete.
- Accountant Agent runtime using the Strategy pattern.
- Inventory Agent runtime for stock, item, movement, location, and import-preview workflows.
- Router Agent runtime for turn classification and accountant/inventory/general delegation.
- Provider selection for OpenAI, Anthropic, DeepSeek, and Ollama through a Factory pattern.
- Chat request orchestration and `text/event-stream` SSE output.
- Conversation creation and history persistence in MongoDB.
- LangChain `AgentExecutor` orchestration for model-requested tool calls.
- RAG lookup through the Knowledge Base Service `POST /retrieve` contract.
- Safe arithmetic through the calculator tool.
- Company validation through Business `GET /companies/{company_id}/exists`.
- Structured company, partner, invoice, expense, and financial summary tools backed by Business HTTP APIs.

## Internal Architecture

```text
routes/
  agents.py              # Agent CRUD and chat streaming
  conversations.py       # Conversation history reads
clients/
  business.py            # Business Service HTTP adapter for domain data
services/
  agent_service.py       # Agent lifecycle business logic
  chat_service.py        # Runtime orchestration, SSE events, persistence
  conversation_service.py
  companybook_service.py # CompanyBook.BG external API adapter
repositories/
  agent_repo.py          # User-scoped agent MongoDB access
  conversation_repo.py   # User-scoped conversation MongoDB access
models/
  agent.py               # Agent config, create/update, response schemas
  company.py             # Business response schemas consumed by tools/client
  conversation.py        # Message and conversation schemas
  chat.py                # Chat request and event schemas
  financial.py           # Business financial schemas consumed by tools/client
  partner.py             # Business partner schemas consumed by tools/client
  companybook.py         # CompanyBook response and mapping schemas
runtime/
  base_agent.py          # Strategy interface and streaming loop
  accountant.py          # Finance concrete agent
  inventory.py           # Inventory concrete agent
  router.py              # LangGraph classifier/delegation runtime
  registry.py            # agent_type -> runtime class
  tool_context.py        # Business and CompanyBook clients injected into tools
  providers/
    factory.py           # provider -> LangChain provider wrapper
tools/
  rag.py                 # Knowledge Base Service adapter
  calculator.py          # Safe arithmetic adapter
  dates.py               # Date helper tool
  financial.py           # Business-backed company, partner, invoice, expense, and summary tools
  companybook.py         # CompanyBook search/import tools backed by Business partner writes
```

Routes do request/response handling only. Services own orchestration and agent-specific business rules. Repositories own Agent MongoDB access. Business-domain persistence and calculations live in Business Service; Agent tools call Business through `BusinessClient`, not through copied repositories or services.

## API Surface

All client calls go through the API Gateway at `http://localhost:8000`. Internal direct calls require `x-user-id`.

| Route | Status | Purpose |
|-------|--------|---------|
| `GET /health` | Implemented | Internal health check |
| `POST /agents` | Implemented | Create an Accountant, Inventory, or Router agent, optionally assigned to a company |
| `GET /agents?company_id=...&limit=50&offset=0` | Implemented | List current user's agents, optionally filtered by company |
| `GET /agents/{agent_id}` | Implemented | Get one current-user agent |
| `PATCH /agents/{agent_id}` | Implemented | Update name, description, or config |
| `DELETE /agents/{agent_id}` | Implemented | Delete an agent |
| `POST /agents/{agent_id}/chat` | Implemented | Stream chat response via SSE |
| `POST /agents/{agent_id}/document-intake` | Implemented | Classify/extract upload and return workflow review union |
| `POST /agents/{agent_id}/document-intake/supplier-invoice/inventory-imports/confirm` | Implemented | Confirm inventory import stage and continue supplier invoice flow |
| `POST /agents/{agent_id}/invoice-workflows/sales-inventory/preview` | Implemented | Resolve partner and inventory candidates for a stock-backed sales invoice |
| `POST /agents/{agent_id}/invoice-workflows/sales-inventory/inventory/confirm` | Implemented | Validate selected inventory and return an invoice draft review |
| `POST /agents/{agent_id}/invoice-workflows/sales-inventory/invoice/confirm` | Implemented | Persist the reviewed invoice through Business Service |
| `POST /agents/{agent_id}/expense-drafts` | Implemented (compatibility) | Legacy receipt draft endpoint kept for older clients |
| `POST /agents/{agent_id}/expenses/confirm` | Implemented | Final explicit approval endpoint that records expense |
| `GET /conversations/{conversation_id}` | Implemented | Load persisted conversation history |

Business-owned public routes are documented under `docs/services/business/`. Gateway keeps their public URLs stable while routing them to Business Service.

## Companies And Partners

The Agent Service no longer owns the `companies` and `partners` collections or REST routes. It consumes company and partner data from Business Service.

Agent create, update, and company-filtered list operations validate non-null `company_id` values through Business `GET /companies/{company_id}/exists`. Business ownership failures are surfaced to Agent callers as `404 Company not found`; Business availability failures become `503`.

Accountant tools use Business-backed company and partner operations:

- `list_companies` and `resolve_company_by_name` read current-user companies.
- `search_partners`, `resolve_partner_by_name`, `get_partner`, and `create_partner` operate inside a resolved company scope.
- `import_companybook_partner` searches CompanyBook.BG, then creates or reuses the partner through Business.

Example workflow:

1. `POST /companies` creates the invoice issuer profile.
2. `POST /partners` creates a recipient under that company.
3. `POST /agents` may assign an Accountant Agent to the company via `company_id`.
4. `POST /invoices` requires `company_id` and uses either `partner_id` or full recipient details.
5. `POST /documents` in the Knowledge Base Service requires the same `company_id` and validates it through Business Service.

Steps 1, 2, and 4 are Business-owned even though they are still reached through the gateway.

## Financial Records


Agent keeps the financial Pydantic schemas it needs to validate tool arguments and parse Business responses. Money storage, date normalization, invoice numbering, totals, status transitions, snapshots, and financial summary aggregation are Business Service responsibilities.

Financial tool calls preserve `x-user-id` and pass validated JSON to Business:

- `GET /companies`
- `GET /companies/{company_id}/exists`
- `GET /partners`
- `GET /partners/{partner_id}`
- `POST /partners`
- `GET /invoices`
- `POST /invoices`
- `GET /expenses`
- `POST /expenses`
- `POST /financial-summary`

### Accountant Financial Tools

The Accountant Agent has Business-backed financial and company tools:

| Tool | Purpose | Key parameters |
|------|---------|----------------|
| `list_companies` | List/search current-user companies | `query`, `limit` |
| `resolve_company_by_name` | Resolve a company name or registration number before company-scoped actions | `name`, `max_matches` |
| `query_invoices` | Query current-user invoices | `company_id`, `partner_id`, `status`, `date_from`, `date_to`, `counterparty`, `amount_min`, `amount_max`, `category`, `limit` |
| `query_expenses` | Query current-user expenses | `category`, `counterparty`, `date_from`, `date_to`, `deductible`, `amount_min`, `amount_max`, `limit` |
| `get_financial_summary` | Summarize invoice and expense totals | `date_from`, `date_to`, `group_by`, `include_invoices`, `include_expenses` |
| `create_invoice` | Create an invoice after explicit confirmation | Invoice create fields plus `confirmed` |
| `record_expense` | Record an expense after explicit confirmation | Expense create fields plus `confirmed` |
| `search_partners` | Search partners in the assigned agent company | `query`, `kind`, `limit` |
| `resolve_partner_by_name` | Resolve a named client/supplier before invoice creation | `name`, `kind`, `max_matches` |
| `get_partner` | Load one partner before invoice creation or clarification | `partner_id` |
| `create_partner` | Create a partner in the assigned agent company | Partner create fields |

Write tools refuse to persist invoices and expenses until the model sets `confirmed=true`, which the system prompt instructs it to do only after the user explicitly confirms the summarized record. Company-scoped partner and invoice tools use the assigned agent company automatically; unassigned agents must resolve and pass `company_id`. RAG still works for shared `global_tax` when an agent has no company.

### Development Tool Logging

Set `AGENT_ENV=development` for the Agent Service to log LangChain tool start, end, and error events from `BaseAgent.run()`. Development logs include the tool name, LangChain run ID, current agent/user context, and bounded input/output previews so large RAG or financial results do not flood the console. This logging is local observability only; it does not change SSE events or persisted conversation messages.

## SSE Event Protocol

`POST /agents/{agent_id}/chat` returns `text/event-stream`. The gateway passes through the stream when clients send `Accept: text/event-stream`.

| Event | Data | When emitted |
|-------|------|--------------|
| `conversation` | `{ "conversation_id": "..." }` | A new conversation is created because `conversation_id` was omitted. |
| `start` | `{ "conversation_id": "..." }` | Runtime initialization succeeded and token streaming is starting. |
| `token` | `{ "content": "..." }` | A streamed assistant token or chunk is available. |
| `route` | `{ "predicted_route": "inventory", "executed_route": "inventory", "reason": "...", "confidence": 0.95, "company_id": "...", "company_scope": "assigned" }` | Router-only metadata emitted after persistence and before `done`. |
| `workflow_suggestion` | `{ "workflow": "sales_invoice_inventory", "confidence": 0.94, "reason": "...", "prefill": { ... } }` | Router-only workflow kickoff suggestion emitted after `route` and before `done`. |
| `error` | `{ "message": "..." }` | Agent lookup, conversation lookup, provider setup, runtime execution, or message persistence failed. |
| `done` | `{ "conversation_id": "..." }` | Runtime completed and user/assistant messages were persisted. |

Example:

```text
event: conversation
data: {"conversation_id":"665f1f77c9e0f7a8093bb711"}

event: start
data: {"conversation_id":"665f1f77c9e0f7a8093bb711"}

event: token
data: {"content":"20% VAT on 100 is "}

event: route
data: {"predicted_route":"accountant","executed_route":"accountant","reason":"VAT question","confidence":0.94,"company_id":"665f1f77c9e0f7a8093bb701","company_scope":"assigned"}

event: workflow_suggestion
data: {"workflow":"sales_invoice_inventory","confidence":0.94,"reason":"Stock-backed invoice request","prefill":{"partner_query":"Acme","lines":[]}}

event: done
data: {"conversation_id":"665f1f77c9e0f7a8093bb711"}
```

Non-router chats do not emit `route` or `workflow_suggestion`. Clients should tolerate optional metadata events and continue using `token` and `done` as the user-visible completion contract. Workflow-specific diagrams and state machines live in `docs/workflows/`.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `MONGODB_URL` | `mongodb://mongodb:27017` | MongoDB connection string. |
| `DB_NAME` | `agents` | Database used by the service. |
| `KNOWLEDGE_SERVICE_URL` | `http://knowledge:8003` | Internal Knowledge Base Service URL. |
| `BUSINESS_SERVICE_URL` | `http://business:8005` | Internal Business Service URL used for company validation and financial tools. |
| `BUSINESS_TIMEOUT_SECONDS` | `15.0` | Per-request timeout for Business Service calls. |
| `OPENAI_API_KEY` | empty | Required for `provider: "openai"`. |
| `OPENAI_CHAT_MODEL` | `gpt-4.1-mini` | Default OpenAI chat model. |
| `ANTHROPIC_API_KEY` | empty | Required for `provider: "anthropic"`. |
| `ANTHROPIC_CHAT_MODEL` | `claude-3-5-haiku-latest` | Default Anthropic chat model. |
| `DEEPSEEK_API_KEY` | empty | Required for `provider: "deepseek"`. |
| `DEEPSEEK_CHAT_MODEL` | `deepseek-chat` | Default DeepSeek chat model. |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Local Ollama server URL. |
| `OLLAMA_CHAT_MODEL` | `llama3.1` | Default Ollama model. |
| `DEFAULT_AGENT_PROVIDER` | `openai` | Provider used when client omits one. |
| `MAX_HISTORY_MESSAGES` | `20` | Recent conversation messages sent to the runtime. |
| `RAG_TOP_K` | `3` | Number of chunks requested from Knowledge Base retrieval. |
| `COMPANYBOOK_API_KEY` | empty | Optional CompanyBook.BG API key; missing values return a tool-level configuration error. |
| `COMPANYBOOK_BASE_URL` | `https://api.companybook.bg/api` | CompanyBook.BG API base URL. |
| `COMPANYBOOK_TIMEOUT_SECONDS` | `10.0` | Per-request timeout for CompanyBook calls. |

## Run And Verify

Start the service with its dependencies:

```bash
cp .env.example .env
docker compose up --build mongodb redis chromadb auth business gateway knowledge agent
```

Health checks:

```bash
curl http://localhost:8000/health
docker compose logs agent
```

Create a company and partner through the Business-owned gateway routes, then create an assigned agent:

```bash
curl -X POST http://localhost:8000/companies \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Ltd",
    "registration_number": "123456789",
    "city": "Sofia",
    "country": "Bulgaria",
    "address": "1 Business St",
    "accountable_person": "Ivan Ivanov",
    "is_default": true
  }'

curl -X POST http://localhost:8000/partners \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "'"$COMPANY_ID"'",
    "kind": "client",
    "name": "Client Ltd",
    "registration_number": "987654321",
    "city": "Plovdiv",
    "country": "Bulgaria",
    "address": "2 Client St",
    "accountable_person": "Petar Petrov"
  }'

curl -X POST http://localhost:8000/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"My Accountant","agent_type":"accountant","company_id":"'"$COMPANY_ID"'","config":{"provider":"openai","temperature":0.2}}'
```

Create a router agent for the same company:

```bash
curl -X POST http://localhost:8000/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Ops Router","agent_type":"router","company_id":"'"$COMPANY_ID"'","config":{"provider":"openai","temperature":0.1}}'
```

Router delegation currently uses linked delegate documents when they exist (`parent_agent_id` and `delegate_role`) and otherwise falls back to the latest same-user, same-company accountant or inventory agent. The public create-agent endpoint does not yet auto-provision hidden delegates or hide delegate documents from list responses.

Stream chat:

```bash
curl -N -X POST "http://localhost:8000/agents/$AGENT_ID/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"message":"Calculate 20% VAT on 100 and explain it."}'
```

For a new chat, provider and runtime setup happens before the conversation is created. During the turn, `BaseAgent` runs a LangChain `AgentExecutor`; the executor calls RAG, calculator/date, Business-backed financial/partner, or CompanyBook tools when the model requests them, feeds tool results back to the model, and streams only final user-facing chunks as `token` events.

For router chats, setup also resolves compatible accountant and inventory child runtimes before conversation creation. A successful router turn may include an optional `route` SSE event before `done`; the metadata is not persisted in conversation messages.

Load conversation history:

```bash
curl "http://localhost:8000/conversations/$CONVERSATION_ID" \
  -H "Authorization: Bearer $TOKEN"
```

Create an invoice through the Business-owned gateway route:

```bash
curl -X POST http://localhost:8000/invoices \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "'"$COMPANY_ID"'",
    "partner_id": "'"$PARTNER_ID"'",
    "issue_date": "2026-04-26",
    "tax_event_date": "2026-04-26",
    "due_date": "2026-05-10",
    "place_of_supply": "Bulgaria",
    "payment_method": "bank_transfer",
    "currency": "EUR",
    "items": [
      {
        "description": "Accounting consultation",
        "quantity": "1",
        "unit_label": "бр.",
        "unit_price": "100.00",
        "vat_rate": "0.20",
        "category": "services"
      }
    ]
  }'
```

Record an expense through the Business-owned gateway route:

```bash
curl -X POST http://localhost:8000/expenses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "counterparty": "Office Store",
    "expense_date": "2026-04-26",
    "amount": "24.00",
    "currency": "EUR",
    "category": "office",
    "source_document_type": "receipt"
  }'
```

## Common Failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `401 Missing x-user-id header` on direct service calls | Bypassing the gateway without internal auth context | Use the gateway or include `x-user-id` for internal smoke tests. |
| SSE `error` with missing API key | Selected provider env var is empty | Set the provider key or choose `ollama`. |
| Ollama runtime errors | Local Ollama is not running or model is missing | Start Ollama and pull `OLLAMA_CHAT_MODEL`. |
| RAG tool reports retrieval failure | Knowledge Base Service, ChromaDB, or embedding provider is unavailable | Start `knowledge` and `chromadb`; verify `/retrieve`. |
| Partner or invoice tool says the agent needs a company | The agent has `company_id = null` | Assign the agent to a company before using partner or financial write tools. |
| Router returns general help for a finance or stock prompt | No compatible child runtime exists, or the child company scope mismatched the router | Create same-scope accountant/inventory agents or seed linked delegates; verify `company_id` matches. |
| Agent create/update returns `404 Company not found` | Business reported the `company_id` does not exist for this user | Use the owning user's token and an owned company id. |
| Financial or partner tool reports Business unavailable | Business Service is down or unreachable from Agent | Start `business` and verify `BUSINESS_SERVICE_URL`. |
| Chat creates a conversation but no `done` event | Runtime execution or message persistence failed after conversation creation | Inspect the SSE `error` event and service logs. Provider setup failures happen before new conversation creation. |
| Financial tool request returns a validation message | Invalid money/date/category value or missing required invoice/expense fields | Send money values as strings and use supported categories/status values. |

## Architectural Rules

- Keep all endpoints `async def`.
- Every non-streaming endpoint must define a Pydantic `response_model`.
- All user-scoped reads and writes must filter by `x-user-id`.
- Avoid N+1 MongoDB queries; batch with `$in` or aggregation pipelines when expanding data.
- Add MongoDB indexes for fields used in filters, sorts, and unique constraints.
- Do not call ChromaDB directly from this service. RAG access goes through the Knowledge Base Service.
- Do not reintroduce Business-owned repositories, routes, or services into Agent. Use `BusinessClient` for company, partner, invoice, expense, and financial summary operations.
