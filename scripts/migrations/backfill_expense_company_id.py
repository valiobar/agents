from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient


def _legacy_company_filter() -> dict[str, Any]:
    return {"$or": [{"company_id": {"$exists": False}}, {"company_id": None}]}


async def _run_backfill(db, *, dry_run: bool) -> dict[str, Any]:
    expenses = db["expenses"]
    companies = db["companies"]

    users = await expenses.distinct("user_id", _legacy_company_filter())
    users_with_legacy_expenses = [user_id for user_id in users if isinstance(user_id, str) and user_id]

    assigned_total = 0
    ambiguous: list[dict[str, Any]] = []

    for user_id in users_with_legacy_expenses:
        legacy_filter = {"user_id": user_id, **_legacy_company_filter()}
        legacy_count = await expenses.count_documents(legacy_filter)
        if legacy_count == 0:
            continue

        company_docs = await companies.find({"user_id": user_id}, {"_id": 1}).to_list(None)
        if len(company_docs) == 1:
            company_id = str(company_docs[0]["_id"])
            if not dry_run:
                result = await expenses.update_many(legacy_filter, {"$set": {"company_id": company_id}})
                assigned_total += result.modified_count
            else:
                assigned_total += legacy_count
            continue

        ambiguous.append(
            {
                "user_id": user_id,
                "legacy_expense_count": legacy_count,
                "company_count": len(company_docs),
                "reason": "company_id not auto-assigned because company count is not exactly one",
            }
        )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "dry_run": dry_run,
        "users_with_legacy_expenses": len(users_with_legacy_expenses),
        "assigned_expense_count": assigned_total,
        "ambiguous_users": ambiguous,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill missing expense company_id values.")
    parser.add_argument(
        "--report-path",
        default="scripts/migrations/reports/backfill_expense_company_id_report.json",
        help="Where to write the ambiguity report JSON.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview report without updating expenses.",
    )
    args = parser.parse_args()

    mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017/agents")
    db_name = os.getenv("MONGODB_DB_NAME", "agents")

    client = AsyncIOMotorClient(mongo_url)
    try:
        report = await _run_backfill(client[db_name], dry_run=args.dry_run)
    finally:
        client.close()

    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Backfill report written to {report_path}")
    print(f"Assigned expense rows: {report['assigned_expense_count']}")
    print(f"Ambiguous users: {len(report['ambiguous_users'])}")


if __name__ == "__main__":
    asyncio.run(main())
