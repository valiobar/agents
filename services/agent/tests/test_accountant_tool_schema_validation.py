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
from app.runtime.accountant import AccountantAgent
from app.models.shared.agent import AgentConfig, AgentInDB
from datetime import UTC, datetime


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

    def test_accountant_prompt_guides_inventory_backed_invoice_workflow(self) -> None:
        now = datetime.now(UTC)
        agent = AgentInDB(
            id="agent-1",
            user_id="user-1",
            name="Accountant",
            description=None,
            agent_type="accountant",
            company_id="company-1",
            config=AgentConfig(provider="openai", model="gpt-4.1-mini", temperature=0.1),
            created_at=now,
            updated_at=now,
        )
        runtime = AccountantAgent(agent, llm=object(), user_id="user-1", tool_context=object())
        prompt = runtime.get_system_prompt()

        self.assertIn("do not call create_invoice directly as the first step", prompt)
        self.assertIn("reviewed sales invoice inventory workflow can be started", prompt)
        self.assertIn("Only the frontend can explicitly start that workflow", prompt)


if __name__ == "__main__":
    unittest.main()
