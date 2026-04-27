from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.dependencies import get_document_service, require_user_id
from app.models.document import DocumentResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: Annotated[UploadFile, File()],
    company_id: Annotated[str, Form()],
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentResponse:
    return await service.upload(user_id=user_id, company_id=company_id, file=file)


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: str,
    file: Annotated[UploadFile, File()],
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentResponse:
    return await service.update_upload(user_id=user_id, document_id=document_id, file=file)


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    company_id: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[DocumentResponse]:
    return await service.list_documents(user_id=user_id, company_id=company_id, limit=limit, offset=offset)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> Response:
    await service.delete(user_id=user_id, document_id=document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

