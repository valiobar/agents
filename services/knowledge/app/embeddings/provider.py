from __future__ import annotations

import logging
import time

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingProvider:
    def __init__(self) -> None:
        # Cap the per-request timeout so a stalled OpenAI embedding call cannot
        # silently hang `/retrieve` for the SDK default of 10 minutes. Two
        # retries are kept to ride out transient rate-limit blips without
        # extending the worst case beyond ~1 minute.
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.embedding_timeout_seconds,
            max_retries=2,
        )
        self.model = settings.embedding_model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), settings.embedding_batch_size):
            batch = texts[start : start + settings.embedding_batch_size]
            t0 = time.monotonic()
            response = await self.client.embeddings.create(model=self.model, input=batch)
            logger.debug(
                "embed_texts batch=%d elapsed=%.2fs", len(batch), time.monotonic() - t0
            )
            embeddings.extend(item.embedding for item in response.data)
        return embeddings

    async def embed_query(self, query: str) -> list[float]:
        t0 = time.monotonic()
        response = await self.client.embeddings.create(model=self.model, input=query)
        elapsed = time.monotonic() - t0
        if elapsed > 5.0:
            logger.warning("embed_query slow: %.2fs (chars=%d)", elapsed, len(query))
        return response.data[0].embedding
