# API Reference

All client traffic goes through the API Gateway at `http://localhost:8000`.
Authenticated endpoints require:

```http
Authorization: Bearer <access_token>
```

The gateway validates the JWT and injects `x-user-id` before proxying to internal services. Clients should not send `x-user-id` directly.

## Business Service

The Business Service owns companies, partners, invoice and expense records, financial summaries, inventory records, and the business rules for those records. Public URLs stay unchanged through the API Gateway: `/companies`, `/partners`, `/invoices`, `/expenses`, and `/inventory/*` route to Business.

### Company And Partner Workflow

Create a company first, then create partners under that company. Agents, invoices, and document uploads can then use the same `company_id`.

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
```

Partner reads/updates/deletes include `company_id` as a query parameter. Cross-user or cross-company ids return `404`.

## Agent Service

The Agent Service owns user-created agents, Accountant, Inventory, and Router chat runtimes, conversation history, provider selection, and tool orchestration. Business-domain tools call the Business Service over internal HTTP, so chat-created invoices, expenses, partners, inventory items, and stock movements use the same validation rules as the public Business APIs.

### Create Agent

```http
POST /agents
Content-Type: application/json
```

Creates an agent for the authenticated user.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | User-visible agent name, 1-120 characters. |
| `description` | string or null | No | `null` | Optional description, max 1000 characters. |
| `agent_type` | string | No | `accountant` | `accountant`, `inventory`, or `router`. |
| `company_id` | string or null | No | `null` | Optional owned company assignment. Required for partner/financial write tools. |
| `config.provider` | string | No | `openai` or `DEFAULT_AGENT_PROVIDER` | `openai`, `anthropic`, `deepseek`, or `ollama`. |
| `config.model` | string or null | No | Provider default | Model override for the selected provider. |
| `config.temperature` | number | No | `0.2` | LLM temperature from 0.0 to 2.0. |
| `config.system_prompt_override` | string or null | No | `null` | Optional custom system prompt, max 4000 characters. |

```bash
curl -X POST http://localhost:8000/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"My Accountant","agent_type":"accountant","company_id":"'"$COMPANY_ID"'","config":{"provider":"openai","temperature":0.2}}'
```

Response `201 Created`:

```json
{
  "id": "665f1f77c9e0f7a8093bb711",
  "name": "My Accountant",
  "description": null,
  "agent_type": "accountant",
  "company_id": "665f1f77c9e0f7a8093bb701",
  "config": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "temperature": 0.2,
    "system_prompt_override": null
  },
  "created_at": "2026-04-26T10:00:00Z",
  "updated_at": "2026-04-26T10:00:00Z"
}
```

### List Agents

```http
GET /agents?company_id={company_id}&limit=50&offset=0
```

Lists the authenticated user's agents, newest first. Optional `company_id` filters to one owned company. `limit` is 1-100 and `offset` is 0 or greater.

```bash
curl "http://localhost:8000/agents?company_id=$COMPANY_ID&limit=20&offset=0" \
  -H "Authorization: Bearer $TOKEN"
```

Response `200 OK`:

```json
[
  {
    "id": "665f1f77c9e0f7a8093bb711",
    "name": "My Accountant",
    "description": null,
    "agent_type": "accountant",
    "company_id": "665f1f77c9e0f7a8093bb701",
    "config": {
      "provider": "openai",
      "model": "gpt-4o-mini",
      "temperature": 0.2,
      "system_prompt_override": null
    },
    "created_at": "2026-04-26T10:00:00Z",
    "updated_at": "2026-04-26T10:00:00Z"
  }
]
```

### Get Agent

```http
GET /agents/{agent_id}
```

Returns one agent owned by the authenticated user.

```bash
curl "http://localhost:8000/agents/$AGENT_ID" \
  -H "Authorization: Bearer $TOKEN"
```

Response `200 OK` uses the same `AgentResponse` shape as create. Missing, invalid, or cross-user IDs return `404`.

### Update Agent

```http
PATCH /agents/{agent_id}
Content-Type: application/json
```

Updates agent name, description, company assignment, and/or full config. Omitted fields are left unchanged. Explicit JSON `null` clears nullable fields such as `description`, `company_id`, and `config.system_prompt_override`. When `config` is sent, it replaces the full agent config object rather than merging nested fields.

```bash
curl -X PATCH "http://localhost:8000/agents/$AGENT_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"VAT Advisor","config":{"provider":"anthropic","temperature":0.1}}'
```

Example clearing nullable fields:

```bash
curl -X PATCH "http://localhost:8000/agents/$AGENT_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"description":null,"company_id":null,"config":{"provider":"openai","model":"gpt-4o-mini","temperature":0.2,"system_prompt_override":null}}'
```

Response `200 OK` uses the same `AgentResponse` shape as create.

### Delete Agent

```http
DELETE /agents/{agent_id}
```

Deletes an agent owned by the authenticated user.

```bash
curl -X DELETE "http://localhost:8000/agents/$AGENT_ID" \
  -H "Authorization: Bearer $TOKEN"
