from __future__ import annotations

from datetime import datetime, timezone

import redis.asyncio as aioredis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        self.limit = settings.rate_limit_per_hour

    async def dispatch(self, request: Request, call_next):
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            return await call_next(request)

        hour_bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H")
        key = f"rate:{user_id}:{hour_bucket}"

        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, 3600)

        if current > self.limit:
            retry_after = await self.redis.ttl(key)
            return JSONResponse(
                {"detail": "Rate limit exceeded. Try again later."},
                status_code=429,
                headers={"Retry-After": str(max(1, retry_after))},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, self.limit - current))
        return response
