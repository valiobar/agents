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
from app.models.financial.companybook import CompanyBookCompanyDetail
from app.models.financial.companybook import CompanyBookSearchResponse
from app.models.financial.partner import PartnerListResponse, PartnerResponse
from app.tools.companybook import build_companybook_tools
from app.tools.companybook import (
    ImportCompanyBookPartnerArgs,
    _import_companybook_partner_for_company,
)


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
    def __init__(self, existing: list[PartnerResponse] | None = None, duplicate: bool = False) -> None:
        self.existing = existing or []
        self.duplicate = duplicate
        self.create_calls = 0

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
        if self.duplicate:
            self.existing = [_partner(getattr(payload, "registration_number"))]
            raise BusinessClientError("Partner already exists.", status_code=409)
        return _partner(getattr(payload, "registration_number"))


class FakeCompanyBookService:
    async def search_companies(
        self,
        name: str,
        limit: int,
        active_only: bool = True,
    ) -> CompanyBookSearchResponse:
        await sleep(0)
        self.last_search_name = name
        self.last_search_limit = limit
        self.last_search_active_only = active_only
        return CompanyBookSearchResponse.model_validate(
            {
                "results": [
                    {"uic": "111111111", "name": "Alpha OOD"},
                    {"uic": "222222222", "name": "Beta OOD"},
                    {"uic": "333333333", "name": "Gamma OOD"},
                ],
                "total": 3,
            }
        )

    async def get_company(self, uic: str) -> CompanyBookCompanyDetail:
        await sleep(0)
        return CompanyBookCompanyDetail.model_validate(
            {
                "uic": uic,
                "name": "Example OOD",
                "seat": {"country": "Bulgaria", "settlement": "Sofia", "address": "1 Test Street"},
                "managers": ["Ivan Ivanov"],
            }
        )


class CompanyBookToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_companybook_returns_list_envelope_shape(self) -> None:
        context = SimpleNamespace(
            business_client=FakeBusinessClient(existing=[]),
            companybook_service=FakeCompanyBookService(),
        )
        search_tool = next(
            tool
            for tool in build_companybook_tools("user-1", "company-1", context)
            if tool.name == "search_companybook_companies"
        )

        result = await search_tool.ainvoke({"name": "alpha", "limit": 2, "offset": 1, "active_only": True})
        payload = json.loads(result)

        self.assertEqual(payload["total_count"], 3)
        self.assertEqual(payload["returned_count"], 2)
        self.assertEqual(payload["offset"], 1)
        self.assertEqual(payload["limit"], 2)
        self.assertTrue(payload["truncated"])
        self.assertEqual(payload["next_offset"], 3)
        self.assertEqual(len(payload["items"]), 2)
        self.assertEqual(payload["source"], "companybook")
        self.assertEqual(context.companybook_service.last_search_name, "alpha")
        self.assertEqual(context.companybook_service.last_search_limit, 3)

    async def test_import_reuses_existing_partner_by_exact_uic(self) -> None:
        business_client = FakeBusinessClient(existing=[_partner()])
        context = SimpleNamespace(
            business_client=business_client,
            companybook_service=FakeCompanyBookService(),
        )

        result = await _import_companybook_partner_for_company(
            user_id="user-1",
            company_id="company-1",
            args=ImportCompanyBookPartnerArgs(uic="123456789"),
            context=context,
        )

        self.assertEqual(json.loads(result)["id"], "partner-1")
        self.assertEqual(business_client.create_calls, 0)

    async def test_import_resolves_partner_after_duplicate_key_race(self) -> None:
        business_client = FakeBusinessClient(duplicate=True)
        context = SimpleNamespace(
            business_client=business_client,
            companybook_service=FakeCompanyBookService(),
        )

        result = await _import_companybook_partner_for_company(
            user_id="user-1",
            company_id="company-1",
            args=ImportCompanyBookPartnerArgs(uic="123456789"),
            context=context,
        )

        self.assertEqual(json.loads(result)["registration_number"], "123456789")
        self.assertEqual(business_client.create_calls, 1)


if __name__ == "__main__":
    unittest.main()
