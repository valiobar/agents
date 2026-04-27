from __future__ import annotations

import argparse
import asyncio
import base64
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure

from app.config import settings
from app.repositories.financial_utils import date_to_datetime_range, decimal_to_bson, quantize_money, quantize_rate


DEFAULT_EMAIL = "demo@example.com"
DEFAULT_PASSWORD = "Password123!"
DEFAULT_NAME = "Demo User"
DEFAULT_AUTH_URL = "http://auth:8001"


@dataclass
class SeedSummary:
    user_id: str
    email: str | None = None
    created_user: bool = False
    companies: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    partners: list[str] = field(default_factory=list)
    invoices: list[str] = field(default_factory=list)
    expenses: list[str] = field(default_factory=list)
    conversations: list[str] = field(default_factory=list)
    dry_run: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Seed fresh local/test data after MongoDB collections have been dropped. "
            "This script only creates data; it never deletes existing records."
        )
    )
    parser.add_argument(
        "--user-id",
        help=(
            "Existing user ObjectId to seed Agent Service data for. "
            "When omitted, the script registers a demo user through the Auth service."
        ),
    )
    parser.add_argument("--email", default=DEFAULT_EMAIL, help=f"Demo user email. Default: {DEFAULT_EMAIL}")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help=f"Demo user password. Default: {DEFAULT_PASSWORD}")
    parser.add_argument("--name", default=DEFAULT_NAME, help=f"Demo user display name. Default: {DEFAULT_NAME}")
    parser.add_argument("--auth-url", default=DEFAULT_AUTH_URL, help=f"Auth service URL. Default: {DEFAULT_AUTH_URL}")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without writing to MongoDB or calling Auth.",
    )
    return parser.parse_args()


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db["users"].create_index("email", unique=True)

    await db["agents"].create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db["agents"].create_index([("user_id", ASCENDING), ("name", ASCENDING)])
    await db["agents"].create_index([("user_id", ASCENDING), ("company_id", ASCENDING), ("created_at", DESCENDING)])

    await db["conversations"].create_index([("user_id", ASCENDING), ("agent_id", ASCENDING), ("updated_at", DESCENDING)])
    await db["conversations"].create_index(
        [("user_id", ASCENDING), ("agent_id", ASCENDING), ("company_id", ASCENDING), ("updated_at", DESCENDING)]
    )
    await db["conversations"].create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])

    await db["invoices"].create_index([("user_id", ASCENDING), ("status", ASCENDING), ("issue_date", DESCENDING)])
    await db["invoices"].create_index([("user_id", ASCENDING), ("issue_date", DESCENDING)])
    await db["invoices"].create_index([("user_id", ASCENDING), ("counterparty", ASCENDING)])
    await db["invoices"].create_index([("user_id", ASCENDING), ("items.category", ASCENDING)])
    try:
        await db["invoices"].drop_index("user_id_1_invoice_number_1")
    except OperationFailure:
        pass
    await db["invoices"].create_index([("user_id", ASCENDING), ("company_id", ASCENDING), ("issue_date", DESCENDING)])
    await db["invoices"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("status", ASCENDING), ("issue_date", DESCENDING)]
    )
    await db["invoices"].create_index([("user_id", ASCENDING), ("company_id", ASCENDING), ("partner_id", ASCENDING)])
    await db["invoices"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("invoice_number", ASCENDING)],
        unique=True,
    )

    await db["expenses"].create_index([("user_id", ASCENDING), ("category", ASCENDING), ("expense_date", DESCENDING)])
    await db["expenses"].create_index([("user_id", ASCENDING), ("expense_date", DESCENDING)])
    await db["expenses"].create_index([("user_id", ASCENDING), ("counterparty", ASCENDING)])
    await db["expenses"].create_index([("user_id", ASCENDING), ("deductible", ASCENDING)])

    await db["companies"].create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db["companies"].create_index([("user_id", ASCENDING), ("registration_number", ASCENDING)], unique=True)
    await db["companies"].create_index([("user_id", ASCENDING), ("is_default", ASCENDING)])

    await db["partners"].create_index([("user_id", ASCENDING), ("company_id", ASCENDING), ("name", ASCENDING)])
    await db["partners"].create_index([("user_id", ASCENDING), ("company_id", ASCENDING), ("kind", ASCENDING)])
    await db["partners"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("registration_number", ASCENDING)],
        unique=True,
    )


