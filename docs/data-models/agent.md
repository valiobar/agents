# Agent Service Data Models

The Agent Service owns the `companies`, `partners`, `agents`, `conversations`, `invoices`, `expenses`, and invoice `counters` MongoDB collections. Ownership is scoped by the gateway-authenticated `user_id` that arrives as `x-user-id`; partners and invoices also carry `company_id`.

## `companies` Collection

Stores invoice issuer profiles owned by one user.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | MongoDB primary key. Public API exposes this as `id`. |
| `user_id` | string | Yes | Gateway-authenticated owner id. Every query filters by this field. |
| `name` | string | Yes | Company legal/display name, 1-200 characters. |
| `registration_number` | string | Yes | Company registration number, unique per user. |
| `vat_number` | string or null | No | Optional VAT number. |
| `city` | string | Yes | Company city. |
| `country` | string | Yes | Defaults to `Bulgaria`. |
| `address` | string | Yes | Company address. |
| `accountable_person` | string | Yes | Person accountable for invoice documents. |
| `email` | string or null | No | Optional contact email. |
| `phone` | string or null | No | Optional contact phone. |
| `logo_data_url` | string or null | No | Optional PNG/JPEG/WebP/GIF data URL, max decoded size 256 KB. |
| `is_default` | boolean | Yes | At most one default company per user. |
| `created_at` | datetime | Yes | Creation timestamp. |
| `updated_at` | datetime | Yes | Last update timestamp. |

Indexes created on startup:

| Index | Purpose |
|-------|---------|
| `(user_id ASC, created_at DESC)` | List a user's companies newest first. |
| `(user_id ASC, registration_number ASC)` unique | Prevent duplicate company registration numbers per user. |
| `(user_id ASC, is_default ASC)` | Find or unset a user's default company. |

## `partners` Collection

Stores reusable clients, suppliers, or both under one company.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | MongoDB primary key. Public API exposes this as `id`. |
| `user_id` | string | Yes | Gateway-authenticated owner id. |
| `company_id` | string | Yes | Owning company id. Partner routes validate this alongside `user_id`. |
| `kind` | string | Yes | `client`, `supplier`, `both`, or `other`. |
| `name` | string | Yes | Partner legal/display name. |
| `registration_number` | string | Yes | Partner registration number, unique per user/company. |
| `vat_number` | string or null | No | Optional VAT number. |
| `city` | string | Yes | Partner city. |
| `country` | string | Yes | Defaults to `Bulgaria`. |
| `address` | string | Yes | Partner address. |
| `accountable_person` | string | Yes | Contact/accountable person. |
| `email` | string or null | No | Optional contact email. |
| `phone` | string or null | No | Optional contact phone. |
| `notes` | string or null | No | Optional internal notes. |
| `created_at` | datetime | Yes | Creation timestamp. |
| `updated_at` | datetime | Yes | Last update timestamp. |

Indexes created on startup:

| Index | Purpose |
|-------|---------|
| `(user_id ASC, company_id ASC, name ASC)` | Company-scoped partner lists and search. |
| `(user_id ASC, company_id ASC, kind ASC)` | Filter partners by kind. |
| `(user_id ASC, company_id ASC, registration_number ASC)` unique | Prevent duplicate partner registration numbers within a company. |

## `agents` Collection

Stores user-created agent instances and provider/runtime configuration.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | MongoDB primary key. Public API exposes this as `id`. |
| `user_id` | string | Yes | Gateway-authenticated owner id. Every query filters by this field. |
| `name` | string | Yes | User-visible agent name, 1-120 characters. |
| `description` | string or null | No | Optional user-visible description, max 1000 characters. |
| `agent_type` | string | Yes | Phase 3 supports only `accountant`. |
| `company_id` | string or null | No | Optional owned company assignment. Financial/partner tools require this for writes. |
| `config` | object | Yes | Provider, model, temperature, and optional system prompt override. |
| `config.provider` | string | Yes | `openai`, `anthropic`, `deepseek`, or `ollama`. |
| `config.model` | string or null | No | Provider model override. Service fills provider defaults on create when omitted. |
| `config.temperature` | number | Yes | LLM temperature, 0.0-2.0. Default is `0.2`. |
| `config.system_prompt_override` | string or null | No | Optional custom prompt, max 4000 characters. |
| `created_at` | datetime | Yes | Creation timestamp. |
| `updated_at` | datetime | Yes | Last update timestamp. |

