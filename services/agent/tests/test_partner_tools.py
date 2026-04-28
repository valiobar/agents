from __future__ import annotations

import json
import sys
import unittest
from asyncio import sleep
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients.business import BusinessClientError
from app.models.partner import PartnerInDB
from app.tools.financial import build_partner_tools


def _partner(registration_number: str = "123456789") -> PartnerInDB:
    now = datetime.now(UTC)
    return PartnerInDB(
        id="partner-1",
        user_id="user-1",
        company_id="company-1",
        kind="client",
        name="Example OOD",
        registration_number=registration_number,
        vat_number=f"BG{registration_number}",
        city="Sofia",
        country="Bulgaria",
        address="1 Test Street",
        accountable_person="Ivan Ivanov",
        created_at=now,
        updated_at=now,
    )


class FakeBusinessClient:
    def __init__(self) -> None:
        self.create_calls = 0
        self.existing: list[PartnerInDB] = []

    async def list_partners(
        self,
        user_id: str,
        company_id: str,
        kind: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> list[PartnerInDB]:
        await sleep(0)
        return self.existing

    async def create_partner(self, user_id: str, payload: object) -> PartnerInDB:
        await sleep(0)
        self.create_calls += 1
        self.existing = [_partner(getattr(payload, "registration_number"))]
        raise BusinessClientError("Partner already exists.", status_code=409)


class PartnerToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_partner_resolves_existing_partner_after_duplicate_key(self) -> None:
        business_client = FakeBusinessClient()
        context = SimpleNamespace(business_client=business_client)
        create_partner = next(
            tool for tool in build_partner_tools("user-1", "company-1", context) if tool.name == "create_partner"
        )

        result = await create_partner.ainvoke(
            {
                "kind": "client",
                "name": "Example OOD",
                "registration_number": "123456789",
                "vat_number": "BG123456789",
                "city": "Sofia",
                "country": "Bulgaria",
                "address": "1 Test Street",
                "accountable_person": "Ivan Ivanov",
            }
        )

        self.assertEqual(json.loads(result)["id"], "partner-1")
        self.assertEqual(business_client.create_calls, 1)


if __name__ == "__main__":
    unittest.main()
