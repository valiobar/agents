from __future__ import annotations

from app.clients.business.base import BusinessClientError
from app.clients.business.companies import _CompaniesClient
from app.clients.business.financial import _FinancialClient
from app.clients.business.inventory import _InventoryClient
from app.clients.business.partners import _PartnersClient


class BusinessClient(
    _CompaniesClient,
    _PartnersClient,
    _FinancialClient,
    _InventoryClient,
):
    pass


__all__ = ["BusinessClient", "BusinessClientError"]