```

Response `204 No Content`.

### Stream Chat

```http
POST /agents/{agent_id}/chat
Accept: text/event-stream
Content-Type: application/json
```

Streams an agent response. If `conversation_id` is omitted, the service creates a new conversation for the agent's current `company_id` and emits a `conversation` event before `start`. Provider and runtime setup happen before new conversation creation, so setup failures return an SSE `error` without inserting an empty conversation.

Accountant and inventory runtimes use LangChain `AgentExecutor` to execute model-requested tools before final response streaming. `rag_search` calls Knowledge; financial, partner, and inventory tools call Business over internal HTTP; `calculator` runs locally. Router runtimes classify the turn and delegate to a compatible accountant/inventory runtime or a no-tool general fallback. `done` is emitted only after the user and assistant messages are persisted.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | Yes | User message, 1-8000 characters. |
| `conversation_id` | string or null | No | Existing conversation to append to. Must belong to the same user, agent, and current agent company scope. |

```bash
curl -N -X POST "http://localhost:8000/agents/$AGENT_ID/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"message":"Calculate 20% VAT on 100 and explain it."}'
```

SSE events:

```text
event: conversation
data: {"conversation_id":"665f1f77c9e0f7a8093bb722"}

event: start
data: {"conversation_id":"665f1f77c9e0f7a8093bb722"}

event: token
data: {"content":"20% VAT on 100 is 20."}

event: route
data: {"predicted_route":"accountant","executed_route":"accountant","reason":"VAT question","confidence":0.94,"company_id":"665f1f77c9e0f7a8093bb701","company_scope":"assigned"}

event: done
data: {"conversation_id":"665f1f77c9e0f7a8093bb722"}
```

`route` is optional and router-only. It is emitted after persistence and before `done`; older clients can ignore it and continue relying on `token`, `error`, and `done`.

Error events use:

```text
event: error
data: {"message":"OPENAI_API_KEY is required for OpenAI agents"}
```

### Document Intake Workflow

```http
POST /agents/{agent_id}/document-intake
Content-Type: multipart/form-data
```

Uploads a document for Agent-orchestrated classification + review routing. Form fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | PDF/image upload to classify and extract. |
| `requested_type` | string | No | `auto` (default), `invoice`, or `receipt`. |

```bash
curl -X POST "http://localhost:8000/agents/$AGENT_ID/document-intake" \
  -H "Authorization: Bearer $TOKEN" \
  -F "requested_type=auto" \
  -F "file=@./supplier-invoice.pdf;type=application/pdf"
