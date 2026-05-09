from __future__ import annotations

from app.clients.business.base import _BusinessClientBase
from app.models.financial.company import CompanyResponse


class _CompaniesClient(_BusinessClientBase):
    async def list_companies(
        self,
        user_id: str,
        *,
        limit: int,
        offset: int = 0,
    ) -> list[CompanyResponse]:
        data = await self._request("GET", "/companies", user_id, params={"limit": limit, "offset": offset})
        return [CompanyResponse.model_validate(item) for item in data]

    async def company_exists(self, user_id: str, company_id: str) -> bool:
        data = await self._request("GET", f"/companies/{company_id}/exists", user_id)
        return bool(data.get("exists")) if isinstance(data, dict) else False
