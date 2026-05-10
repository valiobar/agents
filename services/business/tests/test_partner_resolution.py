from __future__ import annotations

import sys
import unittest
from asyncio import sleep
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.partner.models import PartnerInDB, PartnerResolveRequest
from app.partner.repositories.partner_repo import PartnerRepository
from app.partner.services.partner_service import PartnerService


def _partner(partner_id: str, name: str, registration_number: str) -> PartnerInDB:
    now = datetime.now(timezone.utc)
    return PartnerInDB(
        id=partner_id,
        user_id="user-1",
        company_id="company-1",
        kind="supplier",
        name=name,
        registration_number=registration_number,
        vat_number=f"BG{registration_number}",
        city="Sofia",
        country="Bulgaria",
        address="1 Test Street",
        accountable_person="Ivan Ivanov",
        created_at=now,
        updated_at=now,
    )


class _FakeCompanyService:
    async def require_company(self, user_id: str, company_id: str) -> object:
        await sleep(0)
        return object()


class _FakeInvoiceRepo:
    async def count_by_partner(self, user_id: str, company_id: str, partner_id: str) -> int:
        await sleep(0)
        return 0


class _FakePartnerRepo:
    async def resolve_candidates(self, user_id: str, payload: PartnerResolveRequest) -> list[PartnerInDB]:
        await sleep(0)
        return [
            _partner(partner_id="partner-2", name="Vendor Group", registration_number="999999999"),
            _partner(partner_id="partner-1", name="Vendor Ltd", registration_number="123456789"),
        ]


class _FakeDb:
    def __getitem__(self, _name: str) -> object:
        return object()


class PartnerResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_resolve_partner_returns_ranked_match_reasons(self) -> None:
        service = PartnerService(_FakePartnerRepo(), _FakeCompanyService(), _FakeInvoiceRepo())
        payload = PartnerResolveRequest(
            company_id="company-1",
            registration_number="123456789",
            name="Vendor Ltd",
            limit=5,
        )

        response = await service.resolve_partner("user-1", payload)

        self.assertEqual(response.candidates[0].partner.id, "partner-1")
        self.assertEqual(response.candidates[0].match_type, "registration_number_exact")
        self.assertGreater(response.candidates[0].score, response.candidates[1].score)
        self.assertTrue(
            any("registration number" in reason.lower() for reason in response.candidates[0].match_reasons)
        )

    def test_partner_repository_normalizes_search_fields_for_exact_prefix_lookup(self) -> None:
        repo = PartnerRepository(_FakeDb())  # type: ignore[arg-type]

        fields = repo._build_search_fields(
            name="  Vendor   Ltd  ",
            registration_number="12 34-56",
            vat_number="bg 12 34-56",
        )
        self.assertEqual(fields["name_normalized"], "vendor ltd")
        self.assertEqual(fields["registration_number_normalized"], "123456")
        self.assertEqual(fields["vat_number_normalized"], "BG123456")
        self.assertEqual(fields["search_text"], "vendor ltd 123456 bg123456")

        clauses = repo._build_resolve_clauses(
            PartnerResolveRequest(company_id="company-1", registration_number="12 34-56", name="Vendor")
        )
        self.assertIn({"registration_number_normalized": "123456"}, clauses)
        self.assertIn({"name_normalized": "vendor"}, clauses)
        self.assertIn({"name_normalized": {"$regex": "^vendor"}}, clauses)


if __name__ == "__main__":
    unittest.main()
