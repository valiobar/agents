# Business Service

## Current State

The Business Service owns structured business data and rules for companies, partners, invoices, expenses, invoice counters, financial summaries, and inventory workflows. Public clients reach it through the API Gateway at `/companies`, `/partners`, `/invoices`, `/expenses`, and `/inventory/*`. Agent and Knowledge services call Business over the internal Docker network when they need company validation or business records.

## Responsibility

Business is the source of truth for user-owned business records. It receives authenticated user context through `x-user-id`; it does not decode JWTs directly and every read/write is scoped by that user id.

Implemented responsibilities:

- Company issuer profile CRUD, including one default company per user.
- Partner CRUD scoped by `user_id + company_id`.
- Invoice creation, listing, retrieval, metadata/status update, totals, snapshots, and invoice numbering.
- Expense creation, listing, retrieval, item totals, and deductible amount calculation.
- Financial summary aggregation across invoice and expense records.
- Inventory item/location CRUD, stock movements, stock level derivation, and inventory search.
- Supplier invoice import preview lifecycle (create/list/get/update/confirm/cancel).
- Invoice stock deduction for inventory-linked lines on `draft -> sent` transition.
- Internal company ownership validation through `GET /companies/{company_id}/exists`.
- MongoDB index creation for business collections during startup.

Business explicitly does not own chat runtime, SSE streaming, LLM providers, RAG retrieval, user authentication, or gateway routing. Agent owns chat/tool orchestration and calls Business through `BusinessClient`; Gateway owns JWT validation and prefix routing.

## Internal Architecture

```text
app/
  main.py
  config.py
  dependencies.py
company/
  models.py
  routes/
    companies.py           # Company issuer profile CRUD and existence check
  repositories/
    company_repo.py        # User-scoped company MongoDB access
  services/
    company_service.py     # Company ownership and delete protection
partner/
  models.py
  routes/
    partners.py            # Company-scoped partner CRUD
  repositories/
    partner_repo.py        # User/company-scoped partner MongoDB access
  services/
    partner_service.py     # Partner ownership and invoice delete protection
financial/
  models.py                # Invoice, expense, and summary schemas
  routes/
    invoices.py            # Invoice create/list/get/update
    expenses.py            # Expense create/list/get
    financial_summary.py   # Internal summary aggregation endpoint
  repositories/
    invoice_repo.py        # Invoice, counters, filters, summary aggregation
    expense_repo.py        # Expense filters and summary aggregation
    financial_utils.py     # Decimal, date, and currency helpers
  services/
    invoice_service.py     # Invoice snapshots, numbering, totals, status rules
    expense_service.py     # Expense item totals and deductible amounts
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
  db.py                    # Motor client lifecycle and index creation
```

Routes do request/response handling only. Services own business rules and orchestration. Repositories own MongoDB access and query construction. Models own validation and JSON serialization.

## API Surface

All public calls go through the gateway at `http://localhost:8010`. Direct internal calls require `x-user-id`.

