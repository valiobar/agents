from __future__ import annotations

from typing import Any

import httpx
from langchain_core.tools import tool

from app.config import settings

_ERROR_BODY_MAX = 500


def _snippet(text: str, max_len: int) -> str:
    stripped = text.strip()
    if len(stripped) <= max_len:
        return stripped
    return f"{stripped[:max_len]}…"


def _format_chunk(index: int, chunk: dict[str, Any]) -> str:
    meta = chunk.get("metadata")
    extra = ""
    if isinstance(meta, dict):
        filename = meta.get("filename")
        if filename:
            extra = f" file={filename}"
    coll = chunk.get("collection")
    score = chunk.get("score")
    body = chunk.get("text", "")
    return f"[{index + 1}] collection={coll} score={score}{extra}\n{body}"


def build_rag_search_tool(user_id: str, company_id: str | None):
    @tool("rag_search")
    async def rag_search(query: str) -> str:
        """Search tax regulations and the user's uploaded documents for relevant context."""
        base = settings.knowledge_service_url.rstrip("/")
        payload: dict[str, Any] = {
            "query": query,
            "user_id": user_id,
            "company_id": company_id,
            "top_k": settings.rag_top_k,
            "include_global_tax": True,
            "include_user_documents": company_id is not None,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{base}/retrieve",
                    json=payload,
                    headers={"x-user-id": user_id},
                )
        except httpx.RequestError as exc:
            return f"RAG retrieval failed: could not reach Knowledge Base ({exc!s})."

        if response.status_code >= 400:
            body = _snippet(response.text, _ERROR_BODY_MAX)
            return (
                f"RAG retrieval failed with HTTP {response.status_code}. "
                f"Response: {body}"
            )

        try:
            data = response.json()
        except ValueError:
            return "RAG retrieval failed: Knowledge Base returned invalid JSON."

        raw_chunks = data.get("chunks", [])
        if not raw_chunks:
            return "No relevant knowledge base chunks found."

        parts = [
            _format_chunk(i, c)
            for i, c in enumerate(raw_chunks)
            if isinstance(c, dict)
        ]
        if not parts:
            return "No relevant knowledge base chunks found."
        return "\n\n".join(parts)

    return rag_search
