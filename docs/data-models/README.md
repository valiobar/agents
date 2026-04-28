# Data Models

This folder documents the data models that currently exist in code and the MongoDB collections they persist to.

## Current Model Inventory

| Area | Status | Source | Documentation |
|------|--------|--------|---------------|
| Auth request/response models | Implemented | `services/auth/app/models/user.py` | `auth.md` |
| Auth `users` MongoDB document | Implemented | `services/auth/app/models/user.py`, `services/auth/app/repositories/user_repo.py` | `auth.md` |
| Auth JWT payloads | Implemented | `services/auth/app/utils/jwt.py` | `auth.md` |
| Agent models | Implemented | `services/agent/app/models/agent.py`, `services/agent/app/repositories/agent_repo.py` | `agent.md` |
| Agent conversation models | Implemented | `services/agent/app/models/conversation.py`, `services/agent/app/repositories/conversation_repo.py` | `agent.md` |
| Agent chat request/SSE models | Implemented | `services/agent/app/models/chat.py`, `services/agent/app/services/chat_service.py` | `agent.md` |
| Business company models | Implemented | `services/business/app/models/company.py`, `services/business/app/repositories/company_repo.py` | `business.md` |
| Business partner models | Implemented | `services/business/app/models/partner.py`, `services/business/app/repositories/partner_repo.py` | `business.md` |
| Business invoice models | Implemented | `services/business/app/models/financial.py`, `services/business/app/repositories/invoice_repo.py` | `business.md` |
| Business expense models | Implemented | `services/business/app/models/financial.py`, `services/business/app/repositories/expense_repo.py` | `business.md` |
| Business invoice counters | Implemented | `services/business/app/repositories/invoice_repo.py` | `business.md` |
| Business financial summary models | Implemented | `services/business/app/models/financial.py`, `services/business/app/services/financial_summary_service.py` | `business.md` |
| Knowledge Base document models | Implemented | `services/knowledge/app/models/document.py`, `services/knowledge/app/repositories/document_repo.py` | `knowledge.md` |
| Knowledge Base retrieval models | Implemented | `services/knowledge/app/models/retrieval.py`, `services/knowledge/app/adapters/chroma.py` | `knowledge.md` |
| Orchestrator models | Not implemented yet | Stub service only | Add when code exists |
| Frontend TypeScript models | Implemented | `frontend/src/entities/*/model/types.ts` | Frontend docs |

## Money And Date Semantics

Financial model money values use Python `Decimal`, are stored in MongoDB as BSON `Decimal128`, and are serialized as JSON strings by API responses. This applies to invoice line amounts, invoice totals, expense amounts, deductible amounts, and financial summary totals.

Financial API payloads accept date-only ISO strings such as `"2026-04-26"`. Repositories store those dates as UTC datetimes so MongoDB range filters and monthly grouping can use indexed fields.

## Company Scope Semantics

Company-scoped records use string ObjectId values in API payloads and responses. Business Service owns `companies`, `partners`, `invoices`, and `expenses`; Agent Service stores optional `company_id` assignments on agents and calls Business for company validation and financial tool operations. Knowledge Base Service owns `documents` and validates `company_id` ownership through Business.

| Data | Scope |
|------|-------|
| `companies` | `user_id` |
| `partners` | `user_id + company_id` |
| `agents` | `user_id`, optional `company_id` |
| `invoices` | `user_id + company_id`, optional `partner_id` |
| Knowledge `documents` | `user_id + company_id` |
| Uploaded Chroma chunks | `user_{user_id}` collection plus `company_id` metadata |

## Rule

Only document models here once they exist in code. Planned models can be discussed in service architecture docs, but this folder should remain the source of truth for current schemas.
