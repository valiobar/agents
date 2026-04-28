# API Gateway Architecture

## Current State

The API Gateway is implemented. It validates JWTs, applies Redis-backed rate limiting, routes requests to internal services, injects `x-user-id`, and supports SSE pass-through.

## Responsibility

The gateway is the single backend entry point for frontend and external clients.

Implemented responsibilities:

- Skip auth for `/auth/*` and `/health`.
- Validate Bearer access tokens for protected routes.
- Store `request.state.user_id`.
- Rate limit authenticated users with Redis.
- Proxy requests by path prefix.
- Inject `x-user-id` into authenticated upstream requests.
- Stream SSE responses without buffering.

## Layers

```text
main.py
  -> middleware/auth.py
  -> middleware/rate_limit.py
  -> routes/proxy.py
  -> config.py
```

| Module | Responsibility |
|--------|----------------|
| `main.py` | FastAPI app, middleware registration, health endpoint |
| `middleware/auth.py` | JWT validation and user id extraction |
| `middleware/rate_limit.py` | Redis rate limit counter |
| `routes/proxy.py` | Path routing, header forwarding, SSE pass-through |
| `config.py` | Environment-driven settings |

## Main Patterns

- **API Gateway pattern:** single public API entry point.
- **Middleware chain:** cross-cutting concerns run before proxying.
- **Reverse proxy:** gateway forwards requests without domain logic.
- **SSE pass-through:** streaming responses are not buffered.

## Route Ownership Baseline

Current routing still sends all implemented business-domain APIs to Agent Service. The Business Service split will change only the target service for selected prefixes; public URLs stay stable.

| Prefix | Current target | Target after Business split | Notes |
|--------|----------------|-----------------------------|-------|
| `/auth` | Auth Service | Auth Service | Public auth routes remain JWT-skip routes. |
| `/agents` | Agent Service | Agent Service | Agent CRUD and SSE chat runtime. |
| `/conversations` | Agent Service | Agent Service | Persisted chat history. |
| `/companies` | Agent Service | Business Service | Planned domain ownership move. |
| `/partners` | Agent Service | Business Service | Planned domain ownership move. |
| `/invoices` | Agent Service | Business Service | Planned domain ownership move. |
| `/expenses` | Agent Service | Business Service | Planned domain ownership move. |
| `/documents` | Knowledge Base Service | Knowledge Base Service | Document lifecycle. |
| `/retrieve` | Knowledge Base Service | Knowledge Base Service | RAG retrieval. |
| `/orchestrator` | Orchestrator Service | Orchestrator Service | Stub/planned orchestration. |

Smoke checks for the split:

- `GET http://localhost:8000/health` verifies the gateway remains public and healthy.
- `GET http://business:8005/health` verifies the future Business container inside the Docker network once Phase 1 adds it.
- `GET http://localhost:8000/companies` verifies the gateway contract before and after the target switch.
- `POST /agents/{agent_id}/chat` with a prompt that invokes `query_expenses` verifies Agent runtime and tool routing still work.

## Restrictions

- Do not add business logic to the gateway.
- Do not read/write MongoDB business collections.
- Do not call LLM providers.
- Keep refresh token validation in Auth Service.
- Keep `JWT_SECRET` aligned with Auth Service.
- Add public routes intentionally through auth skip rules.
