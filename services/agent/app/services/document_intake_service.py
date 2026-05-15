from __future__ import annotations

from fastapi import HTTPException, UploadFile, status

from app.clients.business import BusinessClient, BusinessClientError
from app.clients.knowledge import KnowledgeClient, KnowledgeClientError
from app.models.document_intake import (
    ConfirmInventoryImportForExpenseRequest,
    ConfirmInventoryImportForExpenseResponse,
    DocumentIntakeResponse,
)
from app.repositories.agent_repo import AgentRepository
from app.services.document_workflows import (
    DocumentIntakeContext,
    DocumentWorkflowValidationError,
    DocumentWorkflowRegistry,
    ReceiptDocumentWorkflow,
    SupplierInvoiceDocumentWorkflow,
    UnknownDocumentWorkflow,
)
from app.services.workflows import require_company_scoped_agent


def create_document_workflow_registry() -> DocumentWorkflowRegistry:
    fallback = UnknownDocumentWorkflow()
    workflows = {
        "receipt": ReceiptDocumentWorkflow(),
        "supplier_invoice": SupplierInvoiceDocumentWorkflow(),
    }
    return DocumentWorkflowRegistry(workflows=workflows, fallback=fallback)


class DocumentIntakeService:
    def __init__(
        self,
        agent_repo: AgentRepository,
        knowledge_client: KnowledgeClient,
        business_client: BusinessClient,
        workflows: DocumentWorkflowRegistry,
    ) -> None:
        self.agent_repo = agent_repo
        self.knowledge_client = knowledge_client
        self.business_client = business_client
        self.workflows = workflows

    async def create_intake(
        self,
        *,
        user_id: str,
        agent_id: str,
        file: UploadFile,
        requested_type: str,
    ) -> DocumentIntakeResponse:
        company_id = await require_company_scoped_agent(
            user_id=user_id,
            agent_id=agent_id,
            agent_repo=self.agent_repo,
            business_client=self.business_client,
            workflow_name="Document intake workflow",
        )
        try:
            extraction = await self.knowledge_client.create_document_intake_draft(
                user_id=user_id,
                company_id=company_id,
                file=file,
                requested_type=requested_type,
            )
        except KnowledgeClientError as exc:
            if exc.status_code and 400 <= exc.status_code < 500:
                raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=exc.message,
            ) from exc

        workflow = self.workflows.resolve(extraction.classification.document_type)
        try:
            return await workflow.create_review(
                DocumentIntakeContext(
                    user_id=user_id,
                    company_id=company_id,
                    extraction=extraction,
                    business_client=self.business_client,
                )
            )
        except DocumentWorkflowValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    async def confirm_supplier_invoice_inventory_import(
        self,
        *,
        user_id: str,
        agent_id: str,
        payload: ConfirmInventoryImportForExpenseRequest,
    ) -> ConfirmInventoryImportForExpenseResponse:
        await require_company_scoped_agent(
            user_id=user_id,
            agent_id=agent_id,
            agent_repo=self.agent_repo,
            business_client=self.business_client,
            workflow_name="Supplier invoice inventory confirmation workflow",
        )
        try:
            inventory_import_result = await self.business_client.confirm_import_preview(
                user_id,
                preview_id=payload.preview_id,
            )
            inventory_import_preview = await self.business_client.get_import_preview(
                user_id,
                preview_id=payload.preview_id,
            )
        except BusinessClientError as exc:
            if exc.status_code and 400 <= exc.status_code < 500:
                raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=exc.message,
            ) from exc

        return ConfirmInventoryImportForExpenseResponse(
            inventory_import_result=inventory_import_result,
            inventory_import_preview=inventory_import_preview,
            draft=payload.draft,
        )
