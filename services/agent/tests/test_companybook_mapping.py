from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.financial.companybook import CompanyBookCompanyDetail, CompanyBookPartnerMappingError


class CompanyBookMappingTests(unittest.TestCase):
    def test_to_partner_create_maps_complete_company_detail(self) -> None:
        detail = CompanyBookCompanyDetail.model_validate(
            {
                "uic": "123456789",
                "name": "Example OOD",
                "seat": {
                    "country": "Bulgaria",
                    "settlement": "Sofia",
                    "address": "1 Test Street",
                },
                "contacts": {"email": "office@example.bg", "phone": "+359888000000"},
                "managers": ["Ivan Ivanov"],
            }
        )

        partner = detail.to_partner_create(company_id="company-1", kind="client")

        self.assertEqual(partner.company_id, "company-1")
        self.assertEqual(partner.registration_number, "123456789")
        self.assertEqual(partner.vat_number, "BG123456789")
        self.assertEqual(partner.city, "Sofia")
        self.assertEqual(partner.accountable_person, "Ivan Ivanov")

    def test_to_partner_create_maps_companybook_nested_company_name(self) -> None:
        detail = CompanyBookCompanyDetail.from_api(
            {
                "company": {
                    "uic": "202317880",
                    "companyName": {"name": "РОБО ЛАБ"},
                    "seat": {
                        "country": "БЪЛГАРИЯ",
                        "district": "София (столица)",
                        "municipality": "Столична",
                        "settlement": "гр. София",
                        "street": "бул. АЛ.СТАМБОЛИЙСКИ",
                        "streetNumber": "84-86",
                    },
                    "managers": [{"name": "ГЕОРГИ ДИМИТРОВ ХЪРКОВ"}],
                }
            }
        )

        partner = detail.to_partner_create(company_id="company-1", kind="client")

        self.assertEqual(partner.name, "РОБО ЛАБ")
        self.assertEqual(partner.registration_number, "202317880")
        self.assertEqual(partner.city, "гр. София")
        self.assertEqual(partner.country, "БЪЛГАРИЯ")
        self.assertEqual(partner.address, "бул. АЛ.СТАМБОЛИЙСКИ, 84-86")
        self.assertEqual(partner.accountable_person, "ГЕОРГИ ДИМИТРОВ ХЪРКОВ")

    def test_to_partner_create_reports_missing_required_fields_with_draft(self) -> None:
        detail = CompanyBookCompanyDetail.model_validate(
            {
                "uic": "123456789",
                "name": "Example OOD",
                "seat": {"country": "Bulgaria"},
                "contacts": {},
            }
        )

        with self.assertRaises(CompanyBookPartnerMappingError) as exc:
            detail.to_partner_create(company_id="company-1", kind="client")

        self.assertEqual(
            exc.exception.missing_fields,
            ["city", "address", "accountable_person"],
        )
        self.assertEqual(exc.exception.partner_draft["registration_number"], "123456789")
        self.assertEqual(exc.exception.partner_draft["company_id"], "company-1")


if __name__ == "__main__":
    unittest.main()
