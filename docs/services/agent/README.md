# Agent Service

## Current State

The Agent Service implements authenticated company and partner management, company-aware Agent CRUD, MongoDB-backed conversation persistence, Accountant Agent runtime, multi-provider LLM factory, RAG search, calculator tooling, financial invoice/expense APIs, financial LangChain tools, and SSE chat streaming through the API Gateway.

## Responsibility

The Agent Service owns user-created agents and persisted chat history. It receives authenticated user context from the gateway through `x-user-id`; it does not decode JWTs directly.

Implemented responsibilities:

- Agent lifecycle operations: create, list, get, update, and delete.
- Company lifecycle operations for invoice issuer profiles.
- Partner lifecycle operations scoped by `user_id + company_id`.
- Accountant Agent runtime using the Strategy pattern.
- Provider selection for OpenAI, Anthropic, DeepSeek, and Ollama through a Factory pattern.
- Chat request orchestration and `text/event-stream` SSE output.
- Conversation creation and history persistence in MongoDB.
- Invoice and expense REST APIs with user/company-scoped MongoDB persistence.
- Financial summary aggregation across invoice and expense records.
- LangChain `AgentExecutor` orchestration for model-requested tool calls.
- RAG lookup through the Knowledge Base Service `POST /retrieve` contract.
- Safe arithmetic through the calculator tool.
- Structured financial query/write tools for the Accountant Agent.

## Internal Architecture

```text
routes/
  agents.py              # Agent CRUD and chat streaming
  companies.py           # Company issuer profile CRUD
  conversations.py       # Conversation history reads
  invoices.py            # Invoice create/list/get/update
  partners.py            # Company-scoped partner CRUD
  expenses.py            # Expense create/list/get
services/
  agent_service.py       # Agent lifecycle business logic
  chat_service.py        # Runtime orchestration, SSE events, persistence
  company_service.py     # Company ownership and delete protection
  conversation_service.py
  invoice_service.py     # Invoice calculations and status transitions
  partner_service.py     # Partner ownership and invoice delete protection
  expense_service.py     # Expense calculations and deductible amounts
  financial_summary_service.py
repositories/
  agent_repo.py          # User-scoped agent MongoDB access
  company_repo.py        # User-scoped company MongoDB access
  conversation_repo.py   # User-scoped conversation MongoDB access
  invoice_repo.py        # User-scoped invoice MongoDB access
  partner_repo.py        # Company-scoped partner MongoDB access
  expense_repo.py        # User-scoped expense MongoDB access
models/
  agent.py               # Agent config, create/update, response schemas
  company.py             # Company issuer profile schemas and logo validation
  conversation.py        # Message and conversation schemas
  chat.py                # Chat request and event schemas
  financial.py           # Invoice, expense, filter, and summary schemas
  partner.py             # Partner schemas
runtime/
  base_agent.py          # Strategy interface and streaming loop
  accountant.py          # Phase 3 concrete agent
  registry.py            # agent_type -> runtime class
  tool_context.py        # Service bundle injected into LangChain tools
  providers/
    factory.py           # provider -> LangChain provider wrapper
tools/
  rag.py                 # Knowledge Base Service adapter
  calculator.py          # Safe arithmetic adapter
  financial.py           # Invoice, expense, and financial summary tools
```

Routes do request/response handling only. Services own orchestration and business rules. Repositories own MongoDB access. Runtime and tools are called by services, not by route handlers.

## API Surface

All client calls go through the API Gateway at `http://localhost:8000`. Internal direct calls require `x-user-id`.

