from __future__ import annotations

from fastapi import HTTPException, status

from app.clients.business import BusinessClient, BusinessClientError
from app.models.sales_invoice_workflow import (
    ConfirmSalesInvoiceInventoryRequest,
    ConfirmSalesInvoiceRequest,
    CreateSalesInvoiceInventoryPreviewRequest,
    SalesInvoiceCreatedResponse,
    SalesInvoiceInventoryReviewResponse,
    SalesInvoiceReviewResponse,
)
from app.repositories.agent_repo import AgentRepository
from app.services.sales_invoice_workflow_graph import (
    run_inventory_confirm_graph,
    run_invoice_confirm_graph,
    run_preview_graph,
)
from app.services.workflows import map_business_client_error


class SalesInvoiceWorkflowService:
    def __init__(self, agent_repo: AgentRepository, business_client: BusinessClient) -> None:
        self.agent_repo = agent_repo
        self.business_client = business_client

    async def create_preview(
        self,
        *,
        user_id: str,
        agent_id: str,
        payload: CreateSalesInvoiceInventoryPreviewRequest,
    ) -> SalesInvoiceInventoryReviewResponse:
        try:
            return await run_preview_graph(
                user_id=user_id,
                agent_id=agent_id,
                agent_repo=self.agent_repo,
                business_client=self.business_client,
                payload=payload,
            )
        except BusinessClientError as exc:
            raise map_business_client_error(exc) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to create sales invoice inventory preview",
            ) from exc

    async def confirm_inventory(
        self,
        *,
        user_id: str,
        agent_id: str,
        payload: ConfirmSalesInvoiceInventoryRequest,
    ) -> SalesInvoiceReviewResponse:
        try:
            return await run_inventory_confirm_graph(
                user_id=user_id,
                agent_id=agent_id,
                agent_repo=self.agent_repo,
                business_client=self.business_client,
                payload=payload,
            )
        except BusinessClientError as exc:
            raise map_business_client_error(exc) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to confirm sales invoice inventory selection",
            ) from exc

    async def confirm_invoice(
        self,
        *,
        user_id: str,
        agent_id: str,
        payload: ConfirmSalesInvoiceRequest,
    ) -> SalesInvoiceCreatedResponse:
        try:
            return await run_invoice_confirm_graph(
                user_id=user_id,
                agent_id=agent_id,
                agent_repo=self.agent_repo,
                business_client=self.business_client,
                payload=payload,
            )
        except BusinessClientError as exc:
            raise map_business_client_error(exc) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to confirm sales invoice creation",
            ) from exc

