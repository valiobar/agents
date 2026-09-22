# Frontend Data Flow

## Current State

Docker Compose publishes the frontend on `http://localhost:3010` (container port 3000). `npm run dev` listens on `http://localhost:3000`. Browser requests use `NEXT_PUBLIC_GATEWAY_URL` (`/gateway-api` by default), which Next.js rewrites to `GATEWAY_URL`. From the host, the gateway is `http://localhost:8010` (container port 8000). On the droplet those URLs are `http://159.89.26.67:3010` and `http://159.89.26.67:8010`. The gateway allows the frontend origins in `CORS_ORIGINS` and proxies authenticated requests to internal services.

## Authentication Flow

```mermaid
sequenceDiagram
    participant User
    participant FE as Frontend
    participant GW as API Gateway
    participant Auth as Auth Service

    User->>FE: submit email/password
    FE->>GW: POST /auth/login
    GW->>Auth: proxy request
    Auth-->>GW: access + refresh token pair
    GW-->>FE: token pair
    FE->>FE: store session in HTTP-only auth cookie
    FE-->>User: redirect to dashboard
```

## Google Sign-In Flow

```mermaid
sequenceDiagram
    participant User
    participant FE as Frontend / NextAuth
    participant Google
    participant GW as API Gateway
    participant Auth as Auth Service

    User->>FE: click Continue with Google
    FE->>Google: OAuth redirect
    Google-->>FE: OAuth callback + ID token
    FE->>GW: POST /auth/oauth/google { id_token }
    GW->>Auth: proxy request
    Auth-->>GW: access + refresh token pair
    GW-->>FE: token pair
    FE->>FE: create session
```

## Server State Flow

```mermaid
sequenceDiagram
    participant Page as App Route
    participant Query as TanStack Query
    participant API as shared/api/client
    participant GW as API Gateway

    Page->>Query: useCompanies/usePartners/useAgents/useInvoices/useExpenses
    Query->>API: typed request
    API->>GW: HTTP with access token
    GW-->>API: JSON response
    API-->>Query: typed data
    Query-->>Page: cached server state
```

## Company And Partner Flow

```mermaid
sequenceDiagram
    participant User
    participant Page as Dashboard Pages
    participant Form as Company/Partner Feature
    participant Query as TanStack Query
    participant API as shared/api/client
    participant GW as API Gateway

    User->>Page: open Companies or Partners
    Page->>Query: useCompanies / usePartners(company_id)
    Query->>API: GET /companies or GET /partners?company_id=...
    API->>GW: HTTP with access token
    GW-->>API: company/partner JSON
    API-->>Query: typed entities
    User->>Form: submit create/update
    Form->>API: POST/PATCH /companies or /partners
    API->>GW: HTTP with access token
    Query->>Query: invalidate company/partner query keys
```

Companies are the issuer profiles used by agents, invoices, and document uploads. Partners are selected under a company and reused by the invoice form. Query keys include the selected `company_id` so partner and invoice/document lists do not bleed between companies.

## Invoice Detail And PDF Download Flow

```mermaid
sequenceDiagram
    participant User
    participant Widget as Invoice Table Widget
    participant Query as TanStack Query
    participant API as shared/api/client
    participant GW as API Gateway
    participant PdfFeature as download-invoice-pdf feature

    User->>Widget: click invoice row
    Widget->>Query: useInvoice selected invoice id
    Query->>API: GET /invoices/id
    API->>GW: HTTP with access token
    GW-->>API: invoice detail JSON
    API-->>Query: typed invoice
    Query-->>Widget: cached invoice detail
    Widget-->>User: show detail dialog
    User->>PdfFeature: click Download PDF
    PdfFeature->>PdfFeature: render invoice PDF blob from supplier/recipient snapshots
    PdfFeature-->>User: browser downloads pdf file
```

The invoice table owns selected invoice UI state. Full invoice data still comes from `entities/invoice/api/useInvoice`, while the direct PDF download side effect is isolated in `features/download-invoice-pdf/` so entity UI remains reusable and feature side effects stay in the feature layer. PDFs render historical `supplier_snapshot` and `recipient_snapshot` values instead of fetching live company/partner records.

## Chat Streaming Flow

```mermaid
sequenceDiagram
    participant User
    participant Widget as Chat Widget
    participant Feature as send-message feature
    participant API as SSE helper
    participant GW as API Gateway

    User->>Widget: send message
    Widget->>Feature: submit message
    Feature->>API: streamSSE /agents/{id}/chat
    API->>GW: POST with Accept: text/event-stream
    GW-->>API: SSE token stream
    loop each token
        API-->>Feature: token
        Feature-->>Widget: append token
        Widget-->>User: render partial response
    end
```

The stream is implemented with `fetch()` rather than `EventSource` because chat uses authenticated `POST /agents/{id}/chat`. The gateway keeps the upstream `httpx` stream open until the downstream browser stream completes.

Opening the chat widget now starts a fresh conversation by default. Previous conversations are listed in a scoped history menu, and persisted messages are loaded only after an explicit user selection.

## Conversation History Reopen Flow

```mermaid
sequenceDiagram
    participant User
    participant Widget as Chat Widget
    participant Query as TanStack Query
    participant API as shared/api/client
    participant GW as API Gateway

    User->>Widget: open chat for agent/company
    Widget->>Widget: reset local chat state (fresh conversation)
    Widget->>Query: useConversations(agent_id, company_id, limit=20)
    Query->>API: GET /conversations?agent_id=...&company_id=...&limit=20&offset=0
    API->>GW: HTTP with access token
    GW-->>API: conversation summaries (newest first)
    API-->>Query: typed conversation list
    Query-->>Widget: render history menu entries
    User->>Widget: select a previous conversation
    Widget->>API: GET /conversations/{conversation_id}
    API->>GW: HTTP with access token
    GW-->>API: full conversation with messages
    API-->>Widget: load selected history into chat state
```

## Form Mutation Flow

```mermaid
sequenceDiagram
    participant User
    participant Form as Feature Form
    participant Zod
    participant Query as TanStack Query
    participant API as shared/api/client
    participant GW as API Gateway

    User->>Form: submit form
    Form->>Zod: validate input
    Zod-->>Form: parsed data
    Form->>Query: mutation
    Query->>API: POST/PUT request
    API->>GW: HTTP request
    GW-->>API: response
    Query->>Query: invalidate related query keys
    Query-->>Form: success/error state
```

## Document Upload Flow

```mermaid
sequenceDiagram
    participant User
    participant Upload as upload-document feature
    participant API as shared/api/client
    participant GW as API Gateway
    participant KB as Knowledge Service
    participant OpenAI

    User->>Upload: choose company and PDF/text/Markdown file
    Upload->>Upload: validate supported MIME type
    Upload->>API: POST /documents multipart/form-data with company_id
    API->>GW: HTTP with access token
    GW->>KB: proxy with x-user-id
    KB->>OpenAI: create embeddings
    KB-->>GW: document metadata
    GW-->>API: JSON response
    API-->>Upload: invalidate document list
```

Uploads require a selected company and a valid `OPENAI_API_KEY` because ingestion validates `company_id`, embeds chunks, and stores uploaded chunk metadata before the document reaches `ready` status. Without a key, the upload request reaches the Knowledge Service but fails during embedding.

## State Ownership

| State | Owner |
|-------|-------|
| Backend records | TanStack Query |
| Forms | React Hook Form + Zod |
| Selected company in forms/lists | Component state plus company-scoped query keys |
| Chat streaming buffer | Chat widget reducer |
| Session | NextAuth |
| UI preferences/filter state | Zustand stores |
