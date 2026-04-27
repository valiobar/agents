from __future__ import annotations

import argparse
import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

USER_SCOPED_COLLECTIONS = (
    "conversations",
    "agents",
    "invoices",
    "expenses",
    "documents",
    "partners",
    "companies",
)


@dataclass
class ResetSummary:
    user_id: str
    deleted_counts: dict[str, int] = field(default_factory=dict)
    seeded_company_id: str | None = None
    dry_run: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Destructively reset user-scoped test data for company-scope rollout. "
            "This is an opt-in non-production utility and is never run by service startup."
        )
    )
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument(
        "--user-id",
        action="append",
        dest="user_ids",
        help="User id to reset. Repeat the flag to reset multiple users.",
    )
    scope.add_argument(
        "--all-users",
        action="store_true",
        help="Reset all users found in the users collection.",
    )
    parser.add_argument(
        "--no-seed-default-company",
        action="store_true",
        help="Do not create a fresh Default Company after deleting the user's data.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts that would be deleted without deleting or seeding data.",
    )
    parser.add_argument(
        "--confirm-destroy-test-data",
        action="store_true",
        help="Required for non-dry runs. Confirms this destructive test-data reset.",
    )
    return parser.parse_args()


async def resolve_user_ids(db: AsyncIOMotorDatabase, args: argparse.Namespace) -> list[str]:
    if args.all_users:
        cursor = db["users"].find({}, {"_id": 1})
        return [str(user["_id"]) async for user in cursor]

    user_ids = args.user_ids or []
    invalid_ids = [user_id for user_id in user_ids if not ObjectId.is_valid(user_id)]
    if invalid_ids:
        raise ValueError(f"Invalid ObjectId user ids: {', '.join(invalid_ids)}")

    return user_ids


async def _delete_or_count(
    db: AsyncIOMotorDatabase,
    collection_name: str,
    query: dict[str, Any],
    *,
    dry_run: bool,
) -> int:
    collection = db[collection_name]
    if dry_run:
        return await collection.count_documents(query)

    result = await collection.delete_many(query)
    return result.deleted_count


async def seed_default_company(db: AsyncIOMotorDatabase, user_id: str) -> str:
    now = datetime.now(timezone.utc)
    result = await db["companies"].insert_one(
        {
            "user_id": user_id,
            "name": "Default Company",
            "registration_number": f"seed-{user_id}",
            "vat_number": None,
            "city": "Unknown",
            "country": "Bulgaria",
            "address": "Unknown",
            "accountable_person": "Unknown",
            "email": None,
            "phone": None,
            "logo_data_url": None,
            "is_default": True,
            "created_at": now,
            "updated_at": now,
        }
    )
    return str(result.inserted_id)


async def reset_user_data(
    db: AsyncIOMotorDatabase,
    user_id: str,
    *,
    seed_company: bool = True,
    dry_run: bool = False,
) -> ResetSummary:
    summary = ResetSummary(user_id=user_id, dry_run=dry_run)

    for collection_name in USER_SCOPED_COLLECTIONS:
        summary.deleted_counts[collection_name] = await _delete_or_count(
            db,
            collection_name,
            {"user_id": user_id},
            dry_run=dry_run,
        )

    counter_prefix = f"invoice:{re.escape(user_id)}:"
    summary.deleted_counts["counters"] = await _delete_or_count(
        db,
        "counters",
        {"_id": {"$regex": f"^{counter_prefix}"}},
        dry_run=dry_run,
    )

    if seed_company and not dry_run:
        summary.seeded_company_id = await seed_default_company(db, user_id)

    return summary


def print_summary(summary: ResetSummary) -> None:
    mode = "DRY RUN" if summary.dry_run else "RESET"
    print(f"{mode} user_id={summary.user_id}")
    for collection_name, deleted_count in summary.deleted_counts.items():
        print(f"  {collection_name}: {deleted_count}")
    if summary.seeded_company_id:
        print(f"  seeded_company_id: {summary.seeded_company_id}")


async def main() -> None:
    args = parse_args()
    if not args.dry_run and not args.confirm_destroy_test_data:
        raise SystemExit("Refusing to delete data without --confirm-destroy-test-data.")

    client = AsyncIOMotorClient(settings.mongodb_url)
    try:
        db = client[settings.db_name]
        user_ids = await resolve_user_ids(db, args)
        if not user_ids:
            print("No users matched the requested reset scope.")
            return

        for user_id in user_ids:
            summary = await reset_user_data(
                db,
                user_id,
                seed_company=not args.no_seed_default_company,
                dry_run=args.dry_run,
            )
            print_summary(summary)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