| Route | Status | Purpose |
|-------|--------|---------|
| `GET /health` | Implemented | Internal health check |
| `POST /companies` | Implemented | Create a current-user company profile |
| `GET /companies?limit=50&offset=0` | Implemented | List current-user companies |
| `GET /companies/{company_id}` | Implemented | Get one owned company |
| `PATCH /companies/{company_id}` | Implemented | Update one owned company |
| `DELETE /companies/{company_id}` | Implemented | Delete an unreferenced owned company |
| `GET /companies/{company_id}/exists` | Implemented | Internal company ownership validation for Knowledge Service |
| `POST /partners` | Implemented | Create a partner under an owned company |
| `GET /partners?company_id=...&kind=...&query=...` | Implemented | List/search partners for one company |
| `GET /partners/{partner_id}?company_id=...` | Implemented | Get one company-scoped partner |
| `PATCH /partners/{partner_id}?company_id=...` | Implemented | Update one company-scoped partner |
| `DELETE /partners/{partner_id}?company_id=...` | Implemented | Delete an unreferenced company-scoped partner |
| `POST /agents` | Implemented | Create an Accountant Agent, optionally assigned to a company |
| `GET /agents?company_id=...&limit=50&offset=0` | Implemented | List current user's agents, optionally filtered by company |
| `GET /agents/{agent_id}` | Implemented | Get one current-user agent |
| `PATCH /agents/{agent_id}` | Implemented | Update name, description, or config |
| `DELETE /agents/{agent_id}` | Implemented | Delete an agent |
| `POST /agents/{agent_id}/chat` | Implemented | Stream chat response via SSE |
| `GET /conversations/{conversation_id}` | Implemented | Load persisted conversation history |
| `POST /invoices` | Implemented | Create an invoice |
| `GET /invoices?limit=50&offset=0` | Implemented | List current user's invoices |
| `GET /invoices/{invoice_id}` | Implemented | Get one current-user invoice |
| `PATCH /invoices/{invoice_id}` | Implemented | Update invoice status, due date, or notes |
| `POST /expenses` | Implemented | Record an expense |
| `GET /expenses?limit=50&offset=0` | Implemented | List current user's expenses |
| `GET /expenses/{expense_id}` | Implemented | Get one current-user expense |

## Companies And Partners

The Agent Service owns the `companies` and `partners` collections. A company represents the invoice issuer profile and is scoped by `user_id`. Partners represent reusable clients, suppliers, or both, and are scoped by `user_id + company_id`.

Ownership failures intentionally return `404` so callers cannot distinguish "does not exist" from "belongs to another user/company". Company deletes return `409` while agents, invoices, or partners still reference the company. Partner deletes return `409` while invoices reference the partner; existing invoices remain historically correct because they store recipient snapshots.

Example workflow:

1. `POST /companies` creates the invoice issuer profile.
2. `POST /partners` creates a recipient under that company.
3. `POST /agents` may assign an Accountant Agent to the company via `company_id`.
4. `POST /invoices` requires `company_id` and uses either `partner_id` or full recipient details.
5. `POST /documents` in the Knowledge Base Service requires the same `company_id` and validates it through Agent Service.

## Financial Records

The Agent Service owns the `invoices`, `expenses`, and invoice `counters` collections. Invoices are scoped by `user_id + company_id` for new records and may reference a `partner_id`; expenses remain user-scoped. Public client traffic reaches these routes through the gateway prefixes `/invoices/*` and `/expenses/*`.

Money values are modeled as Python `Decimal`, stored in MongoDB as BSON `Decimal128`, and serialized in JSON responses as strings to avoid float precision loss. Date-only API fields are accepted as ISO `YYYY-MM-DD` strings and stored as UTC datetimes for range queries.

Invoice numbers are generated atomically per user/company/year for company-scoped invoices. Invoice totals are calculated server-side from line items:

- `subtotal = quantity * unit_price`
- `vat_amount = subtotal * vat_rate`
- `total = subtotal + vat_amount`

Expense records can be entered as a single `amount` or from optional purchased item lines. If items are present, the service calculates the stored amount from item totals. Deductible expenses store `deductible_amount = amount * deductible_rate`; non-deductible expenses store `0.00`.

Invoice creation persists:

- `supplier_snapshot` from the selected company.
- `recipient_snapshot` from the selected partner or explicit recipient input.
- Bulgarian invoice fields including `tax_event_date`, `place_of_supply`, `payment_method`, bank details, `amount_in_words`, `vat_reason`, `recipient_name`, `compiler_name`, `original_label`, and line-item `unit_label`.

### Accountant Financial Tools

The Accountant Agent has five financial tools:

| Tool | Purpose | Key parameters |
|------|---------|----------------|
| `query_invoices` | Query current-user invoices | `company_id`, `partner_id`, `status`, `date_from`, `date_to`, `counterparty`, `amount_min`, `amount_max`, `category`, `limit` |
| `query_expenses` | Query current-user expenses | `category`, `counterparty`, `date_from`, `date_to`, `deductible`, `amount_min`, `amount_max`, `limit` |
| `get_financial_summary` | Summarize invoice and expense totals | `date_from`, `date_to`, `group_by`, `include_invoices`, `include_expenses` |
| `create_invoice` | Create an invoice after explicit confirmation | Invoice create fields plus `confirmed` |
| `record_expense` | Record an expense after explicit confirmation | Expense create fields plus `confirmed` |
| `search_partners` | Search partners in the assigned agent company | `query`, `kind`, `limit` |
| `resolve_partner_by_name` | Resolve a named client/supplier before invoice creation | `name`, `kind`, `max_matches` |
| `create_partner` | Create a partner in the assigned agent company | Partner create fields |

