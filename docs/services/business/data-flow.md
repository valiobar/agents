# Business Service Data Flow

## Gateway Company Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Business
    participant Mongo

    Client->>Gateway: POST /companies + JWT
    Gateway->>Gateway: validate JWT and inject x-user-id
    Gateway->>Business: POST /companies + x-user-id
    Business->>Business: validate CompanyCreate
    opt is_default=true
        Business->>Mongo: unset other default companies for user_id
    end
    Business->>Mongo: insert company scoped to user_id
    Mongo-->>Business: saved company
    Business-->>Gateway: CompanyResponse
    Gateway-->>Client: CompanyResponse
```

Company list/get/update/delete follow the same `x-user-id` scoping. Invalid company ids and cross-user access return `404 Company not found`.

## Partner Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Business
    participant Mongo

    Client->>Gateway: POST /partners { company_id, ... } + JWT
    Gateway->>Gateway: validate JWT and inject x-user-id
    Gateway->>Business: POST /partners + x-user-id
    Business->>Mongo: verify company by user_id + company_id
    Business->>Mongo: insert partner scoped to user_id + company_id
    Mongo-->>Business: saved partner
    Business-->>Gateway: PartnerResponse
    Gateway-->>Client: PartnerResponse
```

Partner list/get/update/delete always require `company_id`. This keeps partner ids scoped to the company boundary and prevents loading one company's partner from another company route.

## Invoice Creation Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Business
    participant Mongo

    Client->>Gateway: POST /invoices + JWT
    Gateway->>Gateway: validate JWT and inject x-user-id
    Gateway->>Business: POST /invoices + x-user-id
    Business->>Mongo: load company by user_id + company_id
    alt partner_id supplied
        Business->>Mongo: resolve partner by id, registration number, or name within company
        Mongo-->>Business: partner
        Business->>Business: create recipient snapshot from partner
    else inline recipient supplied
        Business->>Business: validate recipient and create snapshot
    end
    Business->>Mongo: increment counters invoice:{user_id}:{company_id}:{year}
    Mongo-->>Business: next sequence
    Business->>Business: calculate line totals, VAT, subtotal, total
    Business->>Mongo: insert invoice with supplier and recipient snapshots
    Mongo-->>Business: saved invoice
    Business-->>Gateway: InvoiceResponse
    Gateway-->>Client: InvoiceResponse
```

Invoice creation is the only path that creates supplier and recipient snapshots. Later updates can change `status`, `due_date`, or `notes`, but do not recalculate historical party snapshots.

## Invoice Query And Update Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Business
    participant Mongo

    Client->>Gateway: GET /invoices?company_id=...&status=...
    Gateway->>Business: forward with x-user-id
    Business->>Mongo: find invoices by user_id and filters
    Mongo-->>Business: sorted invoice list
    Business-->>Gateway: list[InvoiceResponse]
    Gateway-->>Client: JSON response

    Client->>Gateway: PATCH /invoices/{invoice_id}
    Gateway->>Business: forward with x-user-id
    Business->>Mongo: load invoice by user_id + invoice_id
    Business->>Business: validate status transition if status changes
    Business->>Mongo: update status, due_date, or notes
    Mongo-->>Business: updated invoice
    Business-->>Gateway: InvoiceResponse
    Gateway-->>Client: JSON response
```

Supported invoice filters are `company_id`, `partner_id`, `status`, `date_from`, `date_to`, `counterparty`, `amount_min`, `amount_max`, and `category`. Lists are sorted by newest `issue_date` first.

## Expense Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Business
    participant Mongo

    Client->>Gateway: POST /expenses + JWT
    Gateway->>Gateway: validate JWT and inject x-user-id
    Gateway->>Business: POST /expenses + x-user-id
    Business->>Business: validate ExpenseCreate
    alt item lines supplied
        Business->>Business: calculate amount from quantity * unit_price
    else amount supplied
        Business->>Business: use supplied amount
    end
    Business->>Business: calculate deductible_amount
    Business->>Mongo: insert expense scoped to user_id
    Mongo-->>Business: saved expense
    Business-->>Gateway: ExpenseResponse
    Gateway-->>Client: ExpenseResponse
