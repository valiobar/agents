from __future__ import annotations

from app.clients.business.base import _BusinessClientBase
from app.models.financial.company import CompanyListResponse


class _CompaniesClient(_BusinessClientBase):
    async def list_companies(
        self,
        user_id: str,
        *,
        query: str | None = None,
        limit: int,
        offset: int = 0,
    ) -> CompanyListResponse:
        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        if query:
            params["query"] = query
        data = await self._request("GET", "/companies", user_id, params=params)
        return CompanyListResponse.model_validate(data)

    async def company_exists(self, user_id: str, company_id: str) -> bool:
        data = await self._request("GET", f"/companies/{company_id}/exists", user_id)
        return bool(data.get("exists")) if isinstance(data, dict) else False