```

Response `201 Created` returns one of four `type` variants:

- `receipt_expense_review`
- `supplier_invoice_inventory_review`
- `supplier_invoice_expense_review`
- `unknown_document_review`

Shared review fields (when type is not `unknown_document_review`):

| Field | Type | Description |
|-------|------|-------------|
| `classification` | object | Includes `document_type`, `confidence`, and `warnings`. |
| `document` | object | Knowledge document metadata (`id`, `company_id`, `filename`, ...). |
| `draft` | object | Extracted expense draft used by final confirmation. |
| `extracted_text` | string or null | Optional extracted text. |
| `provider` | string | LLM provider used for extraction. |
| `model` | string | LLM model used for extraction. |
| `extracted_at` | ISO datetime string | Extraction timestamp. |

Supplier invoice with line items (`supplier_invoice_inventory_review`) includes:

| Field | Type | Description |
|-------|------|-------------|
| `inventory_import_preview` | object | Business preview (`id`, `status`, `lines`, `company_id`, ...). |

Unknown classification (`unknown_document_review`) includes:

| Field | Type | Description |
|-------|------|-------------|
| `classification` | object | Classified type/confidence/warnings. |
| `document` | object or null | Document metadata when available. |
| `extracted_text` | string or null | Raw extracted text (optional). |
| `warnings` | string[] | Workflow warnings. |

Example `supplier_invoice_inventory_review` response:

```json
{
  "type": "supplier_invoice_inventory_review",
  "classification": {
    "document_type": "supplier_invoice",
    "confidence": 0.93,
    "warnings": []
  },
  "document": {
    "id": "666000000000000000000111",
    "company_id": "666000000000000000000001",
    "filename": "supplier-invoice.pdf",
    "content_type": "application/pdf",
    "size_bytes": 523441,
    "status": "ready",
    "chunk_count": 0,
    "created_at": "2026-05-09T18:00:00Z",
    "updated_at": "2026-05-09T18:00:04Z"
  },
  "draft": {
    "counterparty": "Tech Supplier Ltd",
    "expense_date": "2026-05-09",
    "amount": "1200.00",
    "currency": "EUR",
    "category": "other",
    "description": null,
    "deductible": true,
    "deductible_rate": "1.0",
    "source_document_type": "invoice",
    "source_document_id": "666000000000000000000111",
    "source_document_number": "INV-9921",
    "vendor_partner": {
      "name": "Tech Supplier Ltd",
      "registration_number": "BG123456789",
      "vat_number": "BG123456789",
      "city": "Sofia",
      "country": "Bulgaria",
      "address": "5 Industrial Blvd",
      "accountable_person": "Elena Petrova",
      "email": "office@techsupplier.bg",
      "phone": null,
      "confidence": 0.91,
      "warnings": []
    },
    "items": [
      {
        "description": "Laptop stand",
        "quantity": "10",
        "unit_price": "50.00",
        "unit_label": "pcs",
        "sku": "LST-10",
        "barcode": null,
        "vat_rate": "0.20",
        "category": "office"
      }
    ],
    "confidence": 0.93,
    "warnings": []
  },
  "extracted_text": null,
  "provider": "openai",
  "model": "gpt-4.1-mini",
  "extracted_at": "2026-05-09T18:00:04Z",
  "inventory_import_preview": {
    "id": "666000000000000000000222",
    "user_id": "666000000000000000000900",
    "company_id": "666000000000000000000001",
    "document_id": "666000000000000000000111",
    "source_type": "supplier_invoice_upload",
    "status": "draft",
    "lines": [
      {
        "candidate": {
          "description": "Laptop stand",
          "sku": "LST-10",
          "barcode": null,
          "quantity": "10",
          "unit": "pcs",
          "unit_price": "50.00"
        },
        "matched_item_id": null,
        "proposed_item": {
          "company_id": "666000000000000000000001",
          "sku": "LST-10",
          "name": "Laptop stand",
          "description": null,
          "category": null,
          "barcode": null,
          "aliases": [],
          "unit": "pcs",
          "selling_price": null,
          "reorder_point": null,
          "target_stock_level": null,
          "supplier_partner_id": null,
          "is_active": true
        },
        "location_id": "666000000000000000000333",
        "receipt_quantity": "10",
        "warnings": []
      }
    ],
    "created_at": "2026-05-09T18:00:04Z",
    "updated_at": "2026-05-09T18:00:04Z"
  }
}
```

Supplier invoices with line items require two explicit approvals:

1. Confirm inventory preview.
2. Confirm final expense creation.

Inventory continuation endpoint:

```http
POST /agents/{agent_id}/document-intake/supplier-invoice/inventory-imports/confirm
Content-Type: application/json
```

```bash
curl -X POST "http://localhost:8000/agents/$AGENT_ID/document-intake/supplier-invoice/inventory-imports/confirm" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "preview_id": "'"$PREVIEW_ID"'",
    "draft": {
      "counterparty": "Tech Supplier Ltd",
      "expense_date": "2026-05-09",
      "amount": "1200.00",
      "currency": "EUR",
      "category": "other",
      "description": null,
      "deductible": true,
      "deductible_rate": "1.0",
      "source_document_type": "invoice",
      "source_document_id": "'"$DOCUMENT_ID"'",
      "source_document_number": "INV-9921",
      "vendor_partner": {
        "name": "Tech Supplier Ltd",
        "registration_number": "BG123456789",
        "vat_number": "BG123456789",
        "city": "Sofia",
        "country": "Bulgaria",
        "address": "5 Industrial Blvd",
        "accountable_person": "Elena Petrova",
        "email": "office@techsupplier.bg",
        "phone": null,
        "confidence": 0.91,
        "warnings": []
      },
      "items": [],
      "confidence": 0.93,
      "warnings": []
    }
  }'
