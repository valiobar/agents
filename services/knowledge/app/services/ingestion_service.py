from __future__ import annotations

from app.adapters.chroma import ChromaAdapter
from app.clients.business import BusinessServiceClient
from app.config import settings
from app.errors import DocumentNotFoundError, EmptyDocumentError, UploadTooLargeError
from app.embeddings.provider import EmbeddingProvider
from app.models.document import ChunkMetadata, DocumentCreate, DocumentInDB, DocumentStatus, DocumentUpdate
from app.models.expense_extraction import ExpenseDraftRequestSourceDocumentType
from app.repositories.document_repo import DocumentRepository
from app.errors import UnsupportedDocumentTypeError
from app.services.loaders import load_document
from app.services.text_processing import chunk_pages, compute_sha256

class IngestionService:
    def __init__(
        self,
        documents: DocumentRepository,
        vector_store: ChromaAdapter,
        embeddings: EmbeddingProvider,
        business_service: BusinessServiceClient,
    ) -> None:
        self.documents = documents
        self.vector_store = vector_store
        self.embeddings = embeddings
        self.business_service = business_service

    async def ingest_upload(
        self,
        user_id: str,
        company_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> DocumentInDB:
        if len(content) > settings.max_upload_size_bytes:
            raise UploadTooLargeError()
        if content_type not in settings.allowed_content_types:
            raise UnsupportedDocumentTypeError(content_type)

        await self.business_service.require_company(user_id, company_id)
        content_hash = compute_sha256(content)
        existing = await self.documents.find_by_hash(user_id, company_id, content_hash)
        if existing:
            return existing

        document = await self.documents.create(
            user_id=user_id,
            document=DocumentCreate(
                company_id=company_id,
                filename=filename,
                content_type=content_type,
                size_bytes=len(content),
                content_hash=content_hash,
            ),
        )

        try:
            pages = await load_document(content, content_type)
            chunks = chunk_pages(pages)
            if not chunks:
                raise EmptyDocumentError()

            texts = [text for text, _page in chunks]
            vectors = await self.embeddings.embed_texts(texts)

            metadatas = [
                ChunkMetadata(
                    document_id=document.id,
                    user_id=user_id,
                    company_id=company_id,
                    filename=filename,
                    chunk_index=index,
                    source="upload",
                    page_number=page_number,
                    content_hash=content_hash,
                )
                for index, (_text, page_number) in enumerate(chunks)
            ]
            chunk_ids = [f"{document.id}:{index}" for index in range(len(chunks))]

            await self.vector_store.add_chunks(
                collection_name=self.vector_store.user_collection_name(user_id),
                chunk_ids=chunk_ids,
                texts=texts,
                embeddings=vectors,
                metadatas=metadatas,
            )

            updated = await self.documents.update(
                document.id,
                user_id,
                DocumentUpdate(status=DocumentStatus.READY, chunk_count=len(chunks), error_message=None),
            )
            return updated or document
        except Exception as exc:
            await self.documents.update(
                document.id,
                user_id,
                DocumentUpdate(status=DocumentStatus.FAILED, error_message=str(exc)),
            )
            raise

    async def create_source_document_metadata(
        self,
        *,
        user_id: str,
        company_id: str,
        filename: str,
        content_type: str,
        content: bytes,
        source_document_type: ExpenseDraftRequestSourceDocumentType,
    ) -> DocumentInDB:
        if len(content) > settings.max_upload_size_bytes:
            raise UploadTooLargeError()
        if content_type not in settings.allowed_content_types:
            raise UnsupportedDocumentTypeError(content_type)

        await self.business_service.require_company(user_id, company_id)
        content_hash = compute_sha256(content)

        return await self.documents.create(
            user_id=user_id,
            document=DocumentCreate(
                company_id=company_id,
                filename=filename,
                content_type=content_type,
                size_bytes=len(content),
                content_hash=content_hash,
                metadata={"source_document_type": source_document_type},
            ),
        )

    async def reingest_upload(
        self,
        document_id: str,
        user_id: str,
        company_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> DocumentInDB:
        if len(content) > settings.max_upload_size_bytes:
            raise UploadTooLargeError()
        if content_type not in settings.allowed_content_types:
            raise UnsupportedDocumentTypeError(content_type)

        await self.business_service.require_company(user_id, company_id)
        existing = await self.documents.get_by_id(document_id, user_id)
        if not existing:
            raise DocumentNotFoundError(document_id)

        new_hash = compute_sha256(content)
        if new_hash == existing.content_hash:
            return existing

        # Ensure vector store does not keep stale chunks.
        await self.vector_store.delete_by_document(
            self.vector_store.user_collection_name(user_id),
            document_id,
        )

        # Reset metadata to processing for the same document id, then re-add chunks.
        await self.documents.update(
            document_id,
            user_id,
            DocumentUpdate(
                filename=filename,
                content_type=content_type,
                size_bytes=len(content),
                content_hash=new_hash,
                status=DocumentStatus.PROCESSING,
                error_message=None,
                chunk_count=0,
            ),
        )

        try:
            pages = await load_document(content, content_type)
            chunks = chunk_pages(pages)
            if not chunks:
                raise EmptyDocumentError()

            texts = [text for text, _page in chunks]
            vectors = await self.embeddings.embed_texts(texts)
            metadatas = [
                ChunkMetadata(
                    document_id=document_id,
                    user_id=user_id,
                    company_id=company_id,
                    filename=filename,
                    chunk_index=index,
                    source="upload",
                    page_number=page_number,
                    content_hash=new_hash,
                )
                for index, (_text, page_number) in enumerate(chunks)
            ]
            chunk_ids = [f"{document_id}:{index}" for index in range(len(chunks))]

            await self.vector_store.add_chunks(
                collection_name=self.vector_store.user_collection_name(user_id),
                chunk_ids=chunk_ids,
                texts=texts,
                embeddings=vectors,
                metadatas=metadatas,
            )

            updated = await self.documents.update(
                document_id,
                user_id,
                DocumentUpdate(status=DocumentStatus.READY, chunk_count=len(chunks), error_message=None),
            )
            if not updated:
                raise DocumentNotFoundError(document_id)
            return updated
        except Exception as exc:
            await self.documents.update(
                document_id,
                user_id,
                DocumentUpdate(status=DocumentStatus.FAILED, error_message=str(exc)),
            )
            raise
