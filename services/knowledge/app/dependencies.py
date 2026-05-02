from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.config import settings
from app.adapters.chroma import ChromaAdapter
from app.clients.business import BusinessServiceClient
from app.embeddings.provider import EmbeddingProvider
from app.repositories.document_repo import DocumentRepository
from app.services.document_service import DocumentService
from app.services.expense_extraction_provider import OpenAIExpenseExtractionProvider
from app.services.expense_extraction_service import ExpenseExtractionService
from app.services.ingestion_service import IngestionService
from app.services.retrieval_service import RetrievalService
from app.utils.db import get_database


def require_user_id(x_user_id: Annotated[str | None, Header()] = None) -> str:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing x-user-id header",
        )
    return x_user_id


def get_document_repository() -> DocumentRepository:
    return DocumentRepository(get_database())


def get_vector_store() -> ChromaAdapter:
    return ChromaAdapter()


def get_embedding_provider() -> EmbeddingProvider:
    return EmbeddingProvider()


def get_business_service_client() -> BusinessServiceClient:
    return BusinessServiceClient(settings.business_service_url)


def get_document_service(
    documents: DocumentRepository = Depends(get_document_repository),
    vector_store: ChromaAdapter = Depends(get_vector_store),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    business_service: BusinessServiceClient = Depends(get_business_service_client),
) -> DocumentService:
    ingestion = IngestionService(documents, vector_store, embeddings, business_service)
    expense_provider = OpenAIExpenseExtractionProvider(
        api_key=settings.openai_api_key,
        model=settings.vision_extraction_model,
        timeout_seconds=settings.expense_extraction_timeout_seconds,
    )
    expense_extraction = ExpenseExtractionService(
        provider=expense_provider,
        provider_name=settings.expense_extraction_provider,
        model=settings.vision_extraction_model,
    )

    return DocumentService(documents, ingestion, vector_store, business_service, expense_extraction)


def get_retrieval_service(
    vector_store: ChromaAdapter = Depends(get_vector_store),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    business_service: BusinessServiceClient = Depends(get_business_service_client),
) -> RetrievalService:
    return RetrievalService(vector_store, embeddings, business_service)

