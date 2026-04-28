from __future__ import annotations

from fastapi import HTTPException

from app.adapters.chroma import ChromaAdapter
from app.clients.business import BusinessServiceClient
from app.embeddings.provider import EmbeddingProvider
from app.models.retrieval import RetrievalRequest, RetrievalResponse


class RetrievalService:
    def __init__(
        self,
        vector_store: ChromaAdapter,
        embeddings: EmbeddingProvider,
        business_service: BusinessServiceClient,
    ) -> None:
        self.vector_store = vector_store
        self.embeddings = embeddings
        self.business_service = business_service

    async def retrieve(self, request: RetrievalRequest, user_id_from_header: str | None) -> RetrievalResponse:
        user_id = request.user_id or user_id_from_header
        query_embedding = await self.embeddings.embed_query(request.query)

        global_filters = dict(request.filters)
        global_filters.pop("company_id", None)

        chunks = []
        if request.include_global_tax:
            chunks.extend(
                await self.vector_store.search(
                    collection_name=self.vector_store.global_tax_collection_name(),
                    query_embedding=query_embedding,
                    top_k=request.top_k,
                    where=global_filters or None,
                )
            )

        if request.include_user_documents:
            if not user_id:
                raise HTTPException(status_code=422, detail="user_id is required for user document retrieval")

            if request.company_id:
                await self.business_service.require_company(user_id, request.company_id)
                where = dict(request.filters)
                where["company_id"] = request.company_id
            else:
                if not request.allow_legacy_all_company_documents:
                    raise HTTPException(
                        status_code=422,
                        detail="company_id is required for user document retrieval",
                    )
                where = dict(request.filters)
                where.pop("company_id", None)

            chunks.extend(
                await self.vector_store.search(
                    collection_name=self.vector_store.user_collection_name(user_id),
                    query_embedding=query_embedding,
                    top_k=request.top_k,
                    where=where or None,
                )
            )

        ranked = sorted(chunks, key=lambda chunk: chunk.score, reverse=True)[: request.top_k]
        return RetrievalResponse(query=request.query, chunks=ranked)
