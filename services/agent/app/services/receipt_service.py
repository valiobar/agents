from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, UploadFile, status

from app.clients.business import BusinessClient, BusinessClientError
from app.clients.knowledge import KnowledgeClient, KnowledgeClientError
from app.models.document_intake import (
    ReceiptExpenseReviewResponse,
    SupplierInvoiceExpenseReviewResponse,
)
from app.models.financial import ExpenseCreate
from app.models.financial.receipt import ConfirmExtractedExpenseRequest, ConfirmExtractedExpenseResponse, ExpenseDraftResponse
from app.repositories.agent_repo import AgentRepository
from app.services.document_intake_service import require_company_scoped_agent

if TYPE_CHECKING:
    from app.services.document_intake_service import DocumentIntakeService


class ReceiptService:
    def __init__(
        self,
        agent_repo: AgentRepository,
        knowledge_client: KnowledgeClient,
        business_client: BusinessClient,
        document_intake_service: DocumentIntakeService | None = None,
    ) -> None:
        self.agent_repo = agent_repo
        self.knowledge_client = knowledge_client
        self.business_client = business_client
        self.document_intake_service = document_intake_service

    async def _require_company_scoped_agent(self, user_id: str, agent_id: str) -> str:
        return await require_company_scoped_agent(
            user_id=user_id,
            agent_id=agent_id,
            agent_repo=self.agent_repo,
            business_client=self.business_client,
            workflow_name="Receipt workflow",
        )

    async def _create_legacy_draft(
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

    async def create_draft(
        self,
        *,
        user_id: str,
        agent_id: str,
        file: UploadFile,
        source_document_type: str,
    ) -> ExpenseDraftResponse:
        if self.document_intake_service is None or source_document_type != "receipt":
            return await self._create_legacy_draft(
                user_id=user_id,
                agent_id=agent_id,
                file=file,
                source_document_type=source_document_type,
            )

        intake_response = await self.document_intake_service.create_intake(
            user_id=user_id,
            agent_id=agent_id,
            file=file,
            requested_type=source_document_type,
        )
        if isinstance(
            intake_response,
            ReceiptExpenseReviewResponse | SupplierInvoiceExpenseReviewResponse,
        ):
            return ExpenseDraftResponse(
                document=intake_response.document,
                draft=intake_response.draft,
                extracted_text=intake_response.extracted_text,
                provider=intake_response.provider,
                model=intake_response.model,
                extracted_at=intake_response.extracted_at,
            )

        await file.seek(0)
        return await self._create_legacy_draft(
            user_id=user_id,
            agent_id=agent_id,
            file=file,
            source_document_type=source_document_type,
        )

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

