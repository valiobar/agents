# Knowledge Base Service

## Current State

Phase 2 implements the Knowledge Base Service beyond the original health-check stub. The service now supports authenticated, company-scoped document lifecycle operations, MongoDB metadata persistence, OpenAI embeddings, ChromaDB vector storage, tax document preloading, and retrieval for RAG workflows.

| Route | Status | Purpose |
|-------|--------|---------|
| `GET /health` | Implemented | Service health check |
| `POST /documents` | Implemented | Upload and ingest a PDF, text, or Markdown document for a company |
| `GET /documents?company_id=...` | Implemented | List non-deleted documents for one authenticated user's company |
| `PUT /documents/{id}` | Implemented | Re-ingest a changed document or return existing metadata for unchanged content |
| `DELETE /documents/{id}` | Implemented | Mark metadata deleted and remove document chunks from ChromaDB |
| `POST /retrieve` | Implemented | Search shared tax and company-scoped user document chunks |

External clients call these endpoints through the API Gateway at `http://localhost:8000`. The gateway validates JWTs and injects `x-user-id` for user-scoped document operations.

`POST /documents`, `GET /documents`, and user-document retrieval require a `company_id`. The Knowledge Base Service validates company ownership through the Agent Service internal `GET /companies/{company_id}/exists` endpoint before storing metadata, writing uploaded chunks, or retrieving uploaded chunks. Cross-user company ids return `404`.

## Run Locally

```bash
cp .env.example .env
docker compose up --build mongodb chromadb auth gateway knowledge
```

Minimum required configuration:

| Env Var | Default | Description |
|---------|---------|-------------|
| `MONGODB_URL` | `mongodb://mongodb:27017` | MongoDB server URL used by Motor |
| `DB_NAME` | `agents` | MongoDB database name |
| `CHROMADB_HOST` | `chromadb` | ChromaDB hostname on the Docker network |
| `CHROMADB_PORT` | `8000` | ChromaDB internal service port, not the host-mapped port |
| `CHROMADB_SSL` | `false` | Enables SSL for ChromaDB HTTP client in custom deployments |
| `OPENAI_API_KEY` | empty | Required when embeddings are generated |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model |
| `EMBEDDING_BATCH_SIZE` | `64` | Maximum texts per embedding request |
| `CHUNK_SIZE` | `800` | Text splitter chunk size |
| `CHUNK_OVERLAP` | `200` | Text splitter overlap |
| `MAX_UPLOAD_SIZE_BYTES` | `10485760` | Upload size limit |
| `TAX_DOCS_PATH` | `data/knowledgebase/tax` | Directory scanned when tax preload is enabled |
| `PRELOAD_TAX_DOCS` | `false` | Enables startup preload into `global_tax` |
| `AGENT_SERVICE_URL` | `http://agent:8002` | Internal Agent Service URL used for company ownership validation |

## Internal Architecture

```text
routes/
  documents.py          # POST/GET/PUT/DELETE /documents
  retrieval.py          # POST /retrieve
  health.py             # GET /health
services/
  document_service.py   # User-facing document lifecycle orchestration
  ingestion_service.py  # Validation, hashing, loading, chunking, embedding, vector writes
  retrieval_service.py  # Query embedding, vector searches, result merge/limit
  tax_preload_service.py
repositories/
  document_repo.py      # MongoDB documents collection
models/
  document.py           # Document lifecycle and chunk metadata models
  retrieval.py          # Retrieval request/response models
adapters/
  vector_store.py       # VectorStore interface
  chroma.py             # ChromaDB HTTP adapter
embeddings/
  provider.py           # OpenAI embedding wrapper
```

Routes stay thin and use FastAPI dependencies from `app/dependencies.py`. Services own business rules. Repositories persist metadata only. ChromaDB is accessed through the vector store adapter, and blocking ChromaDB/PDF/file operations are wrapped with `asyncio.to_thread`.

## Data Ownership

| Store | Owner | Purpose |
|-------|-------|---------|
| MongoDB `documents` | Knowledge Base Service | Metadata, `user_id + company_id` ownership, content hash, status, chunk count |
| ChromaDB `global_tax` | Knowledge Base Service | Shared tax regulation chunks loaded from `TAX_DOCS_PATH` |
| ChromaDB `user_{user_id}` | Knowledge Base Service | Chunks from user-uploaded documents with `company_id` metadata |

Raw uploaded documents are not persisted. MongoDB stores metadata and ChromaDB stores searchable chunk text, embeddings, and chunk metadata.

## Ingestion Behavior

`IngestionService` validates the company through Agent Service, checks upload size and content type, computes a SHA-256 content hash, and returns an existing ready document when identical content was already ingested for the same `user_id + company_id`. New or changed documents are loaded by `load_document`, chunked by `chunk_pages`, embedded by `EmbeddingProvider`, and written to ChromaDB through `ChromaAdapter.add_chunks`.

When an update changes content, stale chunks are removed from `user_{user_id}` before new chunks are inserted with the original document `company_id`. Empty documents fail with `400`, unsupported types fail with `415`, and oversized uploads fail with `413`.

## Retrieval Behavior

`RetrievalService` embeds the query once, searches `global_tax` when `include_global_tax` is true, searches `user_{user_id}` with `where={"company_id": request.company_id}` when `include_user_documents` is true, merges results, sorts by `score` descending, and returns at most `top_k` chunks. User-document retrieval requires both a user id and `company_id`; global tax retrieval can still run without company scope.

## Common Failures

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `401 Missing x-user-id header` | Calling the internal service directly without the gateway | Use the gateway with a bearer token or provide `x-user-id` in internal tests |
| `415 Unsupported document type` | Upload content type is not PDF, text, or Markdown | Send `application/pdf`, `text/plain`, or `text/markdown` |
| `413 Uploaded file exceeds maximum allowed size` | File is larger than `MAX_UPLOAD_SIZE_BYTES` | Reduce file size or adjust the env var |
| `404 Company not found` | `company_id` does not belong to the authenticated user or Agent Service is rejecting it | Create/select an owned company and retry |
| `422 company_id is required for user document retrieval` | `/retrieve` requested user documents without company scope | Include `company_id` or set `include_user_documents=false` |
| Chroma connection refused | Container is using the host-mapped Chroma port | Use `CHROMADB_PORT=8000` inside Docker |
| OpenAI authentication error | Missing or invalid `OPENAI_API_KEY` | Set a valid key in `.env` before embedding documents |
