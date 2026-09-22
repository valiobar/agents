# API Gateway

## Overview

Thin reverse-proxy with cross-cutting concerns: **JWT validation**, **per-user rate limiting**, and **request routing**. The gateway listens on container port **8000** and is published on host port **8010**. It is the **only backend entry point** for the frontend and external clients — no service should be called directly in production.

- **Framework:** FastAPI 0.115 (Starlette middleware layer)
- **HTTP client:** httpx (async, streaming-capable)
- **JWT:** python-jose with HS256
- **Rate-limit store:** Redis (via redis-py async)

---

## Request Lifecycle

Every inbound request passes through the following pipeline in this exact order:

```
Client request
  │
  ▼
┌─────────────────────────────────────────┐
│ 1. CORSMiddleware                       │
│    • Allows CORS_ORIGINS                │
│    • Answers browser preflight requests │
├─────────────────────────────────────────┤
│ 2. JWTAuthMiddleware                    │
│    • Skips /auth/* and /health          │
│    • Validates Bearer token             │
│    • Sets request.state.user_id         │
│    • Returns 401 on failure             │
├─────────────────────────────────────────┤
│ 3. RateLimitMiddleware                  │
│    • Skips if no user_id (unauthed)     │
│    • INCR rate:{user_id}:{hour} in Redis│
│    • Returns 429 if over limit          │
│    • Adds X-RateLimit-* headers         │
├─────────────────────────────────────────┤
│ 4. /health or Proxy Router              │
│    • Matches path prefix → target URL   │
│    • Injects x-user-id header           │
│    • SSE streaming if Accept matches    │
│    • Returns 404 if no route match      │
└─────────────────────────────────────────┘
```

> **Middleware registration order matters.** Starlette executes middleware in reverse order of `app.add_middleware()` calls. In `main.py`, `CORSMiddleware` is added after the custom middleware so browser preflight requests are handled before JWT auth/rate limiting. `RateLimitMiddleware` is added before `JWTAuthMiddleware`, so JWT runs before rate limiting on normal requests. This is intentional because rate limiting needs the `user_id` that JWT auth sets.

---

## Routing Table

The proxy resolves the first matching path prefix from the `SERVICE_MAP` dictionary in `routes/proxy.py`:

| Path Prefix | Target Service | Internal URL | Auth Required |
|-------------|---------------|--------------|:------------:|
| `/auth/*` | Auth Service | `http://auth:8001` | No |
| `/companies/*` | Business Service | `http://business:8005` | Yes |
| `/partners/*` | Business Service | `http://business:8005` | Yes |
| `/agents/*` | Agent Service | `http://agent:8002` | Yes |
| `/conversations/*` | Agent Service | `http://agent:8002` | Yes |
| `/invoices/*` | Business Service | `http://business:8005` | Yes |
| `/expenses/*` | Business Service | `http://business:8005` | Yes |
| `/documents` | Knowledge Base Service | `http://knowledge:8003` | Yes |
| `/retrieve` | Knowledge Base Service | `http://knowledge:8003` | Yes |
| `/orchestrator/*` | Orchestrator Service | `http://orchestrator:8004` | Yes |

**Path forwarding:** The full path (including the prefix) is forwarded to the target service. For example, `GET /documents?company_id=abc&limit=20` is proxied to `http://knowledge:8003/documents?company_id=abc&limit=20`. Query parameters are preserved.

`/companies/*`, `/partners/*`, `/invoices/*`, and `/expenses/*` are Business Service routes. The gateway only authenticates, rate limits, injects `x-user-id`, and forwards these requests; company ownership, partner scoping, invoice snapshots, and financial business rules live in the Business Service.

**Supported HTTP methods:** GET, POST, PUT, DELETE, PATCH.

**Unmatched routes:** Any path that doesn't match a prefix returns `404 {"detail": "Route not found"}`.

### Adding a New Route

To route a new path prefix to an existing or new service:

