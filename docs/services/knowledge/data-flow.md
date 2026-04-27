# Knowledge Base Service Data Flow

## Document Upload Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant KB as Knowledge Base
    participant Agent as Agent Service
    participant Mongo
    participant OpenAI
    participant Chroma

    Client->>Gateway: POST /documents + bearer token + multipart file + company_id
    Gateway->>KB: Proxy request with x-user-id
    KB->>Agent: GET /companies/{company_id}/exists with x-user-id
    Agent-->>KB: ownership confirmed
    KB->>KB: Validate size and content type
    KB->>KB: Compute SHA-256 content hash
    KB->>Mongo: Find ready document by user_id + company_id + content_hash
    alt unchanged content exists
        Mongo-->>KB: Existing document metadata
        KB-->>Gateway: DocumentResponse
    else new content
        KB->>Mongo: Insert processing document metadata with company_id
        KB->>KB: Extract text and page numbers
        KB->>KB: Split text into chunks
        KB->>OpenAI: Embed chunks in batches
        OpenAI-->>KB: Embedding vectors
        KB->>Chroma: Upsert chunks into user_{user_id} with company_id metadata
        KB->>Mongo: Mark document ready with chunk_count
        KB-->>Gateway: DocumentResponse
    end
    Gateway-->>Client: Response
```

`IngestionService.ingest_upload` owns this flow. Company ownership is validated by an internal Agent Service client before metadata or vectors are written. If extraction produces no chunks, metadata is marked `failed` and the request returns `400`.

## Document Update Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant KB as Knowledge Base
    participant Agent as Agent Service
    participant Mongo
    participant OpenAI
    participant Chroma

    Client->>Gateway: PUT /documents/{id} + bearer token + multipart file
    Gateway->>KB: Proxy request with x-user-id
    KB->>Mongo: Load owned non-deleted document
    KB->>Agent: Validate existing document company_id
    KB->>KB: Compute new content hash
    alt hash unchanged
        KB-->>Gateway: Existing DocumentResponse
    else hash changed
        KB->>Chroma: Delete chunks by document_id from user_{user_id}
        KB->>Mongo: Reset metadata to processing
        KB->>KB: Extract and chunk document
        KB->>OpenAI: Embed chunks
        KB->>Chroma: Upsert replacement chunks with original company_id
        KB->>Mongo: Mark ready with new metadata
        KB-->>Gateway: Updated DocumentResponse
    end
    Gateway-->>Client: Response
```

## Retrieval Flow

```mermaid
sequenceDiagram
    participant ClientOrAgent
    participant Gateway
    participant KB as Knowledge Base
    participant Agent as Agent Service
    participant OpenAI
    participant Chroma

    ClientOrAgent->>Gateway: POST /retrieve + bearer token + query + company_id
    Gateway->>KB: Proxy request with x-user-id
    KB->>OpenAI: Embed query once
    OpenAI-->>KB: Query vector
    opt include_global_tax
        KB->>Chroma: Search global_tax
    end
    opt include_user_documents and user id + company_id available
        KB->>Agent: Validate company ownership
        KB->>Chroma: Search user_{user_id} where company_id matches
    end
    Chroma-->>KB: Matching chunks
    KB->>KB: Merge, sort by score descending, limit top_k
    KB-->>Gateway: RetrievalResponse
    Gateway-->>ClientOrAgent: RetrievalResponse
```

`RetrievalRequest.user_id` can override the gateway-injected user id. If neither is present, retrieval still works for `global_tax` when enabled. User-uploaded document retrieval requires `company_id` and filters uploaded-source chunks by that company. Requests that set `include_user_documents=true` without `company_id` return `422` unless the explicit legacy all-company flag is used.

## Delete Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant KB as Knowledge Base
    participant Mongo
    participant Chroma

    Client->>Gateway: DELETE /documents/{id} + bearer token
    Gateway->>KB: Proxy request with x-user-id
    KB->>Mongo: Verify owned non-deleted document
    KB->>Chroma: Delete chunks by document_id from user_{user_id}
    KB->>Mongo: Set status=deleted and updated_at
    KB-->>Gateway: 204 No Content
    Gateway-->>Client: 204 No Content
```

Deleted documents are hidden from list/get paths by repository filters.

## Startup Tax Preload Flow

```mermaid
sequenceDiagram
    participant KB as Knowledge Base
    participant FS as TAX_DOCS_PATH
    participant OpenAI
    participant Chroma

    KB->>KB: Lifespan startup
    opt PRELOAD_TAX_DOCS=true
        KB->>FS: Scan .pdf, .txt, .md files
        KB->>KB: Extract, hash, and chunk each file
        KB->>OpenAI: Embed chunks
        KB->>Chroma: Upsert into global_tax
    end
```

Missing or empty tax document directories do not fail startup.

## Write Paths

| Data | Write Path |
|------|------------|
| Document metadata | Gateway -> `routes/documents.py` -> `DocumentService` -> `IngestionService` or `DocumentRepository` -> MongoDB |
| User vectors | `IngestionService` -> Agent Service company validation -> `EmbeddingProvider` -> `ChromaAdapter` -> ChromaDB `user_{user_id}` with `company_id` metadata |
| Global tax vectors | `TaxPreloadService` -> `EmbeddingProvider` -> `ChromaAdapter` -> ChromaDB `global_tax` |
| Retrieval results | Read-only; no logs are persisted yet |
