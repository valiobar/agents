from __future__ import annotations

from fastapi import HTTPException, UploadFile, status

from app.clients.business import BusinessClient, BusinessClientError
from app.clients.knowledge import KnowledgeClient, KnowledgeClientError
from app.models.financial import ExpenseCreate
from app.models.receipt import ConfirmExtractedExpenseRequest, ConfirmExtractedExpenseResponse, ExpenseDraftResponse
from app.repositories.agent_repo import AgentRepository


class ReceiptService:
    def __init__(
        self,
        agent_repo: AgentRepository,
        knowledge_client: KnowledgeClient,
        business_client: BusinessClient,
    ) -> None:
        self.agent_repo = agent_repo
        self.knowledge_client = knowledge_client
        self.business_client = business_client

    async def _require_company_scoped_agent(self, user_id: str, agent_id: str) -> str:
        agent = await self.agent_repo.get_by_id(user_id, agent_id)
        if agent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        if not agent.company_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Receipt workflow requires a company-scoped agent",
            )
        try:
            exists = await self.business_client.company_exists(user_id, agent.company_id)
        except BusinessClientError as exc:
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found") from exc
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message) from exc
        if not exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
        return agent.company_id

    async def create_draft(
        self,
        *,
        user_id: str,
        agent_id: str,
        file: UploadFile,
        source_document_type: str,
    ) -> ExpenseDraftResponse:
        company_id = await self._require_company_scoped_agent(user_id, agent_id)

        try:
            return await self.knowledge_client.create_expense_draft(
                user_id=user_id,
                company_id=company_id,
                file=file,
                source_document_type=source_document_type,
            )
        except KnowledgeClientError as exc:
            if exc.status_code and 400 <= exc.status_code < 500:
                raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=exc.message,
            ) from exc

    async def confirm_expense(
        self,
        *,
        user_id: str,
        agent_id: str,
        payload: ConfirmExtractedExpenseRequest,
    ) -> ConfirmExtractedExpenseResponse:
        if not payload.confirmed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Confirmation is required before recording expense",
            )

        company_id = await self._require_company_scoped_agent(user_id, agent_id)
        try:
            partner_result = None
            if payload.source_document_type == "invoice":
                if payload.vendor_partner is None:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Invoice confirmation requires reviewed vendor partner details",
                    )
                partner_result = await self.business_client.find_or_create_supplier_partner(
                    user_id=user_id,
                    company_id=company_id,
                    vendor=payload.vendor_partner,
                )

            expense_payload = ExpenseCreate.model_validate(
                payload.model_dump(exclude={"confirmed", "vendor_partner"})
            )
            expense = await self.business_client.create_expense(user_id, expense_payload)
            return ConfirmExtractedExpenseResponse(expense=expense, vendor_partner=partner_result)
        except BusinessClientError as exc:
            if exc.status_code and 400 <= exc.status_code < 500:
                raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message) from exc

