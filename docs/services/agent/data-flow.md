# Agent Service Data Flow

## Gateway List Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Agent
    participant Business

    Client->>Gateway: GET /agents?company_id=...&limit=20&offset=0
    Gateway->>Gateway: validate JWT and inject x-user-id
    Gateway->>Agent: proxy to Agent Service
    opt company_id supplied
        Agent->>Business: GET /companies/{company_id}/exists + x-user-id
        Business-->>Agent: exists true/false
    end
    Agent-->>Gateway: agent list for user and optional company
    Gateway-->>Client: agent list response
```

## Agent CRUD Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Agent
    participant Business
    participant Mongo

    Client->>Gateway: POST /agents + optional company_id + access token
    Gateway->>Gateway: validate JWT
    Gateway->>Agent: forward with x-user-id
    opt company_id supplied
        Agent->>Business: GET /companies/{company_id}/exists + x-user-id
        Business-->>Agent: exists true/false
    end
    Agent->>Agent: validate request and defaults
    Agent->>Mongo: insert agent scoped to user_id
    Mongo-->>Agent: saved agent
    Agent-->>Gateway: AgentResponse
    Gateway-->>Client: AgentResponse
```

All CRUD operations are scoped by the gateway-injected `x-user-id`. Agent create/update validates a non-null `company_id` against Business Service, and list can filter by `company_id` after the same ownership check. Invalid IDs and cross-user access return `404`; Business availability failures return `503`.

## Business-Owned Company And Partner Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Business
    participant Mongo

    Client->>Gateway: POST /companies + access token
    Gateway->>Business: forward with x-user-id
    Business->>Mongo: insert company scoped to user_id
    Mongo-->>Business: saved company
    Business-->>Gateway: CompanyResponse
    Gateway-->>Client: CompanyResponse

    Client->>Gateway: POST /partners { company_id, ... }
    Gateway->>Business: forward with x-user-id
    Business->>Mongo: verify company by user_id + company_id
    Business->>Mongo: insert partner scoped to user_id + company_id
    Mongo-->>Business: saved partner
    Business-->>Gateway: PartnerResponse
    Gateway-->>Client: PartnerResponse
```

Companies represent invoice issuer profiles. Partners represent reusable clients, suppliers, or both under one company. These routes are no longer mounted by Agent Service. Gateway preserves the public URLs and routes them to Business Service. Agent consumes the same data only through `BusinessClient`.

## Chat Streaming Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Agent
    participant Runtime as BaseAgent/RouterAgent
    participant Executor as AgentExecutor
    participant Graph as Router Graph
    participant KB as Knowledge Base
    participant Business
    participant LLM
    participant Mongo

    Client->>Gateway: POST /agents/{id}/chat, Accept: text/event-stream
    Gateway->>Gateway: validate JWT and rate limit
    Gateway->>Agent: forward with x-user-id
    Agent->>Mongo: load agent
    Agent->>Agent: create provider and runtime
    opt router runtime
        Agent->>Mongo: resolve linked or same-scope accountant/inventory children
        Agent->>Agent: reject child if company_id differs from router
    end
    alt no conversation_id
        Agent->>Mongo: create conversation
        Agent-->>Gateway: event: conversation
        Gateway-->>Client: event: conversation
    else existing conversation_id
        Agent->>Mongo: load and validate conversation
    end
    Agent-->>Gateway: event: start
    Agent->>Runtime: run(message, recent history)
    alt accountant or inventory runtime
        Runtime->>Runtime: prepare_run_input() and prepare_tools()
        Runtime->>Executor: prompt + history + available tools
        Executor->>LLM: prompt + history + available tools
        LLM-->>Executor: tool calls or final chunks
        opt model invokes rag_search
            Executor->>KB: POST /retrieve with x-user-id and company_id
            KB-->>Executor: relevant chunks
        end
        opt model invokes business-domain tool
            Executor->>Business: HTTP request through BusinessClient + x-user-id
            Business-->>Executor: validated domain response
        end
        Executor->>LLM: tool results for final response
        LLM-->>Executor: streamed final chunks
        Executor-->>Runtime: LangChain stream events
        Runtime->>Runtime: on_event(), on_chunk(), collect usage metadata
    else router runtime
        Runtime->>Graph: classify route and select branch
        Graph->>LLM: structured route decision
        opt specialist branch
            Graph->>Runtime: run configured child runtime
        end
        opt general branch
            Graph->>LLM: no-tool general fallback
        end
    end
    Runtime-->>Agent: token chunks
    Agent-->>Gateway: event: token
    Gateway-->>Client: event: token
    Agent->>Runtime: consume_usage_events()
    Agent->>Mongo: persist messages
    alt persistence succeeded
        Agent->>Mongo: insert usage_events
        opt router route metadata
            Agent-->>Gateway: event: route
            Gateway-->>Client: event: route
        end
        Agent-->>Gateway: event: done
        Gateway-->>Client: event: done
    else provider/runtime/persistence failed
        Agent-->>Gateway: event: error
        Gateway-->>Client: event: error
    end
```