1. Add the prefix → URL mapping in `SERVICE_MAP` in `gateway/app/routes/proxy.py`.
2. Add the service URL to `gateway/app/config.py` as a new `Settings` field with a sensible default.
3. If the service is new, add it to `docker-compose.yml` and the `.env.example`.

No changes to the middleware or proxy function are needed — the catch-all route handler `/{path:path}` picks it up automatically.

---

## Middleware Details

### 1. CORS (`CORSMiddleware`)

The gateway allows the origins in `CORS_ORIGINS` (default `http://localhost:3000` for `npm run dev`, `http://localhost:3010` for Compose, and `http://159.89.26.67:3010` on the droplet). It supports credentials, all methods, and all request headers. This matters when the browser calls the gateway directly. The default frontend uses the same-origin `/gateway-api` rewrite, so most browser calls never leave the frontend origin.

### 2. JWT Authentication (`middleware/auth.py`)

**Class:** `JWTAuthMiddleware` (extends `BaseHTTPMiddleware`)

**Behavior:**

1. Checks the request path against `SKIP_AUTH_PREFIXES = ("/auth", "/health")`. If it matches, the request passes through with no auth check.
2. Reads the `Authorization` header. If missing or not in `Bearer <token>` format → `401`.
3. Decodes the JWT using `settings.jwt_secret` with HS256 algorithm.
4. Extracts the `sub` claim (user ID). If missing → `401`.
5. Stores the user ID on `request.state.user_id` for downstream middleware and route handlers.
6. On any `JWTError` (expired, tampered, malformed) → `401`.

**Skip-auth prefixes:**

| Prefix | Reason |
|--------|--------|
| `/auth` | Registration and login endpoints must be accessible without a token |
| `/health` | Health check must always be reachable for monitoring |

**Future considerations:**

- To add more public routes, append to `SKIP_AUTH_PREFIXES` in `middleware/auth.py`.
- Token refresh is not handled at the gateway level — the auth service issues new tokens. A future enhancement could intercept expired-token errors and attempt a transparent refresh.
- The gateway only validates the **access token**. It does not check the `type` claim (which distinguishes access from refresh tokens). Backend services that accept refresh tokens should validate `type == "refresh"` themselves.

### 3. Rate Limiting (`middleware/rate_limit.py`)

**Class:** `RateLimitMiddleware` (extends `BaseHTTPMiddleware`)

**Behavior:**

1. Reads `request.state.user_id`. If absent (unauthenticated request) → skip rate limiting entirely.
2. Builds a Redis key: `rate:{user_id}:{YYYYMMDDHH}` (UTC hour bucket).
3. Atomically increments the key with `INCR`. On the first increment (value = 1), sets TTL to 3600 seconds.
4. If the current count exceeds the limit → `429` with `Retry-After: 3600` header.
5. Otherwise, proceeds and adds response headers:
   - `X-RateLimit-Limit` — the configured maximum.
   - `X-RateLimit-Remaining` — how many requests are left in the current window.

**Redis key pattern:**

```
rate:{user_id}:{hour_bucket}
```

Examples:
```
rate:665f1a2b3c4d5e6f7a8b9c0d:2026042518   → user's counter for 2026-04-25 18:00-18:59 UTC
```

**Design decisions and trade-offs:**

| Decision | Rationale |
|----------|-----------|
| Fixed 1-hour window (not sliding) | Simple, Redis-cheap (single INCR + TTL), good enough for Phase 1 |
| Per-user, not per-IP | Prevents abuse by authenticated users; unauthenticated paths are unmetered |
| Skip if no user_id | Auth endpoints and health checks are not rate-limited |
| UTC-based hour buckets | Avoids timezone ambiguity across services |

**Future considerations:**

- **Sliding window:** Replace fixed-window with Redis sorted sets (`ZADD` + `ZRANGEBYSCORE`) for smoother rate limiting without burst-at-boundary issues.
- **Per-endpoint limits:** Different limits for heavy operations (e.g., LLM calls) vs. lightweight reads.
- **Admin bypass:** Exempt admin roles from rate limiting via a claim in the JWT.
- **Redis connection failure:** Currently, if Redis is unreachable, the middleware throws an unhandled exception (500). A future improvement should catch `ConnectionError` and either fail-open (allow the request) or fail-closed (deny with 503) based on policy.