Example document:

```json
{
  "_id": {"$oid": "665f1f77c9e0f7a8093bb711"},
  "user_id": "665f1f77c9e0f7a8093bb700",
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
  "created_at": {"$date": "2026-04-26T10:00:00Z"},
  "updated_at": {"$date": "2026-04-26T10:00:00Z"}
}
```

Indexes created on startup:

| Index | Purpose |
|-------|---------|
| `(user_id ASC, created_at DESC)` | List a user's agents newest first. |
| `(user_id ASC, company_id ASC, created_at DESC)` | Filter a user's agents by company. |
| `(user_id ASC, name ASC)` | Support user-scoped name filtering/sorting and future uniqueness checks. |

## `conversations` Collection

Stores persisted chat history for one user, one agent, and the agent's company scope at the time the conversation was created.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | MongoDB primary key. Public API exposes this as `id`. |
| `user_id` | string | Yes | Gateway-authenticated owner id. |
| `agent_id` | string | Yes | Public string id of the owning agent. |
| `company_id` | string or null | No | Agent company scope for this chat. The frontend loads history by `agent_id + company_id`; missing legacy values behave like `null`. |
| `title` | string or null | No | First message prefix when a conversation is created from chat. |
| `messages` | array | Yes | Ordered conversation messages. |
| `messages[].role` | string | Yes | `user`, `assistant`, `system`, or `tool`. Persisted Phase 3 chat writes `user` and `assistant`. |
| `messages[].content` | string | Yes | Message content. |
| `messages[].created_at` | datetime | Yes | Message creation timestamp. |
| `messages[].metadata` | object | Yes | Optional primitive metadata. Defaults to `{}`. |
| `created_at` | datetime | Yes | Conversation creation timestamp. |
| `updated_at` | datetime | Yes | Last message/update timestamp. |

Example document:

```json
{
  "_id": {"$oid": "665f1f77c9e0f7a8093bb722"},
  "user_id": "665f1f77c9e0f7a8093bb700",
  "agent_id": "665f1f77c9e0f7a8093bb711",
  "company_id": "665f1f77c9e0f7a8093bb701",
  "title": "Calculate 20% VAT on 100 and explain it.",
  "messages": [
    {
      "role": "user",
      "content": "Calculate 20% VAT on 100 and explain it.",
      "created_at": {"$date": "2026-04-26T10:01:00Z"},
      "metadata": {}
    },
    {
      "role": "assistant",
      "content": "20% VAT on 100 is 20.",
      "created_at": {"$date": "2026-04-26T10:01:04Z"},
      "metadata": {}
    }
  ],
  "created_at": {"$date": "2026-04-26T10:01:00Z"},
  "updated_at": {"$date": "2026-04-26T10:01:04Z"}
}
```

Indexes created on startup:

| Index | Purpose |
|-------|---------|
| `(user_id ASC, agent_id ASC, updated_at DESC)` | List recent conversations for a user's agent. |
| `(user_id ASC, agent_id ASC, company_id ASC, updated_at DESC)` | Load the latest conversation for one agent/company scope. |
| `(user_id ASC, created_at DESC)` | User-scoped conversation lookup/listing support. |

## Financial Money And Date Semantics

Invoice and expense models use Python `Decimal` for money and rates. Repositories convert `Decimal` values to BSON `Decimal128` before storing in MongoDB and convert them back for Pydantic models. API responses serialize money values as JSON strings, for example `"120.00"`, not floating point numbers.

