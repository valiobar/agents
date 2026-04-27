from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.document import ChunkMetadata
from app.models.retrieval import RetrievedChunk


class VectorStore(ABC):
    @abstractmethod
    async def add_chunks(
        self,
        collection_name: str,
        chunk_ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[ChunkMetadata],
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def search(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int,
        where: dict[str, str | int | float | bool] | None = None,
    ) -> list[RetrievedChunk]:
        raise NotImplementedError

    @abstractmethod
    async def delete_by_document(self, collection_name: str, document_id: str) -> None:
        raise NotImplementedError
