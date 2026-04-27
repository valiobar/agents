# Agent Service Data Flow

## Gateway List Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Agent

    Client->>Gateway: GET /agents?company_id=...&limit=20&offset=0
    Gateway->>Gateway: validate JWT and inject x-user-id
    Gateway->>Agent: proxy to Agent Service
    Agent-->>Gateway: agent list for user and optional company
    Gateway-->>Client: agent list response
```

## Agent CRUD Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Agent
    participant Mongo

    Client->>Gateway: POST /agents + optional company_id + access token
    Gateway->>Gateway: validate JWT
    Gateway->>Agent: forward with x-user-id
    Agent->>Agent: validate request, company ownership, and defaults
    Agent->>Mongo: insert agent scoped to user_id
    Mongo-->>Agent: saved agent
    Agent-->>Gateway: AgentResponse
    Gateway-->>Client: AgentResponse
```

All CRUD operations are scoped by the gateway-injected `x-user-id`. Agent create/update validates a non-null `company_id` against the current user, and list can filter by `company_id`. Invalid IDs and cross-user access return `404` from service-layer checks.

## Company And Partner Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Agent
    participant Mongo

    Client->>Gateway: POST /companies + access token
    Gateway->>Agent: forward with x-user-id
    Agent->>Mongo: insert company scoped to user_id
    Mongo-->>Agent: saved company
    Agent-->>Gateway: CompanyResponse
    Gateway-->>Client: CompanyResponse

    Client->>Gateway: POST /partners { company_id, ... }
    Gateway->>Agent: forward with x-user-id
    Agent->>Mongo: verify company by user_id + company_id
    Agent->>Mongo: insert partner scoped to user_id + company_id
    Mongo-->>Agent: saved partner
    Agent-->>Gateway: PartnerResponse
    Gateway-->>Client: PartnerResponse
```

Companies represent invoice issuer profiles. Partners represent reusable clients, suppliers, or both under one company. Cross-user and cross-company IDs return `404`; deletes return `409` while dependent agents, partners, or invoices still reference the record.

## Chat Streaming Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Agent
    participant Runtime as AgentExecutor
    participant KB as Knowledge Base
    participant LLM
    participant Mongo

    Client->>Gateway: POST /agents/{id}/chat, Accept: text/event-stream
    Gateway->>Gateway: validate JWT and rate limit
    Gateway->>Agent: forward with x-user-id
    Agent->>Mongo: load agent
    Agent->>Agent: create provider and runtime
    alt no conversation_id
        Agent->>Mongo: create conversation
        Agent-->>Gateway: event: conversation
        Gateway-->>Client: event: conversation
    else existing conversation_id
        Agent->>Mongo: load and validate conversation
    end
    Agent-->>Gateway: event: start
    Agent->>Runtime: message + recent history
    Runtime->>LLM: prompt + history + available tools
    LLM-->>Runtime: tool calls or final chunks
    opt model invokes rag_search
        Runtime->>KB: POST /retrieve with x-user-id and company_id
        KB-->>Runtime: relevant chunks
    end
    Runtime->>LLM: tool results for final response
    LLM-->>Runtime: streamed final chunks
    Runtime-->>Agent: token chunks
    Agent-->>Gateway: event: token
    Gateway-->>Client: event: token
    Agent->>Mongo: persist messages
    alt persistence succeeded
        Agent-->>Gateway: event: done
        Gateway-->>Client: event: done
    else provider/runtime/persistence failed
        Agent-->>Gateway: event: error
        Gateway-->>Client: event: error
    end
```

Provider and runtime setup happens before new conversation creation, so setup errors emit `error` without inserting an empty conversation. `done` is emitted only after the user and assistant messages are persisted.

## SSE Events

| Event | Data | Notes |
|-------|------|-------|
| `conversation` | `{ "conversation_id": "..." }` | Only emitted for a new conversation. |
| `start` | `{ "conversation_id": "..." }` | Runtime is ready and streaming begins. |
| `token` | `{ "content": "..." }` | One streamed assistant chunk. |
| `error` | `{ "message": "..." }` | Terminal error for lookup, provider setup, runtime execution, or message persistence. |
| `done` | `{ "conversation_id": "..." }` | Messages were persisted after successful runtime completion. |

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