def decode_jwt_sub(token: str) -> str:
    try:
        payload = token.split(".")[1]
        padding = "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(f"{payload}{padding}")
        sub = json.loads(decoded)["sub"]
    except (IndexError, KeyError, ValueError) as exc:
        raise ValueError("Auth service returned a token without a valid subject") from exc
    if not isinstance(sub, str) or not ObjectId.is_valid(sub):
        raise ValueError("Auth service returned an invalid user id")
    return sub


async def register_demo_user(
    db: AsyncIOMotorDatabase,
    *,
    auth_url: str,
    email: str,
    password: str,
    name: str,
) -> tuple[str, bool]:
    existing = await db["users"].find_one({"email": email}, {"_id": 1})
    if existing is not None:
        return str(existing["_id"]), False

    async with httpx.AsyncClient(base_url=auth_url, timeout=10.0) as client:
        response = await client.post(
            "/auth/register",
            json={"email": email, "password": password, "name": name},
        )

    if response.status_code == 409:
        existing = await db["users"].find_one({"email": email}, {"_id": 1})
        if existing is not None:
            return str(existing["_id"]), False

    response.raise_for_status()
    return decode_jwt_sub(response.json()["access_token"]), True


def party_snapshot(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": doc["name"],
        "registration_number": doc["registration_number"],
        "vat_number": doc.get("vat_number"),
        "city": doc["city"],
        "country": doc["country"],
        "address": doc["address"],
        "accountable_person": doc["accountable_person"],
        "email": doc.get("email"),
        "phone": doc.get("phone"),
        "logo_data_url": doc.get("logo_data_url"),
    }


def invoice_item(
    *,
    description: str,
    quantity: str,
    unit_price: str,
    vat_rate: str = "0.20",
    category: str,
) -> dict[str, Any]:
    qty = Decimal(quantity)
    price = Decimal(unit_price)
    rate = quantize_rate(Decimal(vat_rate))
    subtotal = quantize_money(qty * price)
    vat_amount = quantize_money(subtotal * rate)
    total = quantize_money(subtotal + vat_amount)
    return {
        "description": description,
        "quantity": qty,
        "unit_label": "бр.",
        "unit_price": price,
        "vat_rate": rate,
        "category": category,
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "total": total,
    }


