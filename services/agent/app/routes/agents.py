from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from starlette.responses import StreamingResponse

from app.dependencies import (
    get_agent_service,
    get_chat_service,
    get_document_intake_service,
    get_receipt_service,
    get_sales_invoice_workflow_service,
    get_user_id,
)
from app.models.document_intake import (
    ConfirmInventoryImportForExpenseRequest,
    ConfirmInventoryImportForExpenseResponse,
    DocumentIntakeResponse,
)
from app.models.shared.agent import AgentCreate, AgentResponse, AgentUpdate
from app.models.shared.chat import ChatRequest
from app.models.financial.receipt import (
    ConfirmExtractedExpenseRequest,
    ConfirmExtractedExpenseResponse,
    ExpenseDraftRequestSourceDocumentType,
    ExpenseDraftResponse,
)
from app.models.sales_invoice_workflow import (
    ConfirmSalesInvoiceInventoryRequest,
    ConfirmSalesInvoiceRequest,
    CreateSalesInvoiceInventoryPreviewRequest,
    SalesInvoiceCreatedResponse,
    SalesInvoiceInventoryReviewResponse,
    SalesInvoiceReviewResponse,
)
from app.services.agent_service import AgentService
from app.services.chat_service import ChatService
from app.services.document_intake_service import DocumentIntakeService
from app.services.receipt_service import ReceiptService
from app.services.sales_invoice_workflow_service import SalesInvoiceWorkflowService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[AgentService, Depends(get_agent_service)],
):
    agent = await service.create_agent(user_id, payload)
    return AgentResponse.model_validate(agent)


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[AgentService, Depends(get_agent_service)],
    company_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    agents = await service.list_agents(user_id, limit=limit, offset=offset, company_id=company_id)
    return [AgentResponse.model_validate(a) for a in agents]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[AgentService, Depends(get_agent_service)],
):
    agent = await service.get_agent(user_id, agent_id)
    return AgentResponse.model_validate(agent)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[AgentService, Depends(get_agent_service)],
):
    agent = await service.update_agent(user_id, agent_id, payload)
    return AgentResponse.model_validate(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[AgentService, Depends(get_agent_service)],
):
    await service.delete_agent(user_id, agent_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{agent_id}/chat")
async def chat(
    agent_id: str,
    payload: ChatRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[ChatService, Depends(get_chat_service)],
):
    return StreamingResponse(
        service.stream_chat(user_id, agent_id, payload),
        media_type="text/event-stream",
    )


@router.post(
    "/{agent_id}/document-intake",
    response_model=DocumentIntakeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document_intake(
    agent_id: str,
    file: Annotated[UploadFile, File()],
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[DocumentIntakeService, Depends(get_document_intake_service)],
    requested_type: Annotated[ExpenseDraftRequestSourceDocumentType, Form()] = "auto",
) -> DocumentIntakeResponse:
    return await service.create_intake(
        user_id=user_id,
        agent_id=agent_id,
        file=file,
        requested_type=requested_type,
    )


@router.post(
    "/{agent_id}/document-intake/supplier-invoice/inventory-imports/confirm",
    response_model=ConfirmInventoryImportForExpenseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_supplier_invoice_inventory_import(
    agent_id: str,
    payload: ConfirmInventoryImportForExpenseRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[DocumentIntakeService, Depends(get_document_intake_service)],
) -> ConfirmInventoryImportForExpenseResponse:
    return await service.confirm_supplier_invoice_inventory_import(
        user_id=user_id,
        agent_id=agent_id,
        payload=payload,
    )


@router.post(
    "/{agent_id}/invoice-workflows/sales-inventory/preview",
    response_model=SalesInvoiceInventoryReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_sales_invoice_inventory_preview(
    agent_id: str,
    payload: CreateSalesInvoiceInventoryPreviewRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[SalesInvoiceWorkflowService, Depends(get_sales_invoice_workflow_service)],
) -> SalesInvoiceInventoryReviewResponse:
    return await service.create_preview(user_id=user_id, agent_id=agent_id, payload=payload)


@router.post(
    "/{agent_id}/invoice-workflows/sales-inventory/inventory/confirm",
    response_model=SalesInvoiceReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_sales_invoice_inventory(
    agent_id: str,
    payload: ConfirmSalesInvoiceInventoryRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[SalesInvoiceWorkflowService, Depends(get_sales_invoice_workflow_service)],
) -> SalesInvoiceReviewResponse:
    return await service.confirm_inventory(user_id=user_id, agent_id=agent_id, payload=payload)


@router.post(
    "/{agent_id}/invoice-workflows/sales-inventory/invoice/confirm",
    response_model=SalesInvoiceCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_sales_invoice(
    agent_id: str,
    payload: ConfirmSalesInvoiceRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[SalesInvoiceWorkflowService, Depends(get_sales_invoice_workflow_service)],
) -> SalesInvoiceCreatedResponse:
    return await service.confirm_invoice(user_id=user_id, agent_id=agent_id, payload=payload)


@router.post(
    "/{agent_id}/expense-drafts",
    response_model=ExpenseDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_expense_draft(
    agent_id: str,
    file: Annotated[UploadFile, File()],
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[ReceiptService, Depends(get_receipt_service)],
    source_document_type: Annotated[ExpenseDraftRequestSourceDocumentType, Form()] = "auto",
) -> ExpenseDraftResponse:
    return await service.create_draft(
        user_id=user_id,
        agent_id=agent_id,
        file=file,
        source_document_type=source_document_type,
    )


@router.post(
    "/{agent_id}/expenses/confirm",
    response_model=ConfirmExtractedExpenseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_expense(
    agent_id: str,
    payload: ConfirmExtractedExpenseRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[ReceiptService, Depends(get_receipt_service)],
) -> ConfirmExtractedExpenseResponse:
    return await service.confirm_expense(
        user_id=user_id,
        agent_id=agent_id,
        payload=payload,
    )
