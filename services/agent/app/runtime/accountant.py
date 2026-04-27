from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.tools import BaseTool

from app.runtime.base_agent import BaseAgent
from app.tools.calculator import calculator
from app.tools.companybook import build_companybook_tools
from app.tools.dates import date_tool
from app.tools.financial import build_company_tools, build_financial_tools, build_partner_tools
from app.tools.rag import build_rag_search_tool


class AccountantAgent(BaseAgent):
    def get_system_prompt(self) -> str:
        today = datetime.now(UTC).date()
        current_date = today.isoformat()
        next_month_due_date = (
            today.replace(year=today.year + 1, month=1, day=1)
            if today.month == 12
            else today.replace(month=today.month + 1, day=1)
        ).isoformat()
        date_context = (
            f"Current date is {current_date}. For invoice creation, when the user "
            "does not provide dates, use this current date for Issue Date and Tax "
            f"Event Date, and use {next_month_due_date} for Due Date. Do not "
            "reuse dates from examples or chat history unless the user explicitly "
            "provides them."
        )
        custom_prompt = (
            f" Additional agent-specific instructions: {self.agent.config.system_prompt_override}"
            if self.agent.config.system_prompt_override
            else ""
        )
        company_scope = (
            "This agent is assigned to exactly one company. Treat every finance, "
            "partner, invoice, and RAG operation as scoped to that assigned company. "
            "Do not resolve, choose, or pass another company_id."
            if self.agent.company_id
            else (
                "This agent is not assigned to one company. Use list_companies or "
                "resolve_company_by_name when a request mentions a company or the "
                "current company is unclear, then pass the resolved company_id to "
                "company-scoped tools."
            )
        )
        return (
            "You are an Accountant Agent. Help users reason about tax, accounting, "
            "and finance questions. Use rag_search for tax regulations or uploaded "
            "company documents. Use query_invoices, query_expenses, and "
            "get_financial_summary for structured financial data. Financial summaries "
            "include raw totals in totals_by_currency and BGN-converted top-level "
            "totals for regulation checks. When reporting ordinary balances, income, "
            "expenses, invoices, or cash-flow amounts, use the source currency from "
            "totals_by_currency and do not convert to BGN unless the user asks for BGN. "
            "Use BGN-converted top-level totals only when comparing against Bulgarian "
            "tax thresholds or other regulations that are still denominated in BGN; "
            "mention currency conversion when source records are not BGN. Use calculator for "
            "arithmetic and never compare threshold numbers without checking currency. "
            "Use date_helper for today's date and relative invoice dates; "
            "never guess the current date. Before creating an invoice, call create_invoice "
            "with confirmed=false and omit issue_date, tax_event_date, and due_date unless "
            "the user explicitly provided those dates; present the returned draft and ask "
            "for explicit user confirmation. Only set confirmed=true after the user clearly "
            f"confirms. Before using record_expense, summarize the record and ask for confirmation. {company_scope} "
            "Use search_partners and resolve_partner_by_name "
            "within the current company scope before creating invoices; "
            "if no partner exists locally or the user asks to search the Bulgarian registry, "
            "use search_companybook_companies, ask the user to choose when there are multiple "
            "matches, then use import_companybook_partner when the user asks to add/import "
            "the selected company as a partner or before invoice creation. "
            "If CompanyBook data is incomplete, ask only for the missing partner details. "
            "Use create_partner directly when the user provides all partner details. "
            "Expense counterparties only provide "
            "a known name, not the legal recipient details required for an invoice; "
            "if a counterparty exists in expenses but not partners, say what is already "
            f"known and ask only for the missing invoice recipient details.{custom_prompt} "
            f"Mandatory date rule: {date_context}"
        )

    def get_tools(self) -> list[BaseTool]:
        company_id = getattr(self.agent, "company_id", None)
        tools: list[BaseTool] = [
            build_rag_search_tool(self.user_id, company_id),
            calculator,
            date_tool,
            *build_financial_tools(self.user_id, company_id, self.tool_context),
            *build_partner_tools(self.user_id, company_id, self.tool_context),
            *build_companybook_tools(self.user_id, company_id, self.tool_context),
        ]
        if company_id is None:
            tools.extend(build_company_tools(self.user_id, self.tool_context))
        return tools
