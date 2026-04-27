from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.errors import KnowledgeBaseError
from app.routes.health import router as health_router
from app.routes.documents import router as documents_router
from app.routes.retrieval import router as retrieval_router
from app.services.tax_preload_service import TaxPreloadService
from app.adapters.chroma import ChromaAdapter
from app.embeddings.provider import EmbeddingProvider
from app.utils.db import close_db, connect_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    if settings.preload_tax_docs:
        await TaxPreloadService(ChromaAdapter(), EmbeddingProvider()).preload()
    yield
    close_db()

app = FastAPI(title="Knowledge Base Service", version="1.0.0", lifespan=lifespan)


@app.exception_handler(KnowledgeBaseError)
async def knowledge_error_handler(request: Request, exc: KnowledgeBaseError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.include_router(health_router)
app.include_router(documents_router)
app.include_router(retrieval_router)

