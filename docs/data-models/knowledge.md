# Knowledge Base Data Models

This page documents the models that currently exist in the Knowledge Base Service code.

## MongoDB `documents`

Owned by: Knowledge Base Service

Source:

- `services/knowledge/app/models/document.py`
- `services/knowledge/app/repositories/document_repo.py`

MongoDB stores document metadata only. Raw uploaded file bytes are not persisted.

`company_id` references the Business-owned `companies` collection. Knowledge owns document metadata and vector chunks, but it validates company ownership through Business before accepting company-scoped writes or retrieval.

```json
{
  "_id": "ObjectId",
  "user_id": "665f1f77c9e0f7a8093bb711",
  "company_id": "665f1f77c9e0f7a8093bb701",
  "filename": "tax-notes.pdf",
  "content_type": "application/pdf",
  "size_bytes": 12345,
  "content_hash": "sha256...",
  "status": "ready",
  "chunk_count": 12,
  "error_message": null,
  "metadata": {},
  "created_at": "2026-04-26T10:00:00Z",
  "updated_at": "2026-04-26T10:00:02Z"
}
```

### Status Values

| Value | Meaning |
|-------|---------|
| `processing` | Metadata exists while ingestion or re-ingestion is running |
| `ready` | Chunks were embedded and stored successfully |
| `failed` | Ingestion failed; `error_message` contains the failure detail |
| `deleted` | Metadata is retained but hidden from normal list/get flows |

### Indexes

Created by `services/knowledge/app/utils/db.py` during service startup:

| Index | Purpose |
|-------|---------|
| `user_id + created_at desc` | Fast user-scoped document lists sorted newest first |
| `user_id + company_id + created_at desc` | Fast company-scoped document lists sorted newest first |
| `user_id + company_id + content_hash` | Detect unchanged re-uploads within one company and avoid duplicate embeddings |
| `user_id + company_id + status` | Filter active and deleted documents within one company |

## Public Document Response

Returned by `POST /documents`, `GET /documents`, and `PUT /documents/{id}`.

```json
{
  "id": "665f1f77c9e0f7a8093bb711",
  "company_id": "665f1f77c9e0f7a8093bb701",
  "filename": "tax-notes.pdf",
  "content_type": "application/pdf",
  "size_bytes": 12345,
  "status": "ready",
  "chunk_count": 12,
  "created_at": "2026-04-26T10:00:00Z",
  "updated_at": "2026-04-26T10:00:02Z"
}
```

Public responses intentionally omit `user_id`, `content_hash`, `error_message`, and internal metadata. They include `company_id` so frontend query caches and lists can stay company-scoped.

## Expense Draft Extraction Contract

Source: `services/knowledge/app/routes/documents.py` and `services/knowledge/app/models/financial.py`

Knowledge exposes `POST /documents/expense-draft` for upload-time classify/extract workflows. Agent uses this endpoint as the current compatibility source for `POST /agents/{agent_id}/document-intake`.

The response shape contains:

- `document` (`DocumentResponse`)
- `draft` (`ExpenseDraft`)
- `extracted_text` (`string | null`)
- `provider` (`string`)
- `model` (`string`)
- `extracted_at` (`datetime`)

Ownership rule: this endpoint performs extraction only. It does not approve workflows, confirm inventory imports, or create Business expense/inventory records.

## ChromaDB Chunk Metadata

Owned by: Knowledge Base Service

Source:

- `services/knowledge/app/models/document.py`
- `services/knowledge/app/adapters/chroma.py`
- `services/knowledge/app/services/ingestion_service.py`
- `services/knowledge/app/services/tax_preload_service.py`

User uploads are stored in `user_{user_id}`. Shared tax documents are stored in `global_tax`.

```json
{
  "document_id": "665f1f77c9e0f7a8093bb711",
  "user_id": "665f1f77c9e0f7a8093bb711",
  "company_id": "665f1f77c9e0f7a8093bb701",
  "filename": "tax-notes.pdf",
  "chunk_index": 0,
  "source": "upload",
  "page_number": 1,
  "content_hash": "sha256..."
}
```

For global tax documents, `user_id` and `company_id` are omitted and `source` is `global_tax`.

Chunk ids use:

```text
{document_id}:{chunk_index}
```

Tax preload document ids use:

```text
tax:{relative_path}:{content_hash_prefix}
```

## Retrieval Models

Source: `services/knowledge/app/models/retrieval.py`

Request:

```json
{
  "query": "What do my notes say about VAT?",
  "user_id": null,
  "company_id": "665f1f77c9e0f7a8093bb701",
  "top_k": 5,
  "include_global_tax": true,
  "include_user_documents": true,
  "allow_legacy_all_company_documents": false,
  "filters": {}
}
```

Constraints:

| Field | Constraint |
|-------|------------|
| `query` | 1 to 4000 characters |
| `company_id` | Required when `include_user_documents=true`, unless explicitly using legacy all-company retrieval |
| `top_k` | 1 to 20 |
| `filters` | String, numeric, or boolean values |

Response:

```json
{
  "query": "What do my notes say about VAT?",
  "chunks": [
    {
      "text": "VAT registration rules...",
      "score": 0.12,
      "collection": "user_665f1f77c9e0f7a8093bb711",
      "metadata": {
        "document_id": "665f1f77c9e0f7a8093bb711",
        "user_id": "665f1f77c9e0f7a8093bb711",
        "company_id": "665f1f77c9e0f7a8093bb701",
        "filename": "tax-notes.pdf",
        "chunk_index": 0,
        "source": "upload",
        "page_number": 1,
        "content_hash": "sha256..."
      }
    }
  ]
}
```
