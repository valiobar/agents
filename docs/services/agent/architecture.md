# Agent Service Architecture

## Current State

The Agent Service owns agent instances, chat runtime orchestration, conversation history, invoice and expense records, and the Accountant Agent tool set (`rag_search`, `calculator`, `date_helper`, partner/company tools, `query_invoices`, `query_expenses`, `get_financial_summary`, `create_invoice`, `record_expense`, and CompanyBook partner lookup tools).

## Implemented Responsibilities

- User-scoped Agent CRUD.
- Accountant Agent runtime.
- SSE chat streaming.
- MongoDB conversation persistence.
- MongoDB invoice and expense persistence with Decimal128 money storage.
- Invoice and expense REST APIs.
- Financial summary aggregation.
- LLM provider selection for OpenAI, Anthropic, DeepSeek, and Ollama.
- LangChain `AgentExecutor` execution for model-requested tools.
- RAG access through the Knowledge Base Service `POST /retrieve` endpoint.
- Safe arithmetic calculations through a restricted calculator tool.
- Structured financial query and write tools.
- CompanyBook.BG partner lookup tools that search Bulgarian companies, import a selected UIC into the scoped partner workflow, and leave invoice creation on the existing `create_invoice` path.

## Layers

```text
routes/ -> services/ -> repositories/ -> models/
                     \-> runtime/
                     \-> tools/
```

| Layer | Responsibility |
|-------|----------------|
| `routes/` | HTTP endpoints, request/response models, dependency injection |
| `services/` | Business rules, user scoping, orchestration |
| `repositories/` | MongoDB access only |
| `models/` | Pydantic schemas |
| `runtime/` | Base agent strategy, concrete agents, registry, provider factory |
| `tools/` | LangChain tool adapters over internal or service-to-service contracts |

## Concrete Modules

```text
routes/
  agents.py
  conversations.py
  invoices.py
  expenses.py
services/
  agent_service.py
  chat_service.py
  conversation_service.py
  invoice_service.py
  expense_service.py
  financial_summary_service.py
repositories/
  agent_repo.py
  conversation_repo.py
  invoice_repo.py
  expense_repo.py
  financial_utils.py
models/
  agent.py
  chat.py
  conversation.py
  financial.py
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
  financial.py
  companybook.py
```

## Main Patterns

- **Layered architecture:** routes never touch MongoDB directly.
- **Repository pattern:** all MongoDB access is isolated.
- **Strategy pattern:** each agent type implements the shared `BaseAgent` contract.
- **Registry pattern:** `create_agent_runtime()` maps `agent_type` to a concrete runtime class.
- **Factory pattern:** `LLMProviderFactory` creates provider wrappers for OpenAI, Anthropic, DeepSeek, and Ollama.
- **Thin tools:** LangChain tools adapt stable contracts. `rag_search` calls Knowledge Base over HTTP; `calculator` evaluates restricted arithmetic locally; financial and CompanyBook tools call Agent Service services, never repositories directly.

## Runtime Contract

The chat service loads the agent, creates the configured provider, resolves the runtime from the registry, then creates or validates the conversation and streams chunks from `BaseAgent.run()`. New conversations are created only after provider and runtime setup succeeds. Conversations store the agent's current `company_id`; an existing `conversation_id` is accepted only when it belongs to the same user, agent, and company scope.

`BaseAgent.run()` creates a LangChain `AgentExecutor` for each turn. The executor receives the user input and recent chat history, executes model-requested tool calls, feeds tool results back to the model, and emits final user-facing chunks for SSE `token` events. If the provider does not produce streaming chunks, the runtime returns the executor's final output once.

When the Agent Service runs with `AGENT_ENV=development`, `BaseAgent.run()` also logs LangChain tool start, end, and error events to the service console. These logs include bounded previews of tool inputs and outputs for debugging local tool behavior. Production defaults keep this logging disabled, and the runtime does not expose tool logs through SSE or conversation persistence.

Only `agent_type: "accountant"` is currently valid. The Accountant Agent can query invoices, query expenses, summarize financial records, search/create partners, search CompanyBook.BG for Bulgarian companies, import a selected registry company as a partner, create invoices, and record expenses. Write tools require explicit user confirmation before `confirmed=true` is sent to the tool.

## CompanyBook.BG Integration

The Accountant Agent has two external registry tools:

| Tool | Purpose | Writes data |
|------|---------|-------------|
| `search_companybook_companies` | Calls `GET /companies/search` with a trimmed name or UIC query and returns candidate companies for user selection. | No |
| `import_companybook_partner` | Calls `GET /companies/{uic}?with_data=true`, maps the selected company into `PartnerCreate`, and creates or reuses a scoped partner. | Yes, only through `PartnerService` |

Required configuration:

| Env var | Default | Notes |
|---------|---------|-------|
| `COMPANYBOOK_API_KEY` | empty | Optional at startup. Tool calls return a user-safe configuration error when missing. |
| `COMPANYBOOK_BASE_URL` | `https://api.companybook.bg/api` | Base URL for CompanyBook.BG API calls. |
| `COMPANYBOOK_TIMEOUT_SECONDS` | `10.0` | Per-request timeout for search and detail calls. |

The integration does not store raw CompanyBook financial data or documents. It persists only the user-selected partner fields required by the existing partner model. Partner imports first search local partners by exact UIC, then create through `PartnerService`; duplicate-key races are resolved by searching the partner by UIC again. If CompanyBook omits required invoice recipient fields (`city`, `address`, `accountable_person`, etc.), the tool returns `missing_fields` and `partner_draft` so the agent asks the user only for the missing details.

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
- Add MongoDB indexes for user, agent, status, and date filters.
- Financial tool code must call services, not repositories, so REST and chat behavior stay consistent.
