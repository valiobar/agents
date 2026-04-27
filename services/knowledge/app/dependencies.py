from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.adapters.chroma import ChromaAdapter
from app.clients.agent_service import AgentServiceClient
from app.embeddings.provider import EmbeddingProvider
from app.config import settings
from app.repositories.document_repo import DocumentRepository
from app.services.document_service import DocumentService
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


def get_agent_service_client() -> AgentServiceClient:
    return AgentServiceClient(settings.agent_service_url)


def get_document_service(
    documents: DocumentRepository = Depends(get_document_repository),
    vector_store: ChromaAdapter = Depends(get_vector_store),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    agent_service: AgentServiceClient = Depends(get_agent_service_client),
) -> DocumentService:
    ingestion = IngestionService(documents, vector_store, embeddings, agent_service)
    return DocumentService(documents, ingestion, vector_store, agent_service)


def get_retrieval_service(
    vector_store: ChromaAdapter = Depends(get_vector_store),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    agent_service: AgentServiceClient = Depends(get_agent_service_client),
) -> RetrievalService:
    return RetrievalService(vector_store, embeddings, agent_service)

