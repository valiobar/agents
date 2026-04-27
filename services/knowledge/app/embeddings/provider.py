from __future__ import annotations

from openai import AsyncOpenAI

from app.config import settings


class EmbeddingProvider:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.embedding_model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), settings.embedding_batch_size):
            batch = texts[start : start + settings.embedding_batch_size]
            response = await self.client.embeddings.create(model=self.model, input=batch)
            embeddings.extend(item.embedding for item in response.data)
        return embeddings

    async def embed_query(self, query: str) -> list[float]:
        response = await self.client.embeddings.create(model=self.model, input=query)
        return response.data[0].embedding
