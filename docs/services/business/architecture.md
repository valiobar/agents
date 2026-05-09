# Business Service Architecture

## Current State

The Business Service is the structured-data microservice for the Agent Platform. It owns company issuer profiles, partners, invoices, expenses, invoice counters, financial summary aggregation, and inventory data/flows. It is internal to Docker Compose on port `8005`; public traffic reaches it only through the API Gateway.

## Implemented Responsibilities

- User-scoped company CRUD and default company handling.
- Company-scoped partner CRUD and search.
- Invoice creation with supplier/recipient snapshots, line total calculation, invoice numbering, and status transition rules.
- Expense creation with item total calculation and deductible amount calculation.
- MongoDB filtering for invoices and expenses by common reporting fields.
- Financial summary aggregation by category, counterparty, or month.
- Inventory item CRUD with SKU uniqueness per company, aliases, and search text composition.
- Inventory location CRUD with company-level default location support.
- Append-only stock movement ledger for receipts, issues, adjustments, transfers, and returns.
- Derived stock level aggregation from movements and multi-layer inventory search (SKU/barcode/alias/text/prefix).
- Supplier invoice import preview lifecycle with draft review, confirm, and cancel flows.
- Invoice-to-inventory integration: stock issue on `draft -> sent` transition for linked invoice lines.
- Internal company ownership validation for Agent and Knowledge through `/companies/{company_id}/exists`.
- Startup index creation for all Business-owned collections.

## Service Boundary

Business owns these public gateway prefixes:

- `/companies`
- `/partners`
- `/invoices`
- `/expenses`
- `/inventory`

Business also exposes internal `/financial-summary` for Agent tools. The gateway does not currently route `/financial-summary` publicly; Agent calls it through the internal Docker network.

Business-owned collections are:

- `companies`
- `partners`
- `invoices`
- `expenses`
- `counters`
- `inventory_items`
- `inventory_locations`
- `stock_movements`
- `inventory_import_previews`

Business does not own:

- JWT validation or rate limiting - Gateway owns these.
- Agent lifecycle, chat runtime, SSE, LangChain tools, or LLM providers - Agent owns these.
- Document metadata, embeddings, or retrieval - Knowledge owns these.
- User accounts and tokens - Auth owns these.

## Layers

```text
routes/ -> domain services -> domain repositories -> domain models
                                    \-> utils/db.py
```

| Layer | Responsibility |
|-------|----------------|
| `routes/` | FastAPI endpoints, dependency injection, query parameters, response models |
| `company/services/`, `partner/services/`, `financial/services/`, `inventory/services/` | Business rules, ownership checks, calculations, delete protection |
| `company/repositories/`, `partner/repositories/`, `financial/repositories/`, `inventory/repositories/` | MongoDB collection access, filters, aggregation pipelines, Decimal/date conversion |
| `company/models.py`, `partner/models.py`, `financial/models.py`, `inventory/models.py` | Pydantic request/response contracts and validation |
| `utils/db.py` | Motor client lifecycle and index creation |

Routes never touch MongoDB directly. Repositories do not contain business decisions such as status workflows or delete protection.

## Concrete Modules

```text
app/
  main.py
  config.py
  dependencies.py
  company/
    models.py
    routes/
      companies.py
    repositories/
      company_repo.py
    services/
      company_service.py
  partner/
    models.py
    routes/
      partners.py
    repositories/
      partner_repo.py
    services/
      partner_service.py
  financial/
    models.py
    routes/
      invoices.py
      expenses.py
      financial_summary.py
    repositories/
      invoice_repo.py
      expense_repo.py
      financial_utils.py
    services/
      invoice_service.py
      expense_service.py
      financial_summary_service.py
  inventory/
    models.py
    routes/
      inventory_items.py
      inventory_locations.py
      inventory_movements.py
      inventory_levels.py
      inventory_search.py
      inventory_import_previews.py
    repositories/
      inventory_item_repo.py
      inventory_location_repo.py
      stock_movement_repo.py
      inventory_import_preview_repo.py
    services/
      inventory_service.py
      inventory_search_service.py
      inventory_import_service.py
  utils/
    db.py
```

## Main Patterns

- **Layered architecture:** route handlers call services, services call repositories.
- **Repository pattern:** all MongoDB access and query construction are isolated in repository classes.
- **Service-layer invariants:** ownership, delete protection, invoice calculations, expense calculations, and status transitions live in services.
- **Gateway-authenticated context:** every route depends on `get_user_id()`, which requires `x-user-id`.
- **Stable public prefixes:** the gateway keeps `/companies`, `/partners`, `/invoices`, `/expenses`, and `/inventory/*` URLs stable.

## Cross-Domain Dependencies (Inside Business)

Business centralizes cross-domain dependencies internally so external services can call one domain boundary:

- `financial/services/invoice_service.py` depends on `company` and `partner` domains for ownership/snapshot validation and on `inventory` for stock issuing when an invoice transitions from `draft` to `sent`.
- `inventory/services/*` depends on `company` domain ownership checks so inventory writes are always company-scoped.
- These are in-service dependencies only; Agent and Knowledge use Business via HTTP contracts rather than importing Business modules.

