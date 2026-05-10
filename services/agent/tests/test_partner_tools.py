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
from app.models.financial.partner import PartnerListResponse, PartnerResponse
from app.tools.financial import build_partner_tools
from app.tools.financial.operations import build_partner_tools as build_partner_tools_ops
from app.tools.financial.partner_tools import build_partner_tools as build_partner_tools_split


def _partner(registration_number: str = "123456789") -> PartnerResponse:
    now = datetime.now(UTC)
    return PartnerResponse(
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
        self.existing: list[PartnerResponse] = []
        self.last_list_offset: int | None = None
        self.last_list_limit: int | None = None

    async def list_partners(
        self,
        user_id: str,
        company_id: str,
        kind: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> PartnerListResponse:
        await sleep(0)
        self.last_list_offset = offset
        self.last_list_limit = limit
        window = self.existing[offset : offset + limit]
        return PartnerListResponse(
            total_count=len(self.existing),
            returned_count=len(window),
            offset=offset,
            limit=limit,
            truncated=offset + len(window) < len(self.existing),
            next_offset=offset + len(window) if offset + len(window) < len(self.existing) else None,
            items=window,
        )

    async def create_partner(self, user_id: str, payload: object) -> PartnerResponse:
        await sleep(0)
        self.create_calls += 1
        self.existing = [_partner(getattr(payload, "registration_number"))]
        raise BusinessClientError("Partner already exists.", status_code=409)


class PartnerToolTests(unittest.IsolatedAsyncioTestCase):
    def test_partner_builder_exports_resolve_to_split_module(self) -> None:
        self.assertIs(build_partner_tools, build_partner_tools_split)
        self.assertIs(build_partner_tools, build_partner_tools_ops)

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

    async def test_search_partners_returns_envelope_and_forwards_offset(self) -> None:
        business_client = FakeBusinessClient()
        business_client.existing = [_partner("111111111"), _partner("222222222"), _partner("333333333")]
        context = SimpleNamespace(business_client=business_client)
        search_tool = next(
            tool for tool in build_partner_tools("user-1", "company-1", context) if tool.name == "search_partners"
        )

        result = await search_tool.ainvoke({"query": "example", "limit": 1, "offset": 1})
        payload = json.loads(result)

        self.assertEqual(payload["total_count"], 3)
        self.assertEqual(payload["returned_count"], 1)
        self.assertEqual(payload["offset"], 1)
        self.assertTrue(payload["truncated"])
        self.assertEqual(payload["next_offset"], 2)
        self.assertEqual(payload["items"][0]["registration_number"], "222222222")
        self.assertEqual(business_client.last_list_limit, 1)
        self.assertEqual(business_client.last_list_offset, 1)


if __name__ == "__main__":
    unittest.main()
