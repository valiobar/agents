from __future__ import annotations

from typing import Any

import httpx


class BusinessClientError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class _BusinessClientBase:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    def _headers(self, user_id: str) -> dict[str, str]:
        return {"x-user-id": user_id}

    async def _request(self, method: str, path: str, user_id: str, **kwargs: Any) -> Any:
        try:
            response = await self.http.request(method, path, headers=self._headers(user_id), **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = self._extract_detail(exc.response)
            raise BusinessClientError(detail, status_code=exc.response.status_code) from exc
        except httpx.HTTPError as exc:
            raise BusinessClientError("Business service is unavailable. Try again shortly.") from exc
        return response.json()

    def _extract_detail(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return "Business service returned an unexpected response."
        detail = data.get("detail") if isinstance(data, dict) else None
        return str(detail or "Business request failed.")