```

Response `201 Created` (`ConfirmInventoryImportForExpenseResponse`):

```json
{
  "type": "supplier_invoice_expense_review",
  "inventory_import_result": {
    "preview_id": "666000000000000000000222",
    "items_created": 1,
    "items_updated": 0,
    "movements_created": 1
  },
  "inventory_import_preview": {
    "id": "666000000000000000000222",
    "status": "confirmed",
    "company_id": "666000000000000000000001",
    "source_type": "supplier_invoice_upload",
    "document_id": "666000000000000000000111",
    "lines": [],
    "created_at": "2026-05-09T18:00:04Z",
    "updated_at": "2026-05-09T18:01:10Z",
    "user_id": "666000000000000000000900"
  },
  "draft": {
    "counterparty": "Tech Supplier Ltd",
    "expense_date": "2026-05-09",
    "amount": "1200.00",
    "currency": "EUR",
    "category": "other",
    "description": null,
    "deductible": true,
    "deductible_rate": "1.0",
    "source_document_type": "invoice",
    "source_document_id": "666000000000000000000111",
    "source_document_number": "INV-9921",
    "vendor_partner": {
      "name": "Tech Supplier Ltd",
      "registration_number": "BG123456789",
      "vat_number": "BG123456789",
      "city": "Sofia",
      "country": "Bulgaria",
      "address": "5 Industrial Blvd",
      "accountable_person": "Elena Petrova",
      "email": "office@techsupplier.bg",
      "phone": null,
      "confidence": 0.91,
      "warnings": []
    },
    "items": [],
    "confidence": 0.93,
    "warnings": []
  }
}
```

`POST /agents/{agent_id}/expenses/confirm` is still the final write step for expense persistence.

### List Conversations

```http
GET /conversations?agent_id={agent_id}&company_id={company_id}&limit=20&offset=0
```

Lists conversations for one authenticated user's agent and company scope, newest first. Omit `company_id` to list conversations created while the agent was unassigned. The frontend uses this endpoint to populate the chat history menu and then loads full message history with `GET /conversations/{conversation_id}` for an explicit user selection.

```bash
curl "http://localhost:8000/conversations?agent_id=$AGENT_ID&company_id=$COMPANY_ID&limit=20&offset=0" \
  -H "Authorization: Bearer $TOKEN"
```

Response `200 OK` is an array of `ConversationResponse` objects.

### Get Conversation

```http
GET /conversations/{conversation_id}
```

Loads persisted conversation history for the authenticated user.

```bash
curl "http://localhost:8000/conversations/$CONVERSATION_ID" \
  -H "Authorization: Bearer $TOKEN"