## Request Context

Business trusts the gateway or internal callers to provide `x-user-id`. Missing headers return `401 Missing x-user-id header`.

Every repository query filters by `user_id`. Company-scoped resources also validate `company_id`:

- Partner create/list/get/update/delete validates the company first.
- Invoice create validates the company and validates any selected partner inside the same company.
- `GET /companies/{company_id}/exists` calls the same company ownership check used by public company reads.
- Inventory item/location/movement/list/search/import endpoints validate `company_id` ownership before data changes.

Invalid ObjectIds and cross-user access are normalized as `404`, so callers cannot distinguish "missing" from "belongs to another user".

## Company And Partner Rules

Companies store invoice issuer data. `registration_number` is unique per user. At most one company can be default for a user; setting a company as default unsets the others.

Partners store reusable counterparties under one company. `kind` is one of `client`, `supplier`, `both`, or `other`. `registration_number` is unique per user/company, which supports idempotent CompanyBook imports through Agent tools.

Delete protection is intentionally local to Business-owned data:

- Company delete checks Business invoices and partners.
- Partner delete checks Business invoices.
- Assigned-Agent delete protection is deferred; Business does not import Agent repositories.

## Invoice Rules

Invoice creation requires:

- An owned `company_id`.
- A `partner_id` that resolves inside the same company, or full inline `recipient` details.
- At least one line item.
- `tax_event_date >= issue_date`.
- `due_date >= issue_date` when due date is supplied.

Business snapshots supplier data from the company and recipient data from the partner or inline recipient input. The snapshots preserve historical invoice rendering even when company or partner records change later.

Invoice numbers are generated atomically from `counters` with this key shape:

```text
invoice:{user_id}:{company_id}:{year}
```

The public invoice number format is:

```text
INV-{year}-{seq:05d}
```

Line totals are calculated server-side:

```text
subtotal = quantity * unit_price
vat_amount = subtotal * vat_rate
total = subtotal + vat_amount
```

Allowed status transitions:

| Current | Allowed next statuses |
|---------|-----------------------|
| `draft` | `sent`, `cancelled` |
| `sent` | `paid`, `overdue`, `cancelled` |
| `overdue` | `paid`, `cancelled` |
| `paid` | none |
| `cancelled` | none |

## Expense Rules

Expense creation requires a counterparty, expense date, category, and either `amount` or item lines.

If item lines are provided, Business calculates the stored amount from the item totals. If a single amount is provided, Business stores that amount directly.

Deductible amount is calculated as:

```text
deductible_amount = amount * deductible_rate
```

When `deductible=false`, Business stores `deductible_amount = 0.00`.

## Financial Summary Rules

Financial summaries combine invoice and expense aggregations. Invoices can be filtered by `company_id`, `partner_id`, and date range. Expenses are currently user-scoped and date-filtered for summary aggregation.

Supported grouping:

| `group_by` | Invoice grouping | Expense grouping |
|------------|------------------|------------------|
| `category` | `items.category` after `$unwind` | `category` |
| `counterparty` | `counterparty` | `counterparty` |
| `month` | `issue_date` formatted as `YYYY-MM` | `expense_date` formatted as `YYYY-MM` |
| omitted | `all` | `all` |

The response contains per-currency totals and top-level converted totals. `BGN` and `EUR` can be converted with the configured rate `1.00 EUR = 1.95583000 BGN`; unsupported currencies are listed in `unsupported_currencies`.

## Inventory Rules

Inventory supports these public route groups:

- `/inventory/items`
- `/inventory/locations`
- `/inventory/movements`
- `/inventory/levels`
- `/inventory/search`
- `/inventory/import-previews`

Core invariants:

- Inventory item `sku` is unique per `user_id + company_id`.
- Item `barcode` is indexed for fast lookup and aliases/search text are used by search fallback.
- Stock is append-only through `stock_movements`; current levels are derived from movement aggregation.
- Source-backed movements are idempotent via unique `(user_id, source_type, source_id, source_line_id)`.
- Confirming an import preview creates/updates inventory items and records receipt movements.
- Sending an invoice can record issue movements for lines linked to `inventory_item_id`.

## Persistence

Business uses MongoDB through Motor. `connect_db()` pings MongoDB and creates indexes during FastAPI lifespan startup. The client is closed during shutdown.

Owned collections:

- `companies`
- `partners`
- `invoices`
- `expenses`
- `counters`
- `inventory_items`
- `inventory_locations`
- `stock_movements`
- `inventory_import_previews`

Money values are represented as Python `Decimal`, persisted as BSON `Decimal128`, and serialized to JSON as strings. Date-only API values are stored as UTC datetimes for range queries and converted back to dates in responses.

## Restrictions

- Every route must be `async def`.
- Every endpoint must define a Pydantic `response_model`.
- All user data must be filtered by `x-user-id`.
- Business must not import Agent repositories or runtime code.
- Business must not call ChromaDB or LLM providers.
- Cross-service access must use internal HTTP contracts, not database sharing.