Write tools refuse to persist data until the model sets `confirmed=true`, which the system prompt instructs it to do only after the user explicitly confirms the summarized record. Partner and financial write tools also refuse when the current agent has no `company_id`; RAG still works for shared `global_tax` in that case.

### Development Tool Logging

Set `AGENT_ENV=development` for the Agent Service to log LangChain tool start, end, and error events from `BaseAgent.run()`. Development logs include the tool name, LangChain run ID, current agent/user context, and bounded input/output previews so large RAG or financial results do not flood the console. This logging is local observability only; it does not change SSE events or persisted conversation messages.

## SSE Event Protocol

`POST /agents/{agent_id}/chat` returns `text/event-stream`. The gateway passes through the stream when clients send `Accept: text/event-stream`.

| Event | Data | When emitted |
|-------|------|--------------|
| `conversation` | `{ "conversation_id": "..." }` | A new conversation is created because `conversation_id` was omitted. |
| `start` | `{ "conversation_id": "..." }` | Runtime initialization succeeded and token streaming is starting. |
| `token` | `{ "content": "..." }` | A streamed assistant token or chunk is available. |
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

event: done
data: {"conversation_id":"665f1f77c9e0f7a8093bb711"}
```

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `MONGODB_URL` | `mongodb://mongodb:27017` | MongoDB connection string. |
| `DB_NAME` | `agents` | Database used by the service. |
| `KNOWLEDGE_SERVICE_URL` | `http://knowledge:8003` | Internal Knowledge Base Service URL. |
| `OPENAI_API_KEY` | empty | Required for `provider: "openai"`. |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` | Default OpenAI chat model. |
| `ANTHROPIC_API_KEY` | empty | Required for `provider: "anthropic"`. |
| `ANTHROPIC_CHAT_MODEL` | `claude-3-5-haiku-latest` | Default Anthropic chat model. |
| `DEEPSEEK_API_KEY` | empty | Required for `provider: "deepseek"`. |
| `DEEPSEEK_CHAT_MODEL` | `deepseek-chat` | Default DeepSeek chat model. |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Local Ollama server URL. |
| `OLLAMA_CHAT_MODEL` | `llama3.1` | Default Ollama model. |
| `DEFAULT_AGENT_PROVIDER` | `openai` | Provider used when client omits one. |
| `MAX_HISTORY_MESSAGES` | `20` | Recent conversation messages sent to the runtime. |
| `RAG_TOP_K` | `5` | Number of chunks requested from Knowledge Base retrieval. |

## Run And Verify

Start the service with its dependencies:

```bash
cp .env.example .env
docker compose up --build mongodb redis chromadb auth gateway knowledge agent
```

Health checks:

```bash
curl http://localhost:8000/health
docker compose logs agent
```

Create a company, partner, and assigned agent:

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

Stream chat:

```bash
curl -N -X POST "http://localhost:8000/agents/$AGENT_ID/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"message":"Calculate 20% VAT on 100 and explain it."}'
```

For a new chat, provider and runtime setup happens before the conversation is created. During the turn, `BaseAgent` runs a LangChain `AgentExecutor`; the executor calls `rag_search` or `calculator` when the model requests tools, feeds tool results back to the model, and streams only final user-facing chunks as `token` events.

Load conversation history:

```bash
curl "http://localhost:8000/conversations/$CONVERSATION_ID" \
  -H "Authorization: Bearer $TOKEN"
```

Create an invoice:

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

Record an expense:

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
| Company/partner request returns `404` for an existing id | The id belongs to another user/company or the company was not supplied on partner routes | Use the owning user's token and include the matching `company_id`. |
| Chat creates a conversation but no `done` event | Runtime execution or message persistence failed after conversation creation | Inspect the SSE `error` event and service logs. Provider setup failures happen before new conversation creation. |
| Invoice status update returns `400` | Invalid status transition, such as `paid` back to `draft` | Use the allowed workflow: `draft -> sent/cancelled`, `sent -> paid/overdue/cancelled`, `overdue -> paid/cancelled`. |
| Financial request returns `422` | Invalid money/date/category value or missing required invoice/expense fields | Send money values as strings and use supported categories/status values. |

## Architectural Rules

- Keep all endpoints `async def`.
- Every non-streaming endpoint must define a Pydantic `response_model`.
- All user-scoped reads and writes must filter by `x-user-id`.
- Avoid N+1 MongoDB queries; batch with `$in` or aggregation pipelines when expanding data.
- Add MongoDB indexes for fields used in filters, sorts, and unique constraints.
- Do not call ChromaDB directly from this service. RAG access goes through the Knowledge Base Service.