```

Response `200 OK`:

```json
{
  "id": "665f1f77c9e0f7a8093bb722",
  "agent_id": "665f1f77c9e0f7a8093bb711",
  "company_id": "665f1f77c9e0f7a8093bb701",
  "title": "Calculate 20% VAT on 100 and explain it.",
  "messages": [
    {
      "role": "user",
      "content": "Calculate 20% VAT on 100 and explain it.",
      "created_at": "2026-04-26T10:01:00Z",
      "metadata": {}
    },
    {
      "role": "assistant",
      "content": "20% VAT on 100 is 20.",
      "created_at": "2026-04-26T10:01:04Z",
      "metadata": {}
    }
  ],
  "created_at": "2026-04-26T10:01:00Z",
  "updated_at": "2026-04-26T10:01:04Z"
}
```

### Agent Service Errors

| Status or event | Typical Cause |
|-----------------|---------------|
| `401` | Missing or invalid bearer token at the gateway, or missing `x-user-id` on direct internal calls. |
| `404` | Agent or conversation does not exist, has an invalid ObjectId, or belongs to another user/company scope. |
| `422` | Invalid request body, provider name, agent type, message length, config value, or pagination value. |
| SSE `error` | Provider API key is missing, provider runtime failed, Business or Knowledge tool execution failed, conversation does not match the agent, model execution failed, or message persistence failed. |

## Business Service: Invoices And Expenses

Invoice and expense endpoints are public Gateway routes backed by the Business Service. Agent financial tools call the same Business operations internally through `BusinessClient`.

### Create Invoice

```http
POST /invoices
Content-Type: application/json
```

Creates an invoice for the authenticated user and company. Money values may be sent as JSON strings and are returned as strings. The service validates company/partner ownership, snapshots supplier and recipient parties, calculates line totals, VAT, invoice totals, and the generated `invoice_number`.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `company_id` | string | Yes | - | Owning company id. |
| `partner_id` | string or null | No | `null` | Partner id under the same company. Required unless full recipient details are supplied. |
| `recipient` | object or null | No | `null` | Inline recipient details when no `partner_id` is used. |
| `issue_date` | date string | Yes | - | Invoice issue date, `YYYY-MM-DD`. |
| `tax_event_date` | date string | Yes | - | Tax event date, `YYYY-MM-DD`. |
| `due_date` | date string or null | No | `null` | Optional due date. Must not be before `issue_date`. |
| `place_of_supply` | string | No | `Bulgaria` | Place of supply for Bulgarian invoice layout. |
| `payment_method` | string | No | `bank_transfer` | `bank_transfer`, `cash`, `card`, or `other`. |
| `bank_name`, `bank_bic`, `bank_iban` | string or null | No | `null` | Optional bank details. |
| `currency` | string | No | `EUR` | `BGN`, `EUR`, or `USD`. |
| `items` | array | Yes | - | At least one invoice line. |
| `items[].description` | string | Yes | - | Line description, 1-500 characters. |
| `items[].quantity` | decimal string | Yes | - | Quantity, greater than `0`. |
| `items[].unit_label` | string | No | `бр.` | Unit label rendered in the PDF. |
| `items[].unit_price` | decimal string | Yes | - | Unit price, greater than or equal to `0`. |
| `items[].vat_rate` | decimal string | No | `0.20` | VAT rate from `0` to `1`. |
| `items[].category` | string or null | No | `null` | Optional reporting category. |
| `status` | string | No | `draft` | `draft`, `sent`, `paid`, `overdue`, or `cancelled`. |
| `vat_reason`, `recipient_name`, `compiler_name`, `original_label` | string or null | No | varies | Optional Bulgarian invoice layout fields. |
| `notes` | string or null | No | `null` | Optional notes, max 2000 characters. |

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

Response `201 Created`:

```json
{
  "id": "665f1f77c9e0f7a8093bb733",
  "user_id": "665f1f77c9e0f7a8093bb700",
  "company_id": "665f1f77c9e0f7a8093bb701",
  "partner_id": "665f1f77c9e0f7a8093bb702",
  "invoice_number": "INV-2026-00001",
  "counterparty": "Client Ltd",
  "supplier_snapshot": {
    "name": "Acme Ltd",
    "registration_number": "123456789",
    "vat_number": null,
    "city": "Sofia",
    "country": "Bulgaria",
    "address": "1 Business St",
    "accountable_person": "Ivan Ivanov",
    "email": null,
    "phone": null,
    "logo_data_url": null
  },
  "recipient_snapshot": {
    "name": "Client Ltd",
    "registration_number": "987654321",
    "vat_number": null,
    "city": "Plovdiv",
    "country": "Bulgaria",
    "address": "2 Client St",
    "accountable_person": "Petar Petrov",
    "email": null,
    "phone": null,
    "logo_data_url": null
  },
  "issue_date": "2026-04-26",
  "tax_event_date": "2026-04-26",
  "due_date": "2026-05-10",
  "place_of_supply": "Bulgaria",
  "payment_method": "bank_transfer",
  "bank_name": null,
  "bank_bic": null,
  "bank_iban": null,
  "amount_in_words": "сто и двадесет лева",
  "currency": "EUR",
  "items": [
    {
      "description": "Accounting consultation",
      "quantity": "1",
      "unit_label": "бр.",
      "unit_price": "100.00",
      "vat_rate": "0.20",
      "category": "services",
      "subtotal": "100.00",
      "vat_amount": "20.00",
      "total": "120.00"
    }
  ],
  "subtotal": "100.00",
  "vat_total": "20.00",
  "total": "120.00",
  "status": "draft",
  "vat_reason": null,
  "recipient_name": null,
  "compiler_name": null,
  "original_label": "ОРИГИНАЛ",
  "notes": null,
  "created_at": "2026-04-26T10:00:00Z",
  "updated_at": "2026-04-26T10:00:00Z"
}
```

### List Invoices

```http
GET /invoices?company_id=...&partner_id=...&status=draft&date_from=2026-04-01&date_to=2026-04-30&limit=50&offset=0
```

Lists invoices for the authenticated user, newest issue date first.

Supported query parameters: `company_id`, `partner_id`, `status`, `date_from`, `date_to`, `counterparty`, `amount_min`, `amount_max`, `category`, `limit` from 1 to 100, and `offset` from 0.

Response `200 OK` is an array of `InvoiceResponse` objects.

### Get Invoice

```http
GET /invoices/{invoice_id}
```

Returns one invoice owned by the authenticated user. Missing, invalid, or cross-user IDs return `404`.

### Update Invoice

```http
PATCH /invoices/{invoice_id}
Content-Type: application/json
```

Updates invoice status, due date, and/or notes. Invalid status transitions return `400`.

Allowed status transitions:

| From | To |
|------|----|
| `draft` | `sent`, `cancelled` |
| `sent` | `paid`, `overdue`, `cancelled` |
| `overdue` | `paid`, `cancelled` |
| `paid` | none |
| `cancelled` | none |

```bash
curl -X PATCH "http://localhost:8000/invoices/$INVOICE_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"sent","notes":"Sent to customer by email."}'
```

Response `200 OK` uses the same `InvoiceResponse` shape as create.

### Create Expense

```http
POST /expenses
Content-Type: application/json
```

Records an expense for the authenticated user. Send either `amount` or `items`. If `items` are provided, the service calculates `amount` from item totals.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `counterparty` | string | Yes | - | Vendor or payee name, 1-200 characters. |
| `expense_date` | date string | Yes | - | Expense date, `YYYY-MM-DD`. |
| `amount` | decimal string or null | Conditional | `null` | Required when `items` is omitted. |
| `currency` | string | No | `EUR` | `BGN`, `EUR`, or `USD`. |
| `category` | string | Yes | - | `office`, `travel`, `meals`, `software`, `rent`, `utilities`, `professional_services`, `tax`, `payroll`, or `other`. |
| `description` | string or null | No | `null` | Optional description, max 1000 characters. |
| `deductible` | boolean | No | `true` | Whether the expense is deductible. |
| `deductible_rate` | decimal string | No | `1.0` | Rate from `0` to `1`. |
| `source_document_type` | string or null | No | `null` | Optional `invoice` or `receipt`. |
| `source_document_id` | string or null | No | `null` | Optional linked source document id. |
| `items` | array or null | Conditional | `null` | Required when `amount` is omitted. |

```bash
curl -X POST http://localhost:8000/expenses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "counterparty": "Office Store",
    "expense_date": "2026-04-26",
    "amount": "24.00",
    "category": "office",
    "description": "Printer paper",
    "source_document_type": "receipt"
  }'