## Financial Records Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Runtime as Accountant Runtime
    participant Tool as Finance Tool
    participant Service as Invoice/Expense Service
    participant Repo as Repository
    participant Mongo

    alt REST API
        Client->>Gateway: /invoices or /expenses + access token
        Gateway->>Gateway: validate JWT and rate limit
        Gateway->>Service: proxy to Agent route with x-user-id
    else Chat tool
        Runtime->>Tool: call search_partners/query_invoices/query_expenses/get_financial_summary
        Tool->>Service: validated domain operation
    end
    Service->>Repo: persistence/query request
    Repo->>Mongo: MongoDB operation scoped by user_id and company_id where applicable
    Mongo-->>Repo: result
    Repo-->>Service: domain result
    alt REST API
        Service-->>Gateway: Pydantic response model
        Gateway-->>Client: JSON response
    else Chat tool
        Service-->>Tool: domain result
        Tool-->>Runtime: compact JSON/text result
    end
```

Financial records are available from both REST endpoints and Accountant Agent tools. The shared service/repository layer keeps calculations, filters, company ownership, and user scoping consistent between the two entry points.

Money values are modeled as `Decimal`, stored in MongoDB as BSON `Decimal128`, and serialized to JSON as strings. Invoice and expense dates are accepted as date-only API values and stored as UTC datetimes for indexed range queries.

Invoice creation validates `company_id`, verifies that `partner_id` belongs to the same company when present, calculates totals, and stores immutable `supplier_snapshot` and `recipient_snapshot` values for historical PDF rendering.

The write tools `create_invoice` and `record_expense` require `confirmed=true`. Without confirmation, they return a confirmation-required message and do not write to MongoDB. Partner and invoice tools also require the current agent to be assigned to a company.

## CompanyBook Partner Import Flow

```mermaid
sequenceDiagram
    participant Runtime as Accountant Runtime
    participant Tool as CompanyBook Tool
    participant CB as CompanyBook.BG API
    participant Partner as Partner Service
    participant Mongo

    Runtime->>Tool: search_companybook_companies(name or UIC)
    Tool->>CB: GET /companies/search?name=...&with_data=false
    CB-->>Tool: candidate companies
    Tool-->>Runtime: JSON candidates for user selection
    Runtime->>Tool: import_companybook_partner(uic, kind, company_id?)
    Tool->>Partner: list_partners scoped by user_id + company_id + UIC
    alt existing exact UIC match
        Partner-->>Tool: existing partner
        Tool-->>Runtime: existing partner JSON
    else no exact UIC match
        Tool->>CB: GET /companies/{uic}?with_data=true
        CB-->>Tool: company detail
        alt required partner fields missing
            Tool-->>Runtime: missing_fields + partner_draft
        else complete partner payload
            Tool->>Partner: create_partner(user_id, PartnerCreate)
            Partner->>Mongo: insert partner with unique user_id + company_id + registration_number
            Mongo-->>Partner: saved partner
            Partner-->>Tool: saved partner
            Tool-->>Runtime: saved partner JSON
        end
    end
```

`search_companybook_companies` is read-only and should be used after local partner search, or when the user explicitly asks to search the Bulgarian registry. `import_companybook_partner` is company-scoped: assigned agents use their assigned `company_id`, while unassigned agents must resolve and pass a `company_id` before import.

The import tool reuses existing partners by exact UIC before making a new write. If another request creates the same partner between lookup and insert, MongoDB's unique index raises a duplicate-key error and the tool resolves the partner by UIC again. If the registry detail is incomplete, no partner is written; the returned `partner_draft` contains all mapped fields and `missing_fields` tells the agent which specific values to request from the user.

## Write Paths

| Data | Write Path |
|------|------------|
| Companies | Gateway -> Company routes -> Company service -> Company repo -> MongoDB |
| Partners | Gateway or partner tools -> Partner service -> Partner repo -> MongoDB |
| Agent config | Gateway -> Agent routes -> Agent service -> Agent repo -> MongoDB |
| Conversation messages | Chat service -> Conversation repo -> MongoDB |
| Invoices | Gateway or `create_invoice` tool -> Invoice service -> Invoice repo -> MongoDB |
| Expenses | Gateway or `record_expense` tool -> Expense service -> Expense repo -> MongoDB |
| CompanyBook partner import | Accountant tool -> CompanyBook.BG API -> Partner service -> Partner repo -> MongoDB |
