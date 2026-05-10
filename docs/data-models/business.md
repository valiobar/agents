# Business Service Data Models

The Business Service owns the `companies`, `partners`, `invoices`, `expenses`, `counters`, `inventory_items`, `inventory_locations`, `stock_movements`, and `inventory_import_previews` MongoDB collections. Ownership is scoped by the gateway-authenticated `user_id` that arrives as `x-user-id`; company domains additionally carry `company_id`.

Business exposes public domain APIs through Gateway for `/companies`, `/partners`, `/invoices`, `/expenses`, and `/inventory/*`. Agent tools call Business directly over internal HTTP for company lookup, partner/invoice/expense/inventory operations, and financial summaries through `POST /financial-summary`.

Source files:

- `services/business/app/company/models.py`
- `services/business/app/partner/models.py`
- `services/business/app/financial/models.py`
- `services/business/app/company/repositories/company_repo.py`
- `services/business/app/partner/repositories/partner_repo.py`
- `services/business/app/financial/repositories/invoice_repo.py`
- `services/business/app/financial/repositories/expense_repo.py`
- `services/business/app/financial/services/financial_summary_service.py`
- `services/business/app/inventory/models.py`
- `services/business/app/inventory/repositories/inventory_item_repo.py`
- `services/business/app/inventory/repositories/inventory_location_repo.py`
- `services/business/app/inventory/repositories/stock_movement_repo.py`
- `services/business/app/inventory/repositories/inventory_import_preview_repo.py`
- `services/business/app/inventory/services/inventory_service.py`
- `services/business/app/inventory/services/inventory_search_service.py`
- `services/business/app/inventory/services/inventory_import_service.py`

## Inventory Collections

`inventory_items` stores company-scoped item master data (SKU, aliases, barcode, unit, reorder settings, supplier link).

`inventory_locations` stores company-scoped stock locations, including optional default location.

`stock_movements` stores append-only quantity deltas (`receipt`, `issue`, `adjustment`, `transfer_in`, `transfer_out`, `return`) and source metadata for idempotency.

`inventory_import_previews` stores draft/confirmed/cancelled supplier import review state before applying inventory writes.

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
| `items[].unit_label` | string | Yes | Unit label for PDF layout, default `??.`. |
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
| `original_label` | string or null | No | Bulgarian original/copy label, default `????????`. |
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
  "amount_in_words": "??? ? ???????? ????",
  "currency": "EUR",
  "items": [
    {
      "description": "Accounting consultation",
      "quantity": {"$numberDecimal": "1"},
      "unit_label": "??.",
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
  "original_label": "????????",
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

Stores company-scoped expense records. Expenses may be invoice-backed or receipt-backed, and can be recorded with either a single amount or optional item lines.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | MongoDB primary key. Public API exposes this as `id`. |
| `user_id` | string | Yes | Gateway-authenticated owner id. Every query filters by this field. |
| `company_id` | string | Yes for new records | Owning company id used for scoped filtering and summaries. |
| `partner_id` | string or null | No | Optional linked partner id in the same company. |
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
| `(user_id ASC, company_id ASC, expense_date DESC)` | Company-scoped date-range lists and summaries. |
| `(user_id ASC, company_id ASC, category ASC, expense_date DESC)` | Company-scoped category filtering. |
| `(user_id ASC, company_id ASC, partner_id ASC)` | Partner-scoped expense filtering and summaries. |
| `(user_id ASC, company_id ASC, counterparty ASC)` | Company-scoped counterparty filters. |
| `(user_id ASC, company_id ASC, deductible ASC)` | Company-scoped deductibility filters. |

### Legacy Backfill: Missing `company_id`

Older rows may still have missing or `null` `company_id` from the previous user-scoped contract. New writes are validated to require `company_id`, and company-scoped list/summary flows do not include legacy rows until they are assigned.

Run this one-time backfill script:

```bash
python scripts/migrations/backfill_expense_company_id.py --report-path scripts/migrations/reports/backfill_expense_company_id_report.json
```

Backfill behavior:

- Auto-assign `company_id` only when the owning user has exactly one company.
- Leave ambiguous users unchanged (`0` companies or `>1` companies).
- Write a JSON report with `ambiguous_users` for manual follow-up.
- Use `--dry-run` first to preview updates and ambiguity count.

### Search Normalization Backfill

Normalized search fields are indexed for fast exact/prefix lookups:

- `companies`: `name_normalized`, `registration_number_normalized`, `vat_number_normalized`, `search_text`
- `partners`: `name_normalized`, `registration_number_normalized`, `vat_number_normalized`, `search_text`
- `invoices`: `counterparty_normalized`
- `expenses`: `counterparty_normalized`

For legacy rows created before these fields existed, run:

```bash
python scripts/migrations/backfill_search_normalized_fields.py
```

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

List endpoints (`GET /companies`, `GET /partners`, `GET /invoices`, `GET /expenses`) return a shared envelope:

```json
{
  "total_count": 123,
  "returned_count": 20,
  "offset": 0,
  "limit": 20,
  "truncated": true,
  "next_offset": 20,
  "items": []
}
```

`truncated=true` means additional rows are available and callers should continue with `next_offset`.

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
  "amount_in_words": "??? ? ???????? ????",
  "currency": "EUR",
  "items": [
    {
      "description": "Accounting consultation",
      "quantity": "1",
      "unit_label": "??.",
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
  "original_label": "????????",
  "notes": null,
  "created_at": "2026-04-26T10:00:00Z",
  "updated_at": "2026-04-26T10:00:00Z"
}
```

`ExpenseResponse`:

```json
{
  "company_id": "665f1f77c9e0f7a8093bb701",
  "partner_id": null,
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
  "currency": "EUR",
  "exchange_rates_to_eur": {
    "EUR": "1",
    "BGN": "0.51129188"
  },
  "invoice_total": "120.00",
  "expense_total": "24.00",
  "deductible_expense_total": "24.00",
  "net_total": "96.00",
  "totals_by_currency": [
    {
      "currency": "EUR",
      "invoice_total": "120.00",
      "expense_total": "24.00",
      "deductible_expense_total": "24.00",
      "net_total": "96.00"
    }
  ],
  "unsupported_currencies": [],
  "buckets": [
    {
      "key": "2026-04",
      "invoice_total": "120.00",
      "expense_total": "24.00",
      "deductible_expense_total": "24.00",
      "totals_by_currency": [
        {
          "currency": "EUR",
          "invoice_total": "120.00",
          "expense_total": "24.00",
          "deductible_expense_total": "24.00",
          "net_total": "96.00"
        }
      ]
    }
  ]
}
```

When `partner_id` is supplied in summary requests, `company_id` is required so ownership can be validated.