```

Supported expense filters are `category`, `counterparty`, `date_from`, `date_to`, `deductible`, `amount_min`, and `amount_max`. Lists are sorted by newest `expense_date` first.

## Financial Summary Flow

```mermaid
sequenceDiagram
    participant Agent
    participant Business
    participant InvoiceRepo
    participant ExpenseRepo
    participant Mongo

    Agent->>Business: POST /financial-summary + x-user-id
    Business->>Business: validate FinancialSummaryRequest
    opt include_invoices=true
        Business->>InvoiceRepo: aggregate_summary(user_id, request)
        InvoiceRepo->>Mongo: invoice aggregation pipeline
        Mongo-->>InvoiceRepo: grouped invoice rows
        InvoiceRepo-->>Business: invoice totals by key and currency
    end
    opt include_expenses=true
        Business->>ExpenseRepo: aggregate_summary(user_id, request)
        ExpenseRepo->>Mongo: expense aggregation pipeline
        Mongo-->>ExpenseRepo: grouped expense rows
        ExpenseRepo-->>Business: expense totals by key and currency
    end
    Business->>Business: merge totals, convert BGN/EUR, sort buckets
    Business-->>Agent: FinancialSummaryResponse
```

`/financial-summary` is used by Agent tools over the internal network. It is still a normal FastAPI endpoint with `x-user-id` scoping, so it can be smoke-tested directly from another service container.

## Company Validation Flow

```mermaid
sequenceDiagram
    participant Caller as Agent or Knowledge
    participant Business
    participant Mongo

    Caller->>Business: GET /companies/{company_id}/exists + x-user-id
    Business->>Mongo: find company by _id + user_id
    alt company exists for user
        Business-->>Caller: 200 {"exists": true}
    else missing or cross-user
        Business-->>Caller: 404 {"detail": "Company not found"}
    end
```

Agent uses this flow when creating/updating agents with a `company_id` or listing agents with a company filter. Knowledge uses it when validating company-scoped document operations.

## Delete Protection Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Business
    participant Mongo

    Client->>Gateway: DELETE /companies/{company_id}
    Gateway->>Business: forward with x-user-id
    Business->>Mongo: require company by user_id + company_id
    Business->>Mongo: count invoices for company
    alt invoices exist
        Business-->>Gateway: 409 Company has invoices
    else no invoices
        Business->>Mongo: count partners for company
        alt partners exist
            Business-->>Gateway: 409 Company has partners
        else no Business references
            Business->>Mongo: delete company
            Business-->>Gateway: 204 No Content
        end
    end
```

Partner deletion follows the same pattern and returns `409 Partner has invoices` while any invoice references the partner.

## Write Paths

| Data | Write path |
|------|------------|
| Companies | Gateway -> Business company route -> CompanyService -> CompanyRepository -> MongoDB |
| Partners | Gateway or Agent BusinessClient -> Business partner route -> PartnerService -> PartnerRepository -> MongoDB |
| Invoices | Gateway or Agent BusinessClient -> Business invoice route -> InvoiceService -> InvoiceRepository -> MongoDB |
| Expenses | Gateway or Agent BusinessClient -> Business expense route -> ExpenseService -> ExpenseRepository -> MongoDB |
| Counters | InvoiceService -> InvoiceRepository.next_invoice_number -> MongoDB `counters` |
| Financial summaries | Read-only aggregation over `invoices` and `expenses`; no summary document is stored |

## Error And Response Flow

| Condition | Response |
|-----------|----------|
| Missing `x-user-id` | `401 Missing x-user-id header` |
| Invalid or cross-user company id | `404 Company not found` |
| Invalid or cross-company partner id | `404 Partner not found` |
| Invalid invoice or expense id | `404 Invoice not found` / `404 Expense not found` |
| Duplicate unique business key | Mongo duplicate-key error surfaced by FastAPI unless specifically handled by caller |
| Invalid invoice status transition | `400 Invalid invoice status transition` |
| Pydantic validation failure | `422` with validation details |
| Protected company/partner delete | `409` with dependency detail |
