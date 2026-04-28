from __future__ import annotations

from dataclasses import dataclass

from app.clients.business import BusinessClient
from app.services.companybook_service import CompanyBookService


@dataclass(frozen=True)
class ToolContext:
    business_client: BusinessClient
    companybook_service: CompanyBookService