| Route | Status | Purpose |
|-------|--------|---------|
| `GET /health` | Implemented | Internal health check |
| `POST /companies` | Implemented | Create a current-user company profile |
| `GET /companies?limit=50&offset=0` | Implemented | List current-user companies |
| `GET /companies/{company_id}` | Implemented | Get one owned company |
| `PATCH /companies/{company_id}` | Implemented | Update one owned company |
| `DELETE /companies/{company_id}` | Implemented | Delete an unreferenced owned company |
| `GET /companies/{company_id}/exists` | Implemented | Internal ownership validation for Agent and Knowledge |
| `POST /partners` | Implemented | Create a partner under an owned company |
| `GET /partners?company_id=...&kind=...&query=...` | Implemented | List/search partners for one company |
| `GET /partners/{partner_id}?company_id=...` | Implemented | Get one company-scoped partner |
| `PATCH /partners/{partner_id}?company_id=...` | Implemented | Update one company-scoped partner |
| `DELETE /partners/{partner_id}?company_id=...` | Implemented | Delete an unreferenced company-scoped partner |
| `POST /invoices` | Implemented | Create an invoice |
| `GET /invoices?company_id=...&status=...` | Implemented | List current-user invoices with filters |
| `GET /invoices/{invoice_id}` | Implemented | Get one current-user invoice |
| `PATCH /invoices/{invoice_id}` | Implemented | Update invoice status, due date, or notes |
| `POST /expenses` | Implemented | Record an expense |
| `GET /expenses?category=...&date_from=...` | Implemented | List current-user expenses with filters |
| `GET /expenses/{expense_id}` | Implemented | Get one current-user expense |
| `POST /inventory/items` | Implemented | Create inventory item (company-scoped) |
| `GET /inventory/items?company_id=...` | Implemented | List inventory items with optional filters |
| `GET /inventory/items/{item_id}?company_id=...` | Implemented | Get one company item |
| `PATCH /inventory/items/{item_id}?company_id=...` | Implemented | Update one company item |
| `POST /inventory/locations` | Implemented | Create inventory location |
| `GET /inventory/locations?company_id=...` | Implemented | List locations |
| `GET /inventory/locations/{location_id}?company_id=...` | Implemented | Get one location |
| `PATCH /inventory/locations/{location_id}?company_id=...` | Implemented | Update one location |
| `POST /inventory/movements` | Implemented | Append stock movement |
| `GET /inventory/movements?company_id=...` | Implemented | List stock movements |
| `GET /inventory/levels?company_id=...` | Implemented | Get derived stock levels |
| `POST /inventory/search` | Implemented | Search inventory with optional stock aggregation |
| `POST /inventory/import-previews` | Implemented | Create import preview draft |
| `GET /inventory/import-previews?company_id=...` | Implemented | List previews |
| `GET /inventory/import-previews/{preview_id}` | Implemented | Get preview |
| `PATCH /inventory/import-previews/{preview_id}` | Implemented | Update preview lines |
| `POST /inventory/import-previews/{preview_id}/confirm` | Implemented | Confirm preview and apply receipts |
| `POST /inventory/import-previews/{preview_id}/cancel` | Implemented | Cancel preview |
| `POST /financial-summary` | Implemented | Internal summary endpoint used by Agent tools |

## Domain Rules

Companies represent invoice issuer profiles. A company is scoped by `user_id`, and `registration_number` is unique per user. If a company is marked `is_default=true`, other companies for that user are unset as default.

Partners represent reusable clients, suppliers, or both. They are scoped by `user_id + company_id`, and `registration_number` is unique within that scope. Partner routes require `company_id` so a partner id cannot be loaded outside its owning company.

Invoices require `company_id` and either `partner_id` or full `recipient` details. Business validates the company, resolves the partner inside the same company when present, snapshots supplier and recipient data, generates an invoice number through `counters`, calculates line totals server-side, and stores money as BSON `Decimal128`.

Expenses are user-scoped. They can be recorded with a single `amount` or optional item lines; if lines are present, the stored amount is calculated from line totals. Deductible expenses store `deductible_amount = amount * deductible_rate`; non-deductible expenses store `0.00`.

Inventory is company-scoped. Items enforce unique SKU per `user_id + company_id`; levels are derived from append-only stock movements. Import preview confirmation can create/update items and record `receipt` movements. Invoice status transition `draft -> sent` can issue inventory for lines that carry `inventory_item_id`.

Delete protection:

- Company deletes return `409` while Business invoices or partners reference the company.
- Partner deletes return `409` while invoices reference the partner.
- Company delete protection for assigned Agent records is intentionally deferred to an internal Agent API if required.

## Financial Summary

`POST /financial-summary` is primarily an internal Agent-facing endpoint. It accepts optional `company_id`, `partner_id`, `date_from`, `date_to`, `group_by`, `include_invoices`, and `include_expenses`.

Supported `group_by` values:

- `category`
- `counterparty`
- `month`

