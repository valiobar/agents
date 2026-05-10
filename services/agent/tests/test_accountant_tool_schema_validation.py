from __future__ import annotations

import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tools.financial.company_tools import ListCompaniesArgs
from app.tools.financial.companybook import SearchCompanyBookArgs
from app.tools.financial.financial_tools import GetFinancialSummaryArgs, QueryExpensesArgs
from app.tools.financial.partner_tools import SearchPartnersArgs


class AccountantToolSchemaValidationTests(unittest.TestCase):
    def test_financial_query_schema_rejects_unknown_fields(self) -> None:
        with self.assertRaises(ValidationError):
            QueryExpensesArgs.model_validate({"limit": 5, "unknown": "value"})

    def test_financial_summary_schema_rejects_unknown_fields(self) -> None:
        with self.assertRaises(ValidationError):
            GetFinancialSummaryArgs.model_validate({"include_expenses": True, "unknown": "value"})

    def test_partner_search_schema_rejects_unknown_fields(self) -> None:
        with self.assertRaises(ValidationError):
            SearchPartnersArgs.model_validate({"query": "acme", "surprise": "value"})

    def test_company_search_schema_rejects_unknown_fields(self) -> None:
        with self.assertRaises(ValidationError):
            ListCompaniesArgs.model_validate({"query": "acme", "extra_field": "value"})

    def test_companybook_schema_rejects_unknown_fields(self) -> None:
        with self.assertRaises(ValidationError):
            SearchCompanyBookArgs.model_validate({"name": "acme", "unexpected": True})


if __name__ == "__main__":
    unittest.main()
