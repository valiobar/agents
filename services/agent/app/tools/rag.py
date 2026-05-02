from __future__ import annotations

import logging
import re
import time
from typing import Any

import httpx
from langchain_core.tools import tool

from app.config import settings
from app.runtime.tool_context import ToolContext

logger = logging.getLogger(__name__)

_ERROR_BODY_MAX = 500
_RAG_CHUNK_BODY_MAX = 1200
_MAX_RAG_CALLS_PER_TURN = 2


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
    body_raw = chunk.get("text", "")
    body_text = body_raw if isinstance(body_raw, str) else str(body_raw)
    body = _snippet(body_text, _RAG_CHUNK_BODY_MAX)
    return f"[{index + 1}] collection={coll} score={score}{extra}\n{body}"


def _normalize_query(query: str) -> str:
    # Coarse normalization so tiny wording differences do not trigger
    # repeated near-identical retrieval loops in the same turn.
    lowered = query.lower()
    alnum_spaced = re.sub(r"[^\w\s]", " ", lowered)
    return " ".join(alnum_spaced.split())


def _rag_skip_reason(
    *,
    query: str,
    rag_call_count: int,
    recent_normalized_queries: list[str],
) -> str | None:
    normalized_query = _normalize_query(query)
    similar_query_seen = normalized_query in recent_normalized_queries
    recent_normalized_queries.append(normalized_query)
    if rag_call_count > _MAX_RAG_CALLS_PER_TURN:
        return "max_calls"
    if similar_query_seen:
        return "similar_query"
    return None


def build_rag_search_tool(
    user_id: str,
    company_id: str | None,
    tool_context: ToolContext,
):
    """
    Build the rag_search LangChain tool.

    The tool reuses the application-level ``httpx.AsyncClient`` from
    ``ToolContext.knowledge_http`` so concurrent tool calls share a single
    connection pool and timeout policy, instead of creating a fresh client
    (and pool) on every invocation. The latter caused parallel ``rag_search``
    invocations to occasionally stall because each fresh pool independently
    waited up to 60s on a transient OpenAI embedding hiccup downstream.
    """

    knowledge_http = tool_context.knowledge_http
    rag_call_count = 0
    recent_normalized_queries: list[str] = []

    @tool("rag_search")
    async def rag_search(query: str) -> str:
        """Search tax regulations and the user's uploaded documents for relevant context."""
        nonlocal rag_call_count
        rag_call_count += 1
        skip_reason = _rag_skip_reason(
            query=query,
            rag_call_count=rag_call_count,
            recent_normalized_queries=recent_normalized_queries,
        )
        if skip_reason is not None:
            logger.info(
                "rag_search skip user_id=%s call=%d reason=%s",
                user_id,
                rag_call_count,
                skip_reason,
            )
            return (
                "RAG search skipped to avoid repeated near-identical retrieval. "
                "Use the already retrieved chunks to answer the user directly. "
                "Only call rag_search again if the user asks for a different legal topic."
            )

        payload: dict[str, Any] = {
            "query": query,
            "user_id": user_id,
            "company_id": company_id,
            "top_k": settings.rag_top_k,
            "include_global_tax": True,
            "include_user_documents": company_id is not None,
        }

        started = time.monotonic()
        query_preview = query[:120].replace("\n", " ")
        logger.info(
            "rag_search start user_id=%s company_id=%s query=%s",
            user_id,
            company_id,
            query_preview,
        )
        try:
            response = await knowledge_http.post(
                "/retrieve",
                json=payload,
                headers={"x-user-id": user_id},
            )
        except httpx.TimeoutException as exc:
            elapsed = time.monotonic() - started
            logger.warning(
                "rag_search timed out after %.1fs (user_id=%s, query=%s): %s",
                elapsed,
                user_id,
                query_preview,
                exc,
            )
            return (
                "RAG retrieval timed out while contacting the Knowledge Base. "
                "Try a shorter or more specific query."
            )
        except httpx.RequestError as exc:
            elapsed = time.monotonic() - started
            logger.warning(
                "rag_search transport error after %.1fs (user_id=%s): %s",
                elapsed,
                user_id,
                exc,
            )
            return f"RAG retrieval failed: could not reach Knowledge Base ({exc!s})."

        elapsed = time.monotonic() - started
        if response.status_code >= 400:
            body = _snippet(response.text, _ERROR_BODY_MAX)
            logger.warning(
                "rag_search HTTP %d after %.2fs (user_id=%s): %s",
                response.status_code,
                elapsed,
                user_id,
                body,
            )
            return (
                f"RAG retrieval failed with HTTP {response.status_code}. "
                f"Response: {body}"
            )

        try:
            data = response.json()
        except ValueError:
            logger.error(
                "rag_search non-JSON response after %.2fs (user_id=%s)",
                elapsed,
                user_id,
            )
            return "RAG retrieval failed: Knowledge Base returned invalid JSON."

        raw_chunks = data.get("chunks", [])
        chunks = raw_chunks if isinstance(raw_chunks, list) else []
        logger.info(
            "rag_search ok user_id=%s elapsed=%.2fs chunks=%d",
            user_id,
            elapsed,
            len(chunks),
        )

        parts = [
            _format_chunk(i, c)
            for i, c in enumerate(chunks)
            if isinstance(c, dict)
        ]
        if not parts:
            return "No relevant knowledge base chunks found."
        return "\n\n".join(parts)

    return rag_search
