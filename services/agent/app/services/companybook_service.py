from __future__ import annotations

from typing import Any

import httpx

from app.models.companybook import CompanyBookCompanyDetail, CompanyBookSearchResponse


class CompanyBookError(Exception):
    def __init__(self, user_message: str) -> None:
        self.user_message = user_message
        super().__init__(user_message)


class CompanyBookConfigError(CompanyBookError):
    pass


class CompanyBookApiError(CompanyBookError):
    pass


class CompanyBookService:
    def __init__(self, api_key: str, base_url: str, timeout: float) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @property
    def headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key}

    def _require_api_key(self) -> None:
        if not self.api_key:
            raise CompanyBookConfigError("CompanyBook API key is not configured")

    async def search_companies(
        self,
        name: str,
        limit: int = 5,
        active_only: bool = True,
    ) -> CompanyBookSearchResponse:
        self._require_api_key()
        query = name.strip()
        if not query:
            return CompanyBookSearchResponse(results=[])

        params: dict[str, Any] = {"name": query, "limit": limit, "with_data": False}
        if active_only:
            params["status"] = True

        payload = await self._get_json("/companies/search", params=params)
        return CompanyBookSearchResponse.from_api(payload)

    async def get_company(self, uic: str) -> CompanyBookCompanyDetail:
        self._require_api_key()
        normalized_uic = uic.strip()
        if not normalized_uic:
            raise CompanyBookApiError("Company UIC is required")

        payload = await self._get_json(
            f"/companies/{normalized_uic}",
            params={"with_data": True},
        )
        return CompanyBookCompanyDetail.from_api(payload)

    async def _get_json(self, path: str, params: dict[str, Any]) -> Any:
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self.headers,
            ) as client:
                response = await client.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise CompanyBookApiError("CompanyBook request timed out") from exc
        except httpx.RequestError as exc:
            raise CompanyBookApiError("CompanyBook service is currently unreachable") from exc

        if response.status_code == 401 or response.status_code == 403:
            raise CompanyBookApiError("CompanyBook API key was rejected")
        if response.status_code == 429:
            raise CompanyBookApiError("CompanyBook rate limit was reached. Try again later.")
        if response.status_code == 404:
            raise CompanyBookApiError("CompanyBook did not find a company for that UIC")
        if response.status_code >= 400:
            raise CompanyBookApiError("CompanyBook request failed")

        try:
            return response.json()
        except ValueError as exc:
            raise CompanyBookApiError("CompanyBook returned an invalid response") from exc
