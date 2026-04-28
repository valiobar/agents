from __future__ import annotations

from fastapi import UploadFile

from app.adapters.chroma import ChromaAdapter
from app.clients.business import BusinessServiceClient
from app.models.document import DocumentResponse, DocumentStatus, DocumentUpdate
from app.repositories.document_repo import DocumentRepository
from app.services.ingestion_service import DocumentNotFoundError, IngestionService


class DocumentService:
    def __init__(
        self,
        documents: DocumentRepository,
        ingestion: IngestionService,
        vector_store: ChromaAdapter,
        business_service: BusinessServiceClient,
    ) -> None:
        self.documents = documents
        self.ingestion = ingestion
        self.vector_store = vector_store
        self.business_service = business_service

    async def upload(self, user_id: str, company_id: str, file: UploadFile) -> DocumentResponse:
        content = await file.read()
        document = await self.ingestion.ingest_upload(
            user_id=user_id,
            company_id=company_id,
            filename=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream",
            content=content,
        )
        return DocumentResponse.model_validate(document.model_dump(by_alias=False))

    async def update_upload(self, user_id: str, document_id: str, file: UploadFile) -> DocumentResponse:
        content = await file.read()
        existing = await self.documents.get_by_id(document_id=document_id, user_id=user_id)
        if not existing:
            raise DocumentNotFoundError(document_id)
        document = await self.ingestion.reingest_upload(
            document_id=document_id,
            user_id=user_id,
            company_id=existing.company_id,
            filename=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream",
            content=content,
        )
        return DocumentResponse.model_validate(document.model_dump(by_alias=False))

    async def list_documents(
        self, user_id: str, company_id: str, limit: int, offset: int
    ) -> list[DocumentResponse]:
        docs = await self.documents.list_by_user_company(
            user_id=user_id,
            company_id=company_id,
            limit=min(limit, 100),
            offset=max(offset, 0),
        )
        return [DocumentResponse.model_validate(doc.model_dump(by_alias=False)) for doc in docs]

    async def delete(self, user_id: str, document_id: str) -> None:
        document = await self.documents.get_by_id(document_id=document_id, user_id=user_id)
        if not document:
            raise DocumentNotFoundError(document_id)

        await self.vector_store.delete_by_document(
            self.vector_store.user_collection_name(user_id),
            document_id,
        )
        await self.documents.update(
            document_id=document_id,
            user_id=user_id,
            update=DocumentUpdate(status=DocumentStatus.DELETED),
        )
