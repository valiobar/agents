from __future__ import annotations

import asyncio
from io import BytesIO

from pydantic import BaseModel
from pypdf import PdfReader

from app.errors import UnsupportedDocumentTypeError

class LoadedPage(BaseModel):
    text: str
    page_number: int | None = None


async def load_document(content: bytes, content_type: str) -> list[LoadedPage]:
    if content_type == "application/pdf":
        def _read_pdf() -> list[LoadedPage]:
            reader = PdfReader(BytesIO(content))
            pages: list[LoadedPage] = []
            for index, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(LoadedPage(text=text, page_number=index + 1))
            return pages

        return await asyncio.to_thread(_read_pdf)

    if content_type in {"text/plain", "text/markdown"}:
        text = content.decode("utf-8", errors="replace")
        return [LoadedPage(text=text, page_number=None)] if text.strip() else []

    raise UnsupportedDocumentTypeError(content_type)