---

## Proxy Behavior (`routes/proxy.py`)

### Standard Requests

For non-SSE requests, the gateway:

1. Resolves the target URL via `resolve_target()` (first matching prefix in `SERVICE_MAP`).
2. Copies all request headers **except** `host` and `content-length` (stripped to avoid conflicts).
3. Injects `x-user-id: {user_id}` if the user is authenticated.
4. Forwards the request body as-is.
5. Returns the upstream response (status code, headers, body) verbatim.

### SSE (Server-Sent Events) Streaming

When the request includes `Accept: text/event-stream`:

1. The proxy uses `httpx`'s streaming API (`client.send(req, stream=True)`).
2. Returns a `StreamingResponse` that iterates over `resp.aiter_bytes()`.
3. Keeps the upstream response and `httpx.AsyncClient` open until downstream streaming finishes.
4. Media type is forced to `text/event-stream`.
5. No buffering — chunks are forwarded as they arrive from the upstream service.

This is used by `POST /agents/{id}/chat` for token streaming and remains important for future orchestrator streams.

### `x-user-id` Header Injection

For every authenticated request, the gateway injects:

```
x-user-id: 665f1a2b3c4d5e6f7a8b9c0d
```

This is how downstream services identify the calling user **without** re-decoding the JWT. Services should trust this header only when the request comes from the gateway (i.e., on the internal Docker network). In production, ensure no external traffic can reach services directly and spoof this header.

### Timeout

The httpx client uses a **120-second timeout** (`timeout=120.0`). This is intentionally long to accommodate LLM inference calls that may take tens of seconds to complete.

**Future considerations:**

- **Connection pooling:** Currently, a new `httpx.AsyncClient` is created per request. For higher throughput, create a shared client on startup (via FastAPI lifespan) and reuse it across requests.
- **Circuit breaker:** If a downstream service is consistently failing, the gateway should stop forwarding requests to it temporarily. Consider `tenacity` or a custom circuit breaker.
- **Request/response logging:** Add structured logging for proxied requests (method, path, target, status, latency) for observability.
- **CORS:** Allowed origins come from `CORS_ORIGINS`. Add a new public frontend origin there instead of editing code.

---

## Internal Architecture

```
gateway/
├── app/
│   ├── __init__.py
│   ├── config.py              ← Pydantic Settings (env vars)
│   ├── main.py                ← FastAPI app, middleware registration, health check
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py            ← JWTAuthMiddleware
│   │   └── rate_limit.py      ← RateLimitMiddleware
│   └── routes/
│       ├── __init__.py
│       └── proxy.py           ← SERVICE_MAP, resolve_target(), catch-all proxy route
├── Dockerfile
└── requirements.txt
```

| Module | Responsibility |
|--------|---------------|
| `config.py` | Loads env vars into typed `Settings` object (JWT secret, Redis URL, service URLs, rate limit) |
| `main.py` | Creates the FastAPI app, registers middleware in correct order, exposes `/health`, then mounts the proxy router |
| `middleware/auth.py` | JWT token validation, `request.state.user_id` injection, skip-auth path filtering |
| `middleware/rate_limit.py` | Redis-backed per-user hourly rate counter, `X-RateLimit-*` response headers |
| `routes/proxy.py` | Path-prefix → service URL resolution, header forwarding, SSE streaming, `x-user-id` injection |

---

## Configuration

All settings are loaded via Pydantic Settings from environment variables (and `.env` file as fallback).

