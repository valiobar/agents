from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.middleware.auth import JWTAuthMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.routes.proxy import router as proxy_router

app = FastAPI(title="API Gateway", version="1.0.0")

# Starlette executes middleware in reverse order of addition.
# Add rate limiting first so JWT auth runs before it on each request.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(JWTAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}


app.include_router(proxy_router)
