from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.adapters.chroma import ChromaAdapter
from app.config import settings
from app.embeddings.provider import EmbeddingProvider
from app.models.document import ChunkMetadata
from app.services.loaders import load_document
from app.services.text_processing import chunk_pages, compute_sha256

logger = logging.getLogger(__name__)


def _content_type_for_path(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    if suffix == ".txt":
        return "text/plain"
    if suffix == ".md":
        return "text/markdown"
    return None


class InventoryPreloadService:
    def __init__(self, vector_store: ChromaAdapter, embeddings: EmbeddingProvider) -> None:
        self.vector_store = vector_store
        self.embeddings = embeddings

    async def preload(self) -> None:
        root = Path(settings.inventory_docs_path)
        root.mkdir(parents=True, exist_ok=True)

        paths = [p for p in root.rglob("*") if p.is_file() and _content_type_for_path(p) is not None]
        if not paths:
            logger.info("Inventory preload: no docs found", extra={"inventory_docs_path": str(root)})
            return

        for path in sorted(paths):
            try:
                content = await asyncio.to_thread(path.read_bytes)
                content_hash = compute_sha256(content)
                content_type = _content_type_for_path(path)
                if not content_type:
                    continue

                pages = await load_document(content, content_type)
                chunks = chunk_pages(pages)
                if not chunks:
                    logger.info("Inventory preload: no extractable text", extra={"path": str(path)})
                    continue

                relative_path = str(path.relative_to(root))
                document_id = f"inventory:{relative_path}:{content_hash[:12]}"

                texts = [text for text, _page in chunks]
                vectors = await self.embeddings.embed_texts(texts)
                metadatas = [
                    ChunkMetadata(
                        document_id=document_id,
                        filename=path.name,
                        chunk_index=index,
                        source="global_inventory",
                        page_number=page_number,
                        content_hash=content_hash,
                    )
                    for index, (_text, page_number) in enumerate(chunks)
                ]
                chunk_ids = [f"{document_id}:{index}" for index in range(len(chunks))]

                await self.vector_store.add_chunks(
                    collection_name=self.vector_store.global_inventory_collection_name(),
                    chunk_ids=chunk_ids,
                    texts=texts,
                    embeddings=vectors,
                    metadatas=metadatas,
                )
                logger.info(
                    "Inventory preload: loaded",
                    extra={"path": str(path), "chunks": len(chunks), "document_id": document_id},
                )
            except Exception:
                logger.exception("Inventory preload: failed to load", extra={"path": str(path)})
                continue