```

Response `201 Created`:

```json
{
  "counterparty": "Office Store",
  "expense_date": "2026-04-26",
  "amount": "24.00",
  "currency": "EUR",
  "category": "office",
  "description": "Printer paper",
  "deductible": true,
  "deductible_rate": "1.0000",
  "source_document_type": "receipt",
  "source_document_id": null,
  "items": null,
  "id": "665f1f77c9e0f7a8093bb744",
  "user_id": "665f1f77c9e0f7a8093bb700",
  "deductible_amount": "24.00",
  "created_at": "2026-04-26T10:05:00Z",
  "updated_at": "2026-04-26T10:05:00Z"
}
```

### List Expenses

```http
GET /expenses?category=office&date_from=2026-04-01&date_to=2026-04-30&limit=50&offset=0
```

Lists expenses for the authenticated user, newest expense date first.

Supported query parameters: `category`, `counterparty`, `date_from`, `date_to`, `deductible`, `amount_min`, `amount_max`, `limit` from 1 to 100, and `offset` from 0.

Response `200 OK` is an array of `ExpenseResponse` objects.

### Get Expense

```http
GET /expenses/{expense_id}
```

Returns one expense owned by the authenticated user. Missing, invalid, or cross-user IDs return `404`.

### Internal Financial Summary

```http
POST /financial-summary
Content-Type: application/json
```

Business exposes this endpoint for internal Agent tool calls at `http://business:8005/financial-summary`. It is not a public Gateway route. The request can filter by `company_id`, `partner_id`, date range, and optional grouping, then returns invoice, expense, and net totals for the authenticated `x-user-id`.

### Inventory Endpoints

Business exposes inventory as public gateway routes under `/inventory/*`. All inventory requests are authenticated and user-scoped; company-scoped routes require `company_id` and validate ownership.

| Endpoint | Purpose | Request highlights | Response |
|----------|---------|--------------------|----------|
| `POST /inventory/items` | Create inventory item | Body includes `company_id`, `sku`, `name`, `unit`; optional `barcode`, `aliases`, `reorder_point`, `target_stock_level`, `supplier_partner_id` | `201` `InventoryItemResponse` |
| `GET /inventory/items?company_id=...` | List items | Optional filters: `category`, `is_active`, `sku`, `barcode`, `limit`, `offset` | `200` `InventoryItemResponse[]` |
| `GET /inventory/items/{item_id}?company_id=...` | Get item | Query `company_id` required | `200` `InventoryItemResponse` |
| `PATCH /inventory/items/{item_id}?company_id=...` | Update item | Partial body fields from `InventoryItemUpdate` | `200` `InventoryItemResponse` |
| `POST /inventory/locations` | Create location | Body includes `company_id`, `name`, optional `description`, `is_default` | `201` `InventoryLocationResponse` |
| `GET /inventory/locations?company_id=...` | List locations | Optional `limit`, `offset` | `200` `InventoryLocationResponse[]` |
| `GET /inventory/locations/{location_id}?company_id=...` | Get location | Query `company_id` required | `200` `InventoryLocationResponse` |
| `PATCH /inventory/locations/{location_id}?company_id=...` | Update location | Partial body fields from `InventoryLocationUpdate` | `200` `InventoryLocationResponse` |
| `POST /inventory/movements` | Create stock movement | Body includes `company_id`, `item_id`, `location_id`, `movement_type`, `quantity_delta` | `201` `StockMovementResponse` |
| `GET /inventory/movements?company_id=...` | List stock movements | Optional filters: `item_id`, `location_id`, `movement_type`, `limit`, `offset` | `200` `StockMovementResponse[]` |
| `GET /inventory/levels?company_id=...` | Get derived stock levels | Optional filters: `item_id`, `location_id`, `below_reorder_point` | `200` `StockLevel[]` |
| `POST /inventory/search` | Search inventory | Body includes `company_id`, `query`; optional `include_stock`, `min_confidence`, `limit` | `200` `InventorySearchResponse` |
| `POST /inventory/import-previews` | Create import preview | Body includes `company_id`, source metadata, and supplier line candidates | `201` `InventoryImportPreviewResponse` |
| `GET /inventory/import-previews?company_id=...` | List previews | Optional filters: `preview_status`, `limit`, `offset` | `200` `InventoryImportPreviewResponse[]` |
| `GET /inventory/import-previews/{preview_id}` | Get preview | Path id only | `200` `InventoryImportPreviewResponse` |
| `PATCH /inventory/import-previews/{preview_id}` | Update preview lines | Body includes updated `lines` review payload | `200` `InventoryImportPreviewResponse` |
| `POST /inventory/import-previews/{preview_id}/confirm` | Confirm preview | No body required | `200` `InventoryImportResult` |
| `POST /inventory/import-previews/{preview_id}/cancel` | Cancel preview | No body required | `200` `InventoryImportPreviewResponse` |