def invoice_doc(
    *,
    user_id: str,
    company: dict[str, Any],
    partner: dict[str, Any],
    invoice_number: str,
    issue_date: date,
    due_date: date,
    status: str,
    items: list[dict[str, Any]],
    notes: str | None = None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    subtotal = quantize_money(sum((item["subtotal"] for item in items), Decimal("0")))
    vat_total = quantize_money(sum((item["vat_amount"] for item in items), Decimal("0")))
    total = quantize_money(sum((item["total"] for item in items), Decimal("0")))
    timestamp = created_at or datetime.now(timezone.utc)
    return {
        "user_id": user_id,
        "company_id": str(company["_id"]),
        "partner_id": str(partner["_id"]),
        "invoice_number": invoice_number,
        "counterparty": partner["name"],
        "supplier_snapshot": party_snapshot(company),
        "recipient_snapshot": party_snapshot(partner),
        "issue_date": date_to_datetime_range(issue_date),
        "tax_event_date": date_to_datetime_range(issue_date),
        "due_date": date_to_datetime_range(due_date),
        "place_of_supply": "Bulgaria",
        "payment_method": "bank_transfer",
        "bank_name": "Demo Bank",
        "bank_bic": "DEMOBGSF",
        "bank_iban": "BG80DEMO00000000000000",
        "amount_in_words": None,
        "currency": "EUR",
        "items": items,
        "subtotal": subtotal,
        "vat_total": vat_total,
        "total": total,
        "status": status,
        "vat_reason": None,
        "recipient_name": partner["accountable_person"],
        "compiler_name": company["accountable_person"],
        "original_label": "ОРИГИНАЛ",
        "notes": notes,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def expense_doc(
    *,
    user_id: str,
    counterparty: str,
    expense_date: date,
    amount: str,
    category: str,
    description: str,
    deductible_rate: str = "1.0",
    created_at: datetime | None = None,
) -> dict[str, Any]:
    expense_amount = quantize_money(Decimal(amount))
    rate = quantize_rate(Decimal(deductible_rate))
    timestamp = created_at or datetime.now(timezone.utc)
    return {
        "user_id": user_id,
        "counterparty": counterparty,
        "expense_date": date_to_datetime_range(expense_date),
        "amount": expense_amount,
        "currency": "EUR",
        "category": category,
        "description": description,
        "deductible": True,
        "deductible_rate": rate,
        "deductible_amount": quantize_money(expense_amount * rate),
        "source_document_type": None,
        "source_document_id": None,
        "items": None,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


async def seed_agent_data(db: AsyncIOMotorDatabase, user_id: str) -> SeedSummary:
    now = datetime.now(timezone.utc)
    company_id = ObjectId()
    secondary_company_id = ObjectId()
    client_id = ObjectId()
    supplier_id = ObjectId()
    agent_id = ObjectId()

    companies = [
        {
            "_id": company_id,
            "user_id": user_id,
            "name": "Demo Accounting Ltd.",
            "registration_number": "DEMO-1001",
            "vat_number": "BGDEMO1001",
            "city": "Sofia",
            "country": "Bulgaria",
            "address": "1 Demo Street",
            "accountable_person": "Demo Manager",
            "email": "accounting@example.com",
            "phone": "+359888000001",
            "logo_data_url": None,
            "is_default": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": secondary_company_id,
            "user_id": user_id,
            "name": "Demo Consulting EOOD",
            "registration_number": "DEMO-1002",
            "vat_number": None,
            "city": "Plovdiv",
            "country": "Bulgaria",
            "address": "22 Test Boulevard",
            "accountable_person": "Consulting Manager",
            "email": "consulting@example.com",
            "phone": None,
            "logo_data_url": None,
            "is_default": False,
            "created_at": now,
            "updated_at": now,
        },
    ]
    partners = [
        {
            "_id": client_id,
            "user_id": user_id,
            "company_id": str(company_id),
            "kind": "client",
            "name": "Acme Client Ltd.",
            "registration_number": "CLIENT-2001",
            "vat_number": "BGCLIENT2001",
            "city": "Varna",
            "country": "Bulgaria",
            "address": "5 Client Avenue",
            "accountable_person": "Client Director",
            "email": "client@example.com",
            "phone": "+359888000002",
            "notes": "Primary demo client.",
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": supplier_id,
            "user_id": user_id,
            "company_id": str(company_id),
            "kind": "supplier",
            "name": "Office Supplier Ltd.",
            "registration_number": "SUPPLIER-3001",
            "vat_number": "BGSUPPLIER3001",
            "city": "Sofia",
            "country": "Bulgaria",
            "address": "9 Supplier Road",
            "accountable_person": "Supplier Manager",
            "email": "supplier@example.com",
            "phone": "+359888000003",
            "notes": "Demo office supplier.",
            "created_at": now,
            "updated_at": now,
        },
    ]
    agents = [
        {
            "_id": agent_id,
            "user_id": user_id,
            "name": "Demo Accountant",
            "description": "Seeded accountant agent for testing company-scoped finance workflows.",
            "agent_type": "accountant",
            "company_id": str(company_id),
            "config": {
                "provider": settings.default_provider,
                "model": None,
                "temperature": settings.default_temperature,
                "system_prompt_override": None,
            },
            "created_at": now,
            "updated_at": now,
        }
    ]
    invoices = [
        invoice_doc(
            user_id=user_id,
            company=companies[0],
            partner=partners[0],
            invoice_number="INV-2026-00001",
            issue_date=date(2026, 4, 1),
            due_date=date(2026, 4, 15),
            status="sent",
            items=[
                invoice_item(
                    description="Monthly accounting advisory",
                    quantity="1",
                    unit_price="1200.00",
                    category="professional_services",
                )
            ],
            notes="Seeded sent invoice.",
            created_at=now,
        ),
        invoice_doc(
            user_id=user_id,
            company=companies[0],
            partner=partners[0],
            invoice_number="INV-2026-00002",
            issue_date=date(2026, 4, 10),
            due_date=date(2026, 4, 24),
            status="paid",
            items=[
                invoice_item(
                    description="VAT return preparation",
                    quantity="1",
                    unit_price="350.00",
                    category="tax",
                ),
                invoice_item(
                    description="Payroll review",
                    quantity="2",
                    unit_price="180.00",
                    category="payroll",
                ),
            ],
            notes="Seeded paid invoice.",
            created_at=now,
        ),
    ]
    expenses = [
        expense_doc(
            user_id=user_id,
            counterparty=partners[1]["name"],
            expense_date=date(2026, 4, 5),
            amount="180.00",
            category="office",
            description="Office supplies for demo accounting company.",
            created_at=now,
        ),
        expense_doc(
            user_id=user_id,
            counterparty="Cloud Software Vendor",
            expense_date=date(2026, 4, 12),
            amount="96.00",
            category="software",
            description="Monthly accounting software subscription.",
            created_at=now,
        ),
    ]
    conversations = [
        {
            "_id": ObjectId(),
            "user_id": user_id,
            "agent_id": str(agent_id),
            "company_id": str(company_id),
            "title": "Seeded finance overview",
            "messages": [
                {
                    "role": "user",
                    "content": "Show me the seeded invoices and expenses for April.",
                    "created_at": now,
                    "metadata": {},
                },
                {
                    "role": "assistant",
                    "content": "I found two invoices and two expenses in the seeded demo data.",
                    "created_at": now,
                    "metadata": {"seeded": True},
                },
            ],
            "created_at": now,
            "updated_at": now,
        }
    ]

    await db["companies"].insert_many(companies)
    await db["partners"].insert_many(partners)
    await db["agents"].insert_many(agents)
    await db["invoices"].insert_many(decimal_to_bson(invoices))
    await db["expenses"].insert_many(decimal_to_bson(expenses))
    await db["conversations"].insert_many(conversations)
    await db["counters"].update_one(
        {"_id": f"invoice:{user_id}:{company_id}:2026"},
        {"$set": {"seq": len(invoices)}},
        upsert=True,
    )

    return SeedSummary(
        user_id=user_id,
        companies=[str(company["_id"]) for company in companies],
        agents=[str(agent["_id"]) for agent in agents],
        partners=[str(partner["_id"]) for partner in partners],
        invoices=[invoice["invoice_number"] for invoice in invoices],
        expenses=[expense["description"] for expense in expenses],
        conversations=[str(conversation["_id"]) for conversation in conversations],
    )


def print_summary(summary: SeedSummary) -> None:
    mode = "DRY RUN" if summary.dry_run else "SEEDED"
    print(f"{mode} user_id={summary.user_id}")
    if summary.email:
        print(f"  email: {summary.email}")
        print(f"  created_user: {summary.created_user}")
    print(f"  companies: {len(summary.companies)} {summary.companies}")
    print(f"  agents: {len(summary.agents)} {summary.agents}")
    print(f"  partners: {len(summary.partners)} {summary.partners}")
    print(f"  invoices: {len(summary.invoices)} {summary.invoices}")
    print(f"  expenses: {len(summary.expenses)}")
    print(f"  conversations: {len(summary.conversations)}")


async def main() -> None:
    args = parse_args()
    if args.user_id and not ObjectId.is_valid(args.user_id):
        raise SystemExit("--user-id must be a valid MongoDB ObjectId.")

    mongo = AsyncIOMotorClient(settings.mongodb_url)
    try:
        db = mongo[settings.db_name]
        user_id = args.user_id
        created_user = False

        if args.dry_run:
            print_summary(
                SeedSummary(
                    user_id=user_id or "<registered demo user id>",
                    email=None if user_id else args.email,
                    created_user=user_id is None,
                    companies=["Demo Accounting Ltd.", "Demo Consulting EOOD"],
                    agents=["Demo Accountant"],
                    partners=["Acme Client Ltd.", "Office Supplier Ltd."],
                    invoices=["INV-2026-00001", "INV-2026-00002"],
                    expenses=["Office supplies", "Cloud software subscription"],
                    conversations=["Seeded finance overview"],
                    dry_run=True,
                )
            )
            return

        await ensure_indexes(db)
        if user_id is None:
            user_id, created_user = await register_demo_user(
                db,
                auth_url=args.auth_url,
                email=args.email,
                password=args.password,
                name=args.name,
            )
        else:
            user = await db["users"].find_one({"_id": ObjectId(user_id)}, {"_id": 1})
            if user is None:
                raise SystemExit(f"User {user_id} does not exist. Omit --user-id to register a demo user.")

        summary = await seed_agent_data(db, user_id)
        summary.email = None if args.user_id else args.email
        summary.created_user = created_user
        print_summary(summary)
    finally:
        mongo.close()


if __name__ == "__main__":
    asyncio.run(main())
