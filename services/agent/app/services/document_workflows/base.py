from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from app.clients.business import BusinessClient
from app.models.document_intake import (
    DocumentIntakeDraftResponse,
    DocumentIntakeResponse,
)


class DocumentWorkflowValidationError(ValueError):
    """Raised when a workflow cannot build a valid review payload."""


@dataclass(frozen=True)
class DocumentIntakeContext:
    user_id: str
    company_id: str
    extraction: DocumentIntakeDraftResponse
    business_client: BusinessClient


class DocumentWorkflow(Protocol):
    async def create_review(self, context: DocumentIntakeContext) -> DocumentIntakeResponse:
        ...


class DocumentWorkflowRegistry:
    def __init__(
        self,
        workflows: Mapping[str, DocumentWorkflow],
        fallback: DocumentWorkflow,
    ) -> None:
        self._workflows = dict(workflows)
        self._fallback = fallback

    def resolve(self, document_type: str) -> DocumentWorkflow:
        return self._workflows.get(document_type, self._fallback)