Invoice create form uses `POST /inventory/search` for line-item linking with debounced input. Typical selector request:

```bash
curl -X POST http://localhost:8000/inventory/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "'"$COMPANY_ID"'",
    "query": "SKU-123",
    "include_stock": true,
    "min_confidence": 0.5,
    "limit": 20
  }'
```

Example response `200 OK` (`InventorySearchResponse`):

```json
{
  "query": "SKU-123",
  "matches": [
    {
      "item_id": "665f1f77c9e0f7a8093bb901",
      "sku": "SKU-123",
      "name": "Widget A",
      "confidence": "1.0000",
      "available_quantity": "42.0000"
    }
  ]
}
```

Example create preview request:

```bash
curl -X POST http://localhost:8000/inventory/import-previews \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "'"$COMPANY_ID"'",
    "source_type": "invoice",
    "source_id": "'"$INVOICE_ID"'",
    "lines": [
      {
        "candidate": {
          "description": "iPhone 15 Pro 128GB",
          "sku": "IPH15P-128",
          "barcode": null,
          "quantity": "5",
          "unit": "pcs",
          "unit_price": "999.00"
        },
        "location_id": "'"$LOCATION_ID"'"
      }
    ]
  }'
```

Response `201 Created`:

```json
{
  "id": "665f1f77c9e0f7a8093bb888",
  "user_id": "665f1f77c9e0f7a8093bb700",
  "company_id": "665f1f77c9e0f7a8093bb701",
  "document_id": null,
  "source_type": "invoice",
  "source_id": "665f1f77c9e0f7a8093bb733",
  "status": "draft",
  "lines": [
    {
      "candidate": {
        "description": "iPhone 15 Pro 128GB",
        "sku": "IPH15P-128",
        "barcode": null,
        "quantity": "5",
        "unit": "pcs",
        "unit_price": "999.00"
      },
      "matched_item_id": null,
      "proposed_item": {
        "sku": "IPH15P-128",
        "name": "iPhone 15 Pro 128GB",
        "unit": "pcs"
      },
      "location_id": "665f1f77c9e0f7a8093bb799",
      "receipt_quantity": "5",
      "warnings": ["No exact SKU match found; proposed item will be created on confirm."]
    }
  ],
  "created_at": "2026-04-26T11:10:00Z",
  "updated_at": "2026-04-26T11:10:00Z"
}
```

Example confirm and cancel requests:

```bash
curl -X POST "http://localhost:8000/inventory/import-previews/$PREVIEW_ID/confirm" \
  -H "Authorization: Bearer $TOKEN"

curl -X POST "http://localhost:8000/inventory/import-previews/$PREVIEW_ID/cancel" \
  -H "Authorization: Bearer $TOKEN"
```

Confirm response `200 OK` (`InventoryImportResult`):

```json
{
  "preview_id": "665f1f77c9e0f7a8093bb888",
  "items_created": 1,
  "items_updated": 0,
  "movements_created": 1
}
```

Cancel response `200 OK` returns the same `InventoryImportPreviewResponse` shape with `"status": "cancelled"`.

Invoice and inventory are connected inside Business: when an invoice transitions from `draft` to `sent`, linked line items can produce stock issue movements.

### Business Service Errors

| Status | Typical Cause |
|--------|---------------|
| `401` | Missing or invalid bearer token at the gateway, or missing `x-user-id` on direct internal calls. |
| `400` | Invalid invoice status transition. |
| `404` | Company, partner, invoice, or expense does not exist, has an invalid ObjectId, or belongs to another user/company. |
| `422` | Invalid request body, money/date value, category/status, company/partner relationship, or pagination value. |

## Knowledge Base Service

The Knowledge Base Service owns uploaded documents, MongoDB document metadata, ChromaDB vector chunks, and retrieval over shared tax knowledge plus company-scoped user documents.

### Upload Document

```http
POST /documents
Content-Type: multipart/form-data
```