| Env Var | Default | Description |
|---------|---------|-------------|
| `JWT_SECRET` | `change-me-in-production` | Signing key for JWT validation (**must match auth service**) |
| `REDIS_URL` | `redis://redis:6379` | Redis connection string for rate limiting |
| `RATE_LIMIT_PER_HOUR` | `50` | Max requests per authenticated user per hour |
| `AUTH_SERVICE_URL` | `http://auth:8001` | Auth service base URL (internal Docker network) |
| `AGENT_SERVICE_URL` | `http://agent:8002` | Agent service base URL |
| `BUSINESS_SERVICE_URL` | `http://business:8005` | Business service base URL |
| `KNOWLEDGE_SERVICE_URL` | `http://knowledge:8003` | Knowledge Base service base URL |
| `ORCHESTRATOR_SERVICE_URL` | `http://orchestrator:8004` | Orchestrator service base URL |

> **Critical:** `JWT_SECRET` must be identical between the auth service and the gateway. Auth signs tokens; the gateway validates them. A mismatch means every authenticated request returns 401.

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | >=0.115, <1.0 | Web framework, routing, middleware base |
| `uvicorn[standard]` | >=0.32, <1.0 | ASGI server |
| `httpx` | >=0.28, <1.0 | Async HTTP client for proxying (supports streaming) |
| `python-jose[cryptography]` | >=3.3, <4.0 | JWT decoding and validation |
| `redis[hiredis]` | >=5.2, <6.0 | Async Redis client for rate limiting |
| `pydantic-settings` | >=2.6, <3.0 | Typed settings from environment variables |

---

## Health Check

```
GET /health → {"status": "ok", "service": "gateway"}
```

The health endpoint is exempt from JWT auth and rate limiting (path starts with `/health`). It is registered before the catch-all proxy route so `GET /health` is handled by the gateway instead of being treated as an unmatched proxied path.

---

## Request Flow Examples

### Unauthenticated — Registration

```
Client  →  POST http://localhost:8010/auth/register  { email, password, name }

  JWTAuthMiddleware:  path starts with /auth → SKIP
  RateLimitMiddleware: no user_id → SKIP
  Proxy:  /auth → http://auth:8001/auth/register
    Auth Service creates user, returns tokens

Client  ←  201 { access_token, refresh_token, token_type }
```

### Unauthenticated — Token Refresh

`/auth/*` routes are exempt from JWT auth at the gateway and are forwarded directly to the Auth Service.

```
Client  →  POST http://localhost:8010/auth/refresh  { refresh_token }

  JWTAuthMiddleware:  path starts with /auth → SKIP
  RateLimitMiddleware: no user_id → SKIP
  Proxy:  /auth → http://auth:8001/auth/refresh
    Auth Service validates refresh token, returns new token pair

Client  ←  200 { access_token, refresh_token, token_type }
```

### Authenticated — Calling Agent Service

```
Client  →  GET http://localhost:8010/agents?limit=20&offset=0
            Authorization: Bearer eyJ...

  JWTAuthMiddleware:
    path /agents does NOT start with /auth or /health → VALIDATE
    decode token → user_id = "665f..."
    set request.state.user_id = "665f..."

  RateLimitMiddleware:
    user_id present → INCR rate:665f...:2026042518
    count = 3, limit = 50 → ALLOW
    add X-RateLimit-Limit: 50, X-RateLimit-Remaining: 47

  Proxy:
    /agents → http://agent:8002
    inject header: x-user-id: 665f...
    forward to http://agent:8002/agents?limit=20&offset=0

Client  ←  200 [{ "id": "...", "name": "My Accountant", ... }]
            X-RateLimit-Limit: 50
            X-RateLimit-Remaining: 47
```

### Authenticated — Company Workflow

Company, partner, invoice, and expense requests use the same gateway behavior as Agent requests: validate JWT, rate limit by user, inject `x-user-id`, and proxy to the target service. Business-domain prefixes route to the Business Service, while `/agents` and `/conversations` route to the Agent Service.

```
Client  →  POST http://localhost:8010/companies
            Authorization: Bearer eyJ...
            { "name": "Acme Ltd", "registration_number": "123", ... }

  Gateway:
    /companies → http://business:8005
    inject header: x-user-id: 665f...

Client  ←  201 { "id": "...", "user_id": "665f...", "name": "Acme Ltd", ... }
```