Provider and runtime setup happens before new conversation creation, so setup errors emit `error` without inserting an empty conversation. Router child runtime resolution also happens before conversation creation. `done` is emitted only after the user and assistant messages are persisted. Raw provider usage events are inserted after message persistence; usage insert failures are logged but do not replace a successful chat with an SSE `error`.

Runtime hooks are internal to `BaseAgent`. They may transform inputs, tools, normalized LangChain events, streamed chunks, final fallback output, and run metadata before the Agent Service emits SSE or writes MongoDB. Hooks must not emit SSE or persist data directly.

## SSE Events

| Event | Data | Notes |
|-------|------|-------|
| `conversation` | `{ "conversation_id": "..." }` | Only emitted for a new conversation. |
| `start` | `{ "conversation_id": "..." }` | Runtime is ready and streaming begins. |
| `token` | `{ "content": "..." }` | One streamed assistant chunk. |
| `route` | `{ "predicted_route": "inventory", "executed_route": "inventory", "reason": "...", "confidence": 0.95, "company_id": "...", "company_scope": "assigned" }` | Optional router metadata emitted after persistence and before `done`. |
| `error` | `{ "message": "..." }` | Terminal error for lookup, provider setup, runtime execution, or message persistence. |
| `done` | `{ "conversation_id": "..." }` | Messages were persisted after successful runtime completion. |

The public SSE event names and payloads do not include usage data. Usage is stored internally in `usage_events` for future billing or analytics. Route metadata is diagnostic and non-persisted; clients should ignore it if they do not display routing information.

## Runtime Usage Flow

```mermaid
sequenceDiagram
    participant Runtime as BaseAgent
    participant Logger as AgentLoopLogger
    participant Chat as ChatService
    participant UsageRepo
    participant Mongo

    Runtime->>Logger: track LangChain LLM stream/end events
    Logger->>Logger: extract provider token metadata
    Logger-->>Runtime: LLMUsageEvent values
    Runtime-->>Chat: consume_usage_events()
    Chat->>Chat: keep only events with provider-reported token fields
    Chat->>Mongo: append user and assistant messages
    Chat->>UsageRepo: insert_many(UsageEventCreate[])
    UsageRepo->>Mongo: insert usage_events with idempotency_key
```

The usage ledger records raw provider/model facts only: user, agent, conversation, provider, model, optional run id, LLM call index, input/output/total token counts when reported, stream chunk/character counts, timing, and `source="agent_runtime"`. It does not estimate missing tokens and does not compute billing cost. Router classifier/general calls are attributed to the router agent id; delegated child calls keep the accountant or inventory runtime agent id.

## RAG Tool Flow

```mermaid
sequenceDiagram
    participant Runtime as Accountant Runtime
    participant Executor as AgentExecutor
    participant Tool as rag_search
    participant KB as Knowledge Base Service
    participant Chroma as ChromaDB
    participant Mongo

    Runtime->>Executor: message + history + tools
    Executor->>Tool: query string requested by model
    Tool->>KB: POST /retrieve + x-user-id
    KB->>Chroma: search global_tax and user collection
    KB->>Mongo: read document metadata as needed
    KB-->>Tool: chunks with scores and metadata
    Tool-->>Executor: compact context text
    Executor->>Runtime: final response chunks
```

The Agent Service never calls ChromaDB directly. RAG retrieval remains owned by the Knowledge Base Service. Assigned agents send their `company_id` so uploaded chunks are filtered by company; unassigned agents set `include_user_documents=false` and use shared `global_tax` only.

## Business-Backed Financial Tool Flow

