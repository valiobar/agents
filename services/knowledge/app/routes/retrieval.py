from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.dependencies import get_retrieval_service
from app.models.retrieval import RetrievalRequest, RetrievalResponse
from app.services.retrieval_service import RetrievalService

router = APIRouter(tags=["retrieval"])


@router.post("/retrieve", response_model=RetrievalResponse)
async def retrieve(
    payload: RetrievalRequest,
    service: Annotated[RetrievalService, Depends(get_retrieval_service)],
    x_user_id: Annotated[str | None, Header()] = None,
):
    return await service.retrieve(payload, user_id_from_header=x_user_id)

