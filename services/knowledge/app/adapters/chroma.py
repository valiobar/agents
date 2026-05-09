from __future__ import annotations

import asyncio
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.adapters.vector_store import VectorStore
from app.config import settings
from app.models.document import ChunkMetadata
from app.models.retrieval import RetrievedChunk


def _normalize_chroma_result(collection_name: str, result: dict[str, Any]) -> list[RetrievedChunk]:
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    chunks: list[RetrievedChunk] = []
    for text, metadata_dict, distance in zip(documents, metadatas, distances, strict=False):
        if not text:
            continue
        metadata = ChunkMetadata.model_validate(metadata_dict or {})
        chunks.append(
            RetrievedChunk(
                text=text,
                score=float(distance) if distance is not None else 0.0,
                collection=collection_name,
                metadata=metadata,
            )
        )
    return chunks


class ChromaAdapter(VectorStore):
    def __init__(self) -> None:
        # Disable client-side anonymized telemetry. ChromaDB's bundled posthog
        # client emits "Failed to send telemetry event ClientStartEvent:
        # capture() takes 1 positional argument but 3 were given" on every
        # call when it sees a newer posthog API; the warnings flood logs and
        # make it harder to spot real errors.
        self.client = chromadb.HttpClient(
            host=settings.chromadb_host,
            port=settings.chromadb_port,
            ssl=settings.chromadb_ssl,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def user_collection_name(self, user_id: str) -> str:
        return f"user_{user_id}"

    def global_tax_collection_name(self) -> str:
        return "global_tax"

    def global_inventory_collection_name(self) -> str:
        return "global_inventory"

    async def add_chunks(
        self,
        collection_name: str,
        chunk_ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[ChunkMetadata],
    ) -> None:
        def _add() -> None:
            collection = self.client.get_or_create_collection(collection_name)
            collection.upsert(
                ids=chunk_ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=[m.model_dump(exclude_none=True) for m in metadatas],
            )

        await asyncio.to_thread(_add)

    async def search(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int,
        where: dict[str, str | int | float | bool] | None = None,
    ) -> list[RetrievedChunk]:
        def _search() -> dict[str, Any]:
            collection = self.client.get_or_create_collection(collection_name)
            return collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )

        result = await asyncio.to_thread(_search)
        return _normalize_chroma_result(collection_name, result)

    async def delete_by_document(self, collection_name: str, document_id: str) -> None:
        def _delete() -> None:
            collection = self.client.get_or_create_collection(collection_name)
            collection.delete(where={"document_id": document_id})

        await asyncio.to_thread(_delete)