The response includes top-level totals, per-bucket totals when grouped, `totals_by_currency`, configured `exchange_rates_to_bgn`, and `unsupported_currencies`. The service can convert `BGN` and `EUR`; unsupported currencies stay visible in `totals_by_currency` and are listed in `unsupported_currencies`.

## Cross-Domain Dependencies

Business owns its internal cross-domain dependencies:

- `financial` depends on `company` and `partner` for validation/snapshots and on `inventory` for stock issue on invoice send.
- `inventory` depends on `company` ownership checks.
- External services (Agent, Knowledge, Gateway) never import these modules; they use Business HTTP contracts.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `MONGODB_URL` | `mongodb://mongodb:27017` | MongoDB connection string. |
| `DB_NAME` | `agents` | Database used by the service. |

## Run And Verify

Start Business with its runtime dependencies and gateway:

```bash
cp .env.example .env
docker compose up --build mongodb business gateway
```

Health checks:

```bash
curl http://localhost:8010/health
docker compose exec business python -m compileall app
docker compose logs business
```

Create a company, partner, invoice, expense, and summary through the gateway:

```bash
curl -X POST http://localhost:8010/companies \
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

curl -X POST http://localhost:8010/partners \
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

curl -X POST http://localhost:8010/invoices \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "'"$COMPANY_ID"'",
    "partner_id": "'"$PARTNER_ID"'",
    "issue_date": "2026-04-26",
    "tax_event_date": "2026-04-26",
    "due_date": "2026-05-10",
    "currency": "EUR",
    "items": [
      {
        "description": "Accounting consultation",
        "quantity": "1",
        "unit_price": "100.00",
        "vat_rate": "0.20",
        "category": "services"
      }
    ]
  }'

curl -X POST http://localhost:8010/expenses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "counterparty": "Office Store",
    "expense_date": "2026-04-26",
    "amount": "24.00",
    "currency": "EUR",
    "category": "office",
    "source_document_type": "receipt"
  }'
```

Internal summary smoke from another service container:

```bash
docker compose exec agent python - <<'PY'
import asyncio
import httpx

async def main():
    async with httpx.AsyncClient(base_url="http://business:8005") as client:
        response = await client.post(
            "/financial-summary",
            headers={"x-user-id": "smoke-user"},
            json={"include_invoices": True, "include_expenses": True},
        )
        print(response.status_code, response.text)

asyncio.run(main())
PY
```

## Common Failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `401 Missing x-user-id header` on direct service calls | Bypassing the gateway without internal auth context | Use the gateway or include `x-user-id` for internal smoke tests. |
| Company/partner/invoice/expense/inventory resource returns `404` | The id is invalid, missing, or belongs to another user/company | Use the owning user's token and matching `company_id`. |
| Company delete returns `409 Company has invoices` | Existing invoices reference the company | Keep the company for historical invoices. |
| Company delete returns `409 Company has partners` | Existing partners reference the company | Delete unreferenced partners first or keep the company. |
| Partner delete returns `409 Partner has invoices` | Existing invoices reference the partner | Keep the partner for historical invoices. |
| Invoice create returns `422 partner_id or recipient is required` | Neither a stored partner nor inline recipient was provided | Send `partner_id` or full `recipient` details. |
| Invoice update returns `400 Invalid invoice status transition` | The requested status transition is not allowed | Use `draft -> sent/cancelled`, `sent -> paid/overdue/cancelled`, or `overdue -> paid/cancelled`. |
| Money or date request returns `422` | Invalid Decimal/date/category/status value | Send money as strings and dates as `YYYY-MM-DD`. |

## Architectural Rules

- Keep all endpoints `async def`.
- Every non-streaming endpoint must define a Pydantic `response_model`.
- All user-scoped reads and writes must filter by `x-user-id`.
- Keep Business logic in services and MongoDB access in repositories.
- Avoid N+1 queries; use repository filters and aggregation pipelines.
- Add indexes for fields used in filters, sorts, and unique constraints.
- Do not import Agent, Knowledge, Gateway, or frontend code into Business.
