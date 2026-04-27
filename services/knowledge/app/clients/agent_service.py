from __future__ import annotations

import httpx
from fastapi import HTTPException


class AgentServiceClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def require_company(self, user_id: str, company_id: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/companies/{company_id}/exists",
                    headers={"x-user-id": user_id},
                )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Company validation failed") from exc

        if response.status_code == 404:
            # Do not leak cross-user existence through upstream details.
            raise HTTPException(status_code=404, detail="Company not found")
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail="Company validation failed")

