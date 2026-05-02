from __future__ import annotations

from typing import Any

import httpx
from fastapi import UploadFile

from app.models.receipt import ExpenseDraftResponse


class KnowledgeClientError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class KnowledgeClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    def _headers(self, user_id: str) -> dict[str, str]:
        return {"x-user-id": user_id}

    def _extract_detail(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return "Knowledge service returned an unexpected response."
        detail = data.get("detail") if isinstance(data, dict) else None
        return str(detail or "Knowledge request failed.")

    async def create_expense_draft(
        self,
        *,
        user_id: str,
        company_id: str,
        file: UploadFile,
        source_document_type: str,
    ) -> ExpenseDraftResponse:
        try:
            content = await file.read()
            files = {
                "file": (
                    file.filename or "receipt",
                    content,
                    file.content_type or "application/octet-stream",
                )
            }
            data = {"company_id": company_id, "source_document_type": source_document_type}
            response = await self.http.post(
                "/documents/expense-draft",
                headers=self._headers(user_id),
                files=files,
                data=data,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = self._extract_detail(exc.response)
            raise KnowledgeClientError(detail, status_code=exc.response.status_code) from exc
        except httpx.HTTPError as exc:
            raise KnowledgeClientError("Knowledge service is unavailable. Try again shortly.") from exc

        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise KnowledgeClientError("Knowledge service returned invalid JSON.") from exc
        return ExpenseDraftResponse.model_validate(payload)