The API accepts date-only values such as `"2026-04-26"` for `issue_date`, `due_date`, and `expense_date`. Repositories store them as UTC datetimes for indexed range queries and convert them back to date-only response values.

Supported currencies are `BGN`, `EUR`, and `USD`.

## `invoices` Collection

Stores company-scoped invoice records. Invoice totals are calculated server-side from line items, invoice numbers are generated atomically through the `counters` collection, and supplier/recipient party data is snapshotted at creation time for historical PDF rendering.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | MongoDB primary key. Public API exposes this as `id`. |
| `user_id` | string | Yes | Gateway-authenticated owner id. Every query filters by this field. |
| `company_id` | string | Yes for new records | Owning company id. |
| `partner_id` | string or null | No | Selected partner id when the invoice uses a stored partner. |
| `invoice_number` | string | Yes | Generated per user/company/year. |
| `counterparty` | string or null | No | Recipient display name, derived from partner/recipient details when possible. |
| `supplier_snapshot` | object | Yes for new records | Immutable company party snapshot used for PDF rendering. |
| `recipient_snapshot` | object | Yes for new records | Immutable partner or inline-recipient snapshot used for PDF rendering. |
| `issue_date` | datetime | Yes | Invoice issue date stored as a UTC datetime. API response exposes a date. |
| `tax_event_date` | datetime | Yes for new records | Tax event date. Must not be before `issue_date`. |
| `due_date` | datetime or null | No | Optional due date. Must not be before `issue_date`. |
| `place_of_supply` | string | Yes for new records | Defaults to `Bulgaria`. |
| `payment_method` | string | Yes for new records | `bank_transfer`, `cash`, `card`, or `other`. |
| `bank_name` | string or null | No | Optional bank name for Bulgarian invoice layout. |
| `bank_bic` | string or null | No | Optional BIC. |
| `bank_iban` | string or null | No | Optional IBAN. |
| `amount_in_words` | string or null | No | Amount in words; generated when omitted where supported. |
| `currency` | string | Yes | `BGN`, `EUR`, or `USD`. Default is `EUR`. |
| `items` | array | Yes | At least one invoice line item. |
| `items[].description` | string | Yes | Line description, 1-500 characters. |
| `items[].quantity` | Decimal128 | Yes | Quantity, greater than `0`. |
| `items[].unit_label` | string | Yes | Unit label for PDF layout, default `бр.`. |
| `items[].unit_price` | Decimal128 | Yes | Unit price, greater than or equal to `0`. |
| `items[].vat_rate` | Decimal128 | Yes | VAT rate from `0` to `1`. Default is `0.20`. |
| `items[].category` | string or null | No | Optional reporting category, max 120 characters. |
| `items[].subtotal` | Decimal128 | Yes | Calculated `quantity * unit_price`, rounded to 2 decimals. |
| `items[].vat_amount` | Decimal128 | Yes | Calculated VAT amount, rounded to 2 decimals. |
| `items[].total` | Decimal128 | Yes | Calculated line total, rounded to 2 decimals. |
| `subtotal` | Decimal128 | Yes | Sum of line subtotals. |
| `vat_total` | Decimal128 | Yes | Sum of line VAT amounts. |
| `total` | Decimal128 | Yes | Sum of line totals. |
| `status` | string | Yes | `draft`, `sent`, `paid`, `overdue`, or `cancelled`. Default is `draft`. |
| `vat_reason` | string or null | No | Reason shown when VAT is not charged. |
| `recipient_name` | string or null | No | Optional recipient/signature label. |
| `compiler_name` | string or null | No | Optional compiler/signature label. |
| `original_label` | string or null | No | Bulgarian original/copy label, default `ОРИГИНАЛ`. |
| `notes` | string or null | No | Optional notes, max 2000 characters. |
| `created_at` | datetime | Yes | Creation timestamp. |
| `updated_at` | datetime | Yes | Last update timestamp. |

