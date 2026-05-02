from __future__ import annotations

from fastapi import UploadFile

from app.adapters.chroma import ChromaAdapter
from app.clients.business import BusinessServiceClient
from app.models.document import DocumentResponse, DocumentStatus, DocumentUpdate
from app.models.expense_extraction import ExpenseDraftRequestSourceDocumentType, ExpenseDraftResponse
from app.repositories.document_repo import DocumentRepository
from app.services.ingestion_service import DocumentNotFoundError, IngestionService
from app.services.expense_extraction_service import ExpenseExtractionService


class DocumentService:
    _DEFAULT_CONTENT_TYPE = "application/octet-stream"

    def __init__(
        self,
        documents: DocumentRepository,
        ingestion: IngestionService,
        vector_store: ChromaAdapter,
        business_service: BusinessServiceClient,
        expense_extraction: ExpenseExtractionService,
    ) -> None:
        self.documents = documents
        self.ingestion = ingestion
        self.vector_store = vector_store
        self.business_service = business_service
        self.expense_extraction = expense_extraction

    async def upload(self, user_id: str, company_id: str, file: UploadFile) -> DocumentResponse:
        content = await file.read()
        document = await self.ingestion.ingest_upload(
            user_id=user_id,
            company_id=company_id,
            filename=file.filename or "upload",
            content_type=file.content_type or self._DEFAULT_CONTENT_TYPE,
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
            content_type=file.content_type or self._DEFAULT_CONTENT_TYPE,
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

    async def create_expense_draft(
        self,
        *,
        user_id: str,
        company_id: str,
        file: UploadFile,
        source_document_type: ExpenseDraftRequestSourceDocumentType,
    ) -> ExpenseDraftResponse:
        content = await file.read()
        filename = file.filename or "receipt-upload"
        content_type = file.content_type or self._DEFAULT_CONTENT_TYPE

        document = await self.ingestion.create_source_document_metadata(
            user_id=user_id,
            company_id=company_id,
            filename=filename,
            content_type=content_type,
            content=content,
            source_document_type=source_document_type,
        )

        try:
            result = await self.expense_extraction.extract(
                filename=filename,
                content_type=content_type,
                content=content,
                source_document_type=source_document_type,
                source_document_id=document.id,
            )

            updated = await self.documents.update(
                document.id,
                user_id,
                DocumentUpdate(
                    status=DocumentStatus.READY,
                    chunk_count=0,
                    error_message=None,
                    metadata={
                        "source_document_type": result.draft.source_document_type,
                        "source_document_number": result.draft.source_document_number,
                        "extraction": {
                            "provider": result.provider,
                            "model": result.model,
                            "confidence": result.draft.confidence,
                            "warnings": result.draft.warnings,
                            "extracted_text": result.extracted_text,
                            "extracted_at": result.extracted_at,
                            "tasks": {
                                "expense": {
                                    "status": "draft_created",
                                    "confidence": result.draft.confidence,
                                },
                                "inventory": {"status": "not_requested"},
                            },
                        },
                    },
                ),
            )

            return ExpenseDraftResponse(
                document=DocumentResponse.model_validate(
                    (updated or document).model_dump(by_alias=False)
                ),
                draft=result.draft,
                extracted_text=result.extracted_text,
                provider=result.provider,
                model=result.model,
                extracted_at=result.extracted_at,
            )
        except Exception as exc:
            await self.documents.update(
                document.id,
                user_id,
                DocumentUpdate(
                    status=DocumentStatus.FAILED,
                    error_message=str(exc),
                    metadata={
                        "source_document_type": source_document_type,
                        "extraction": {
                            "tasks": {"expense": {"status": "failed"}},
                        },
                    },
                ),
            )
            raise
