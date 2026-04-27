from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import Response, StreamingResponse

from app.config import settings

router = APIRouter()

SERVICE_MAP: dict[str, str] = {
    "/auth": settings.auth_service_url,
    "/companies": settings.agent_service_url,
    "/partners": settings.agent_service_url,
    "/agents": settings.agent_service_url,
    "/conversations": settings.agent_service_url,
    "/invoices": settings.agent_service_url,
    "/expenses": settings.agent_service_url,
    "/documents": settings.knowledge_service_url,
    "/retrieve": settings.knowledge_service_url,
    "/orchestrator": settings.orchestrator_service_url,
}

STRIPPED_HEADERS = {"host", "content-length"}


def resolve_target(path: str) -> str | None:
    for prefix, base_url in SERVICE_MAP.items():
        if f"/{path}".startswith(prefix):
            return f"{base_url}/{path}"
    return None


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str):
    target_url = resolve_target(path)
    if not target_url:
        raise HTTPException(status_code=404, detail="Route not found")

    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    headers = {
        k: v for k, v in request.headers.items() if k.lower() not in STRIPPED_HEADERS
    }

    user_id = getattr(request.state, "user_id", None)
    if user_id:
        headers["x-user-id"] = str(user_id)

    body = await request.body()
    is_sse = "text/event-stream" in request.headers.get("accept", "")

    if is_sse:
        client = httpx.AsyncClient(timeout=120.0)
        req = client.build_request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
        )
        resp = await client.send(req, stream=True)

        async def stream_response():
            try:
                async for chunk in resp.aiter_bytes():
                    yield chunk
            finally:
                await resp.aclose()
                await client.aclose()

        return StreamingResponse(
            stream_response(),
            status_code=resp.status_code,
            headers=dict(resp.headers),
            media_type="text/event-stream",
        )

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
        )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
        )