```mermaid
sequenceDiagram
    participant Runtime as Accountant Runtime
    participant Tool as Finance Tool
    participant Client as BusinessClient
    participant Business as Business Service
    participant Mongo

    Runtime->>Tool: call company/partner/financial tool
    Tool->>Tool: validate arguments and resolve company scope
    Tool->>Client: typed method call
    Client->>Business: HTTP request with x-user-id
    Business->>Mongo: MongoDB operation scoped by user_id and company_id where applicable
    Mongo-->>Business: result
    Business-->>Client: Pydantic-compatible JSON response
    Client-->>Tool: parsed model or BusinessClientError
    Tool-->>Runtime: compact JSON/text result
```

Financial records are available from Business REST endpoints and Accountant Agent tools. Business Service owns calculations, filters, company ownership, user scoping, persistence, and summary aggregation. Agent owns only tool argument validation, company-scope enforcement for assigned agents, and conversion of Business responses into compact tool output.

Money values are modeled as `Decimal` in shared Pydantic schemas and sent to Business as JSON strings. Business stores them in MongoDB as BSON `Decimal128` and serializes responses as strings.

Invoice creation in Agent tools resolves the company scope and waits for explicit confirmation, then Business validates `company_id`, verifies that `partner_id` belongs to the same company when present, calculates totals, and stores immutable `supplier_snapshot` and `recipient_snapshot` values for historical PDF rendering.

The write tools `create_invoice` and `record_expense` require `confirmed=true`. Without confirmation, they return a confirmation-required message and do not call Business. Partner and invoice tools also require the current agent to be assigned to a company or a resolved `company_id` to be supplied.

## CompanyBook Partner Import Flow

```mermaid
sequenceDiagram
    participant Runtime as Accountant Runtime
    participant Tool as CompanyBook Tool
    participant CB as CompanyBook.BG API
    participant Business as Business Service
    participant Mongo

    Runtime->>Tool: search_companybook_companies(name or UIC)
    Tool->>CB: GET /companies/search?name=...&with_data=false
    CB-->>Tool: candidate companies
    Tool-->>Runtime: JSON candidates for user selection
    Runtime->>Tool: import_companybook_partner(uic, kind, company_id?)
    Tool->>Business: GET /partners scoped by user_id + company_id + UIC
    alt existing exact UIC match
        Business-->>Tool: existing partner
        Tool-->>Runtime: existing partner JSON
    else no exact UIC match
        Tool->>CB: GET /companies/{uic}?with_data=true
        CB-->>Tool: company detail
        alt required partner fields missing
            Tool-->>Runtime: missing_fields + partner_draft
        else complete partner payload
            Tool->>Business: POST /partners with PartnerCreate
            Business->>Mongo: insert partner with unique user_id + company_id + registration_number
            Mongo-->>Business: saved partner
            Business-->>Tool: saved partner
            Tool-->>Runtime: saved partner JSON
        end
    end
```

`search_companybook_companies` is read-only and should be used after local partner search, or when the user explicitly asks to search the Bulgarian registry. `import_companybook_partner` is company-scoped: assigned agents use their assigned `company_id`, while unassigned agents must resolve and pass a `company_id` before import.

The import tool reuses existing partners by exact UIC before making a new write. If another request creates the same partner between lookup and insert, Business returns a conflict and the tool resolves the partner by UIC again. If the registry detail is incomplete, no partner is written; the returned `partner_draft` contains all mapped fields and `missing_fields` tells the agent which specific values to request from the user.

## Write Paths

| Data | Write Path |
|------|------------|
| Companies | Gateway -> Business company routes -> Business company service -> Business company repo -> MongoDB |
| Partners | Gateway or Agent partner tools -> Business partner routes/client -> Business partner service -> Business partner repo -> MongoDB |
| Agent config | Gateway -> Agent routes -> Agent service -> Agent repo -> MongoDB |
| Conversation messages | Chat service -> Conversation repo -> MongoDB |
| LLM usage events | Chat service after conversation persistence -> Usage repo -> MongoDB `usage_events` |
| Invoices | Gateway or Agent `create_invoice` tool -> Business invoice route/client -> Business invoice service -> Business invoice repo -> MongoDB |
| Expenses | Gateway or Agent `record_expense` tool -> Business expense route/client -> Business expense service -> Business expense repo -> MongoDB |
| CompanyBook partner import | Accountant tool -> CompanyBook.BG API -> Business partner route/client -> Business partner service -> Business partner repo -> MongoDB |