The gateway does not check whether a `company_id` or `partner_id` belongs to the user. Business Service owns business-domain ownership checks, Agent Service validates assigned agent companies through Business, and Knowledge Base Service validates document company scope through Business.

### Rate-Limited Request

```
Client  →  GET http://localhost:8010/agents
            Authorization: Bearer eyJ...

  JWTAuthMiddleware: valid → user_id set
  RateLimitMiddleware:
    INCR rate:665f...:2026042518 → count = 51, limit = 50 → DENY

Client  ←  429 { "detail": "Rate limit exceeded. Try again later." }
            Retry-After: 3600
```

### SSE Streaming

```
Client  →  POST http://localhost:8010/agents/{agent_id}/chat
            Authorization: Bearer eyJ...
            Accept: text/event-stream
            Content-Type: application/json
            { "message": "Say hello" }

  JWTAuthMiddleware: valid → user_id set
  RateLimitMiddleware: count within limit → ALLOW
  Proxy:
    detects Accept: text/event-stream
    opens streaming connection to http://agent:8002/agents/{agent_id}/chat
    returns StreamingResponse (chunks forwarded as they arrive)

Client  ←  200  text/event-stream
            event: token
            data: {"content": "Hello"}
            ...
```

---

## Running Locally

### Via Docker Compose (recommended)

```bash
docker compose up --build gateway redis auth mongodb
```

Compose publishes the gateway on `http://localhost:8010` (container port 8000). It requires Redis (for rate limiting) and Auth (so proxied auth requests work).

### Standalone (development)

```bash
cd gateway
pip install -r requirements.txt

# Make sure Redis is running and REDIS_URL is set
# Make sure JWT_SECRET matches the auth service
# Host port 8010 matches Compose. The container command stays --port 8000.
uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
```

---

## Testing

```bash
# Health check (no auth needed)
curl http://localhost:8010/health

# Register a user (no auth needed, proxied to auth service)
curl -X POST http://localhost:8010/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "secret1234", "name": "Test"}'

# Use the returned access_token for authenticated requests
TOKEN="eyJ..."

# Proxy to agent service (auth required)
curl "http://localhost:8010/agents?limit=20&offset=0" \
  -H "Authorization: Bearer $TOKEN"

# Check rate limit headers in response
curl -v "http://localhost:8010/agents?limit=20&offset=0" \
  -H "Authorization: Bearer $TOKEN" 2>&1 | grep -i x-ratelimit

# Hit a non-existent route → 404
curl http://localhost:8010/unknown/path \
  -H "Authorization: Bearer $TOKEN"
```

---

## Future Considerations

These are known gaps and planned improvements for later phases. Document them here so future implementers have full context.

| Area | Current State | Future Improvement |
|------|--------------|-------------------|
| **CORS** | `CORS_ORIGINS` (localhost `:3000`, `:3010`, droplet `:3010`) | Add HTTPS origins when a reverse proxy is introduced |
| **Connection pooling** | New `httpx.AsyncClient` per request | Shared client via FastAPI lifespan for better throughput |
| **Rate limiting** | Fixed 1-hour window | Sliding window (Redis sorted sets) for smoother limiting |
| **Per-endpoint limits** | Single global limit | Different limits for LLM-heavy vs. lightweight endpoints |
| **Circuit breaker** | None — failed upstream = 500 | Add circuit breaker to gracefully handle downstream outages |
| **Redis failure mode** | Unhandled exception (500) | Catch `ConnectionError`, decide fail-open vs. fail-closed |
| **Request logging** | None | Structured JSON logs (method, path, target, status, latency) |
| **Token refresh** | Client must handle refresh manually | Gateway could intercept expired-token 401s and attempt transparent refresh |
| **Admin bypass** | Rate limiting applies to all users | Exempt admin roles via a JWT claim |
| **WebSocket** | Not supported | Add WebSocket proxy for real-time features |
| **Request body size limit** | No limit enforced | Add a max body size for file upload protection |
| **Response caching** | None | Cache idempotent GET responses in Redis for frequently accessed data |