Example document:

```json
{
  "_id": {"$oid": "665f1f77c9e0f7a8093bb733"},
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
  "issue_date": {"$date": "2026-04-26T00:00:00Z"},
  "tax_event_date": {"$date": "2026-04-26T00:00:00Z"},
  "due_date": {"$date": "2026-05-10T00:00:00Z"},
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
      "quantity": {"$numberDecimal": "1"},
      "unit_label": "бр.",
      "unit_price": {"$numberDecimal": "100.00"},
      "vat_rate": {"$numberDecimal": "0.20"},
      "category": "services",
      "subtotal": {"$numberDecimal": "100.00"},
      "vat_amount": {"$numberDecimal": "20.00"},
      "total": {"$numberDecimal": "120.00"}
    }
  ],
  "subtotal": {"$numberDecimal": "100.00"},
  "vat_total": {"$numberDecimal": "20.00"},
  "total": {"$numberDecimal": "120.00"},
  "status": "draft",
  "vat_reason": null,
  "recipient_name": null,
  "compiler_name": null,
  "original_label": "ОРИГИНАЛ",
  "notes": null,
  "created_at": {"$date": "2026-04-26T10:00:00Z"},
  "updated_at": {"$date": "2026-04-26T10:00:00Z"}
}
```

Indexes created on startup:

| Index | Purpose |
|-------|---------|
| `(user_id ASC, status ASC, issue_date DESC)` | Filter invoices by status and list newest first. |
| `(user_id ASC, issue_date DESC)` | User-scoped date-range lists and summaries. |
| `(user_id ASC, company_id ASC, issue_date DESC)` | Company-scoped invoice lists and summaries. |
| `(user_id ASC, company_id ASC, status ASC, issue_date DESC)` | Company + status filtering. |
| `(user_id ASC, company_id ASC, partner_id ASC)` | Partner-scoped invoice filtering and delete protection. |
| `(user_id ASC, counterparty ASC)` | User-scoped counterparty filters. |
| `(user_id ASC, items.category ASC)` | Category filters and grouped summaries over invoice lines. |
| `(user_id ASC, company_id ASC, invoice_number ASC)` unique | Prevent duplicate invoice numbers per company. |

## `expenses` Collection

Stores user-scoped expense records. Expenses may be invoice-backed or receipt-backed, and can be recorded with either a single amount or optional item lines.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | MongoDB primary key. Public API exposes this as `id`. |
| `user_id` | string | Yes | Gateway-authenticated owner id. Every query filters by this field. |
| `counterparty` | string | Yes | Vendor or payee name, 1-200 characters. |
| `expense_date` | datetime | Yes | Expense date stored as a UTC datetime. API response exposes a date. |
| `amount` | Decimal128 | Yes | Stored expense amount. Calculated from items when item lines are provided. |
| `currency` | string | Yes | `BGN`, `EUR`, or `USD`. Default is `EUR`. |
| `category` | string | Yes | `office`, `travel`, `meals`, `software`, `rent`, `utilities`, `professional_services`, `tax`, `payroll`, or `other`. |
| `description` | string or null | No | Optional description, max 1000 characters. |
| `deductible` | boolean | Yes | Whether the expense is deductible. Default is `true`. |
| `deductible_rate` | Decimal128 | Yes | Deductible rate from `0` to `1`. Default is `1.0`. |
| `deductible_amount` | Decimal128 | Yes | Calculated deductible amount. Non-deductible expenses store `0.00`. |
| `source_document_type` | string or null | No | Optional `invoice` or `receipt`. |
| `source_document_id` | string or null | No | Optional external or uploaded source document id. |
| `items` | array or null | No | Optional purchased goods/services line items. |
| `items[].description` | string | Yes when item exists | Line description, 1-500 characters. |
| `items[].quantity` | Decimal128 | Yes when item exists | Quantity, greater than `0`. |
| `items[].unit_price` | Decimal128 | Yes when item exists | Unit price, greater than or equal to `0`. |
| `items[].category` | string or null | No | Optional category override for the item. |
| `items[].total` | Decimal128 | Yes when item exists | Calculated `quantity * unit_price`, rounded to 2 decimals. |
| `created_at` | datetime | Yes | Creation timestamp. |
| `updated_at` | datetime | Yes | Last update timestamp. |