Uploads and ingests a PDF, text, or Markdown document for one authenticated user's company.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | Document to ingest. Supported types: `application/pdf`, `text/plain`, `text/markdown`. |
| `company_id` | string | Yes | Owned company id. Knowledge Base validates ownership through Business Service before ingestion. |

```bash
curl -X POST http://localhost:8000/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "company_id=$COMPANY_ID" \
  -F "file=@./tax-notes.md;type=text/markdown"
```

Response `201 Created`:

```json
{
  "id": "665f1f77c9e0f7a8093bb711",
  "company_id": "665f1f77c9e0f7a8093bb701",
  "filename": "tax-notes.md",
  "content_type": "text/markdown",
  "size_bytes": 12345,
  "status": "ready",
  "chunk_count": 12,
  "created_at": "2026-04-26T10:00:00Z",
  "updated_at": "2026-04-26T10:00:02Z"
}
```

Identical ready content for the same `user_id + company_id` returns the existing document metadata instead of re-embedding duplicate chunks.

### List Documents

```http
GET /documents?company_id=...&limit=50&offset=0
```

Lists non-deleted documents for one authenticated user's company, newest first.

```bash
curl "http://localhost:8000/documents?company_id=$COMPANY_ID&limit=20&offset=0" \
  -H "Authorization: Bearer $TOKEN"
```

Response `200 OK`:

```json
[
  {
    "id": "665f1f77c9e0f7a8093bb711",
    "company_id": "665f1f77c9e0f7a8093bb701",
    "filename": "tax-notes.md",
    "content_type": "text/markdown",
    "size_bytes": 12345,
    "status": "ready",
    "chunk_count": 12,
    "created_at": "2026-04-26T10:00:00Z",
    "updated_at": "2026-04-26T10:00:02Z"
  }
]
```

### Update Document

```http
PUT /documents/{id}
Content-Type: multipart/form-data
```

Re-ingests a document owned by the authenticated user. The document keeps its original `company_id`. If the uploaded content hash matches the current document hash, the service returns the existing metadata and skips vector replacement. If content changed, old chunks are deleted from the user's ChromaDB collection and new company-tagged chunks are embedded.

```bash
curl -X PUT "http://localhost:8000/documents/665f1f77c9e0f7a8093bb711" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@./tax-notes-updated.md;type=text/markdown"
```

Response `200 OK` uses the same `DocumentResponse` shape as upload.

### Delete Document

```http
DELETE /documents/{id}
```

Deletes vector chunks from the user's ChromaDB collection and marks the MongoDB document metadata as `deleted`.

```bash
curl -X DELETE "http://localhost:8000/documents/665f1f77c9e0f7a8093bb711" \
  -H "Authorization: Bearer $TOKEN"
```

Response `204 No Content`.

### Retrieve Chunks

```http
POST /retrieve
Content-Type: application/json
```

Retrieves relevant chunks from `global_tax`, `global_inventory`, and when a user id and `company_id` are available, `user_{user_id}` filtered by company. The endpoint is designed for the Agent Service, but it is also available through the gateway for integration testing.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | Yes | - | Search query, 1-4000 characters. |
| `user_id` | string | No | `null` | Optional explicit user id. If omitted, the gateway-injected user id is used. |
| `company_id` | string | Required for user documents | `null` | Company filter for uploaded chunks. |
| `top_k` | integer | No | `5` | Number of chunks to return, from 1 to 20. |
| `include_global_tax` | boolean | No | `true` | Search shared tax documents. |
| `include_global_inventory` | boolean | No | `false` | Search shared inventory reference documents (movement types, import guides, best practices). |
| `include_user_documents` | boolean | No | `true` | Search the user's uploaded documents. |
| `allow_legacy_all_company_documents` | boolean | No | `false` | Explicit compatibility flag for legacy all-company retrieval. |
| `filters` | object | No | `{}` | ChromaDB metadata filters. Values may be string, number, or boolean. |

```bash
curl -X POST http://localhost:8000/retrieve \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"What do my notes say about VAT?","company_id":"'"$COMPANY_ID"'","top_k":5}'
```

Response `200 OK`:

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
        "filename": "tax-notes.md",
        "chunk_index": 0,
        "source": "upload",
        "page_number": null,
        "content_hash": "sha256..."
      }
    }
  ]
}
```

### Knowledge Base Errors

| Status | Typical Cause |
|--------|---------------|
| `400` | Empty document or invalid request body/query parameters. |
| `401` | Missing or invalid bearer token at the gateway, or missing `x-user-id` on user-scoped internal document routes. |
| `404` | Document does not exist, is deleted, or belongs to another user. |
| `413` | Uploaded file exceeds `MAX_UPLOAD_SIZE_BYTES`. |
| `415` | Unsupported document content type. |
| `500` | Upstream MongoDB, ChromaDB, OpenAI, or ingestion failure. |
