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
from app.models.companybook import CompanyBookCompanyDetail
from app.models.partner import PartnerInDB
from app.tools.companybook import (
    ImportCompanyBookPartnerArgs,
    _import_companybook_partner_for_company,
)


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
    def __init__(self, existing: list[PartnerInDB] | None = None, duplicate: bool = False) -> None:
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
    ) -> list[PartnerInDB]:
        await sleep(0)
        return self.existing

    async def create_partner(self, user_id: str, payload: object) -> PartnerInDB:
        await sleep(0)
        self.create_calls += 1
        if self.duplicate:
            self.existing = [_partner(getattr(payload, "registration_number"))]
            raise BusinessClientError("Partner already exists.", status_code=409)
        return _partner(getattr(payload, "registration_number"))


class FakeCompanyBookService:
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
