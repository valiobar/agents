from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_financial_summary_service, get_user_id
from app.financial.models import FinancialSummaryRequest, FinancialSummaryResponse
from app.financial.services.financial_summary_service import FinancialSummaryService

router = APIRouter(prefix="/financial-summary", tags=["financial-summary"])


@router.post("", response_model=FinancialSummaryResponse)
async def get_financial_summary(
    payload: FinancialSummaryRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[FinancialSummaryService, Depends(get_financial_summary_service)],
) -> FinancialSummaryResponse:
    summary = await service.get_summary(user_id, payload)
    return FinancialSummaryResponse.model_validate(summary)
