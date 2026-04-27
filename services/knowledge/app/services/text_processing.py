from __future__ import annotations

import hashlib

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.services.loaders import LoadedPage


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def chunk_pages(pages: list[LoadedPage]) -> list[tuple[str, int | None]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    chunks: list[tuple[str, int | None]] = []
    for page in pages:
        for chunk in splitter.split_text(page.text):
            if chunk.strip():
                chunks.append((chunk, page.page_number))
    return chunks