Example document:

```json
{
  "_id": {"$oid": "665f1f77c9e0f7a8093bb744"},
  "user_id": "665f1f77c9e0f7a8093bb700",
  "counterparty": "Office Store",
  "expense_date": {"$date": "2026-04-26T00:00:00Z"},
  "amount": {"$numberDecimal": "24.00"},
  "currency": "EUR",
  "category": "office",
  "description": "Printer paper",
  "deductible": true,
  "deductible_rate": {"$numberDecimal": "1.0000"},
  "deductible_amount": {"$numberDecimal": "24.00"},
  "source_document_type": "receipt",
  "source_document_id": "receipt-2026-04-26-1",
  "items": null,
  "created_at": {"$date": "2026-04-26T10:05:00Z"},
  "updated_at": {"$date": "2026-04-26T10:05:00Z"}
}
```

Indexes created on startup:

| Index | Purpose |
|-------|---------|
| `(user_id ASC, category ASC, expense_date DESC)` | Filter expenses by category and list newest first. |
| `(user_id ASC, expense_date DESC)` | User-scoped date-range lists and summaries. |
| `(user_id ASC, counterparty ASC)` | User-scoped counterparty filters. |
| `(user_id ASC, deductible ASC)` | Deductibility filters. |

## `counters` Collection

Stores atomic sequence counters used by invoice number generation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | string | Yes | Counter key, currently `invoice:{user_id}:{company_id}:{year}` for company-scoped invoices. |
| `seq` | integer | Yes | Last used sequence number. |

Indexes created on startup:

| Index | Purpose |
|-------|---------|
| `(_id ASC)` unique | Atomic lookup and increment for sequence counters. |

## API Shapes

`AgentResponse`:

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

`ConversationResponse`:

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
    }
  ],
  "created_at": "2026-04-26T10:01:00Z",
  "updated_at": "2026-04-26T10:01:04Z"
}
```

`AgentUpdate` PATCH payloads use explicit nullable semantics. Omitted fields are left unchanged, while fields sent as JSON `null` clear nullable values such as `description` and `config.system_prompt_override`. When `config` is provided, it is treated as the replacement Agent Service config object rather than a partial nested merge.

Example clearing nullable fields:

```json
{
  "description": null,
  "config": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "temperature": 0.2,
    "system_prompt_override": null
  }
}
```

`InvoiceResponse`:

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

`ExpenseResponse`:

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
  "source_document_id": "receipt-2026-04-26-1",
  "items": null,
  "id": "665f1f77c9e0f7a8093bb744",
  "user_id": "665f1f77c9e0f7a8093bb700",
  "deductible_amount": "24.00",
  "created_at": "2026-04-26T10:05:00Z",
  "updated_at": "2026-04-26T10:05:00Z"
}
```

`FinancialSummaryResponse`:

```json
{
  "invoice_total": "120.00",
  "expense_total": "24.00",
  "deductible_expense_total": "24.00",
  "net_total": "96.00",
  "buckets": [
    {
      "key": "2026-04",
      "invoice_total": "120.00",
      "expense_total": "24.00",
      "deductible_expense_total": "24.00"
    }
  ]
}
```

`ChatRequest`:

```json
{
  "message": "Calculate 20% VAT on 100 and explain it.",
  "conversation_id": null
}
```

SSE `ChatEvent` data is serialized as `event: <name>` plus JSON `data`, for example:

```text
event: token
data: {"content":"20% VAT on 100 is 20."}
```
