from __future__ import annotations

from typing import Any

import httpx
from fastapi import UploadFile

from app.models.document_intake import (
    DocumentClassification,
    DocumentIntakeDraftResponse,
)
from app.models.financial.receipt import ExpenseDraftResponse


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

    @staticmethod
    def _normalize_expense_draft_payload(payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload
        draft = payload.get("draft")
        if not isinstance(draft, dict):
            return payload
        vendor_partner = draft.get("vendor_partner")
        if not isinstance(vendor_partner, dict):
            return payload
        email = vendor_partner.get("email")
        if not isinstance(email, str):
            return payload
        normalized_email = email.strip()
        if not normalized_email or "@" not in normalized_email:
            vendor_partner["email"] = None
        else:
            vendor_partner["email"] = normalized_email
        return payload

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
        payload = self._normalize_expense_draft_payload(payload)
        return ExpenseDraftResponse.model_validate(payload)

    async def create_document_intake_draft(
        self,
        *,
        user_id: str,
        company_id: str,
        file: UploadFile,
        requested_type: str = "auto",
    ) -> DocumentIntakeDraftResponse:
        # Extension point: switch to a dedicated `/documents/intake-draft` endpoint
        # when Knowledge exposes one without changing Agent workflow callers.
        response = await self.create_expense_draft(
            user_id=user_id,
            company_id=company_id,
            file=file,
            source_document_type=requested_type,
        )
        source_type = response.draft.source_document_type
        if source_type == "invoice":
            document_type = "supplier_invoice"
        elif source_type == "receipt":
            document_type = "receipt"
        else:
            document_type = "unknown"
        return DocumentIntakeDraftResponse(
            classification=DocumentClassification(
                document_type=document_type,
                confidence=response.draft.confidence,
                warnings=list(response.draft.warnings),
            ),
            document=response.document,
            draft=response.draft,
            extracted_text=response.extracted_text,
            provider=response.provider,
            model=response.model,
            extracted_at=response.extracted_at,
        )

