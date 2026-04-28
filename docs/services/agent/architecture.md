# Agent Service Architecture

## Current State

The Agent Service owns agent instances, chat runtime orchestration, conversation history, and the Accountant Agent tool set (`rag_search`, `calculator`, `date_helper`, Business-backed company/partner tools, Business-backed `query_invoices`, `query_expenses`, `get_financial_summary`, `create_invoice`, `record_expense`, and CompanyBook partner lookup tools).

## Implemented Responsibilities

- User-scoped Agent CRUD.
- Accountant Agent runtime.
- SSE chat streaming.
- MongoDB conversation persistence.
- LLM provider selection for OpenAI, Anthropic, DeepSeek, and Ollama.
- LangChain `AgentExecutor` execution for model-requested tools.
- RAG access through the Knowledge Base Service `POST /retrieve` endpoint.
- Safe arithmetic calculations through a restricted calculator tool.
- Business HTTP access for company validation, partner lookup/write, invoice and expense query/write, and financial summary aggregation.
- Structured financial query and write tools over Business Service contracts.
- CompanyBook.BG partner lookup tools that search Bulgarian companies, import a selected UIC into the scoped partner workflow through Business, and leave invoice creation on the existing `create_invoice` tool path.

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
  business.py
services/
  agent_service.py
  chat_service.py
  conversation_service.py
  companybook_service.py
repositories/
  agent_repo.py
  conversation_repo.py
models/
  agent.py
  chat.py
  conversation.py
  company.py
  financial.py
  partner.py
  companybook.py
runtime/
  base_agent.py
  accountant.py
  registry.py
  tool_context.py
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
```

## Main Patterns

- **Layered architecture:** routes never touch MongoDB or service clients directly.
- **Repository pattern:** Agent-owned MongoDB access is isolated.
- **Strategy pattern:** each agent type implements the shared `BaseAgent` contract.
- **Registry pattern:** `create_agent_runtime()` maps `agent_type` to a concrete runtime class.
- **Factory pattern:** `LLMProviderFactory` creates provider wrappers for OpenAI, Anthropic, DeepSeek, and Ollama.
- **Client adapter pattern:** `BusinessClient` wraps Business Service HTTP calls and translates HTTP failures into tool/service-safe errors.
- **Thin tools:** LangChain tools adapt stable contracts. `rag_search` calls Knowledge Base over HTTP; `calculator` and `date_helper` run locally; financial and CompanyBook tools call Business through `BusinessClient`, never Business repositories directly.

## Runtime Contract

The chat service loads the agent, creates the configured provider, resolves the runtime from the registry, then creates or validates the conversation and streams chunks from `BaseAgent.run()`. New conversations are created only after provider and runtime setup succeeds. Conversations store the agent's current `company_id`; an existing `conversation_id` is accepted only when it belongs to the same user, agent, and company scope.

`BaseAgent.run()` creates a LangChain `AgentExecutor` for each turn. The executor receives the user input and recent chat history, executes model-requested tool calls, feeds tool results back to the model, and emits final user-facing chunks for SSE `token` events. If the provider does not produce streaming chunks, the runtime returns the executor's final output once.

When the Agent Service runs with `AGENT_ENV=development`, `BaseAgent.run()` also logs LangChain tool start, end, and error events to the service console. These logs include bounded previews of tool inputs and outputs for debugging local tool behavior. Production defaults keep this logging disabled, and the runtime does not expose tool logs through SSE or conversation persistence.

Only `agent_type: "accountant"` is currently valid. The Accountant Agent can list and resolve companies, query invoices, query expenses, summarize financial records, search/create partners, search CompanyBook.BG for Bulgarian companies, import a selected registry company as a partner, create invoices, and record expenses. Business-domain reads and writes are delegated to Business Service. Invoice and expense write tools require explicit user confirmation before `confirmed=true` is sent to the tool.

## Business Service Boundary

Agent does not mount company, partner, invoice, expense, or financial summary REST routes. The gateway routes those public prefixes to Business Service while `/agents` and `/conversations` continue to route to Agent Service.

Agent consumes Business Service in two places:

- `AgentService` validates non-null `company_id` values during create, update, and company-filtered list operations through `GET /companies/{company_id}/exists`.
- Accountant tools use `BusinessClient` for company listing/resolution, partner lookup/write, invoice and expense query/write, and financial summary calls.

`BusinessClient` is backed by a long-lived `httpx.AsyncClient` created during FastAPI lifespan startup. It forwards `x-user-id` on every request and normalizes Business HTTP/transport failures into `BusinessClientError`.

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

## Restrictions

- Every route must be `async def`.
- Every endpoint must define Pydantic request/response models, except streaming responses.
- All user data must be scoped by `x-user-id`.
- Do not call ChromaDB directly; use Knowledge Base Service for RAG.
- Add MongoDB indexes for Agent-owned user, agent, and conversation filters.
- Do not reintroduce Business-owned repositories, routes, or services into Agent.
- Financial and partner tool code must call `BusinessClient`, not MongoDB repositories, so REST and chat behavior stay consistent with Business Service.
