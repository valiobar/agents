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

## Restrictions

- Do not add business logic to the gateway.
- Do not read/write MongoDB business collections.
- Do not call LLM providers.
- Keep refresh token validation in Auth Service.
- Keep `JWT_SECRET` aligned with Auth Service.
- Add public routes intentionally through auth skip rules.
