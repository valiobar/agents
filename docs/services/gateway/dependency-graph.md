# API Gateway Dependency Graph

## Dependency Graph

```mermaid
graph TD
    Client["Frontend / Client"] --> Gateway["API Gateway"]
    Gateway --> Redis[("Redis")]
    Gateway --> Auth["Auth Service"]
    Gateway --> Agent["Agent Service"]
    Gateway --> Knowledge["Knowledge Base Service"]
    Gateway --> Orchestrator["Orchestrator Service"]

    subgraph internal ["Gateway internals"]
        Main["main.py"]
        AuthMW["middleware/auth.py"]
        RateMW["middleware/rate_limit.py"]
        Proxy["routes/proxy.py"]
        Config["config.py"]
    end

    Gateway --> Main
    Main --> AuthMW
    Main --> RateMW
    Main --> Proxy
    AuthMW --> Config
    RateMW --> Config
    RateMW --> Redis
    Proxy --> Config
    Proxy --> Auth
    Proxy --> Agent
    Proxy --> Knowledge
    Proxy --> Orchestrator
```

## Route Dependencies

| Path Prefix | Target | Status |
|-------------|--------|--------|
| `/auth/*` | Auth Service | Implemented |
| `/agents/*` | Agent Service | Implemented |
| `/conversations/*` | Agent Service | Implemented |
| `/invoices/*` | Agent Service | Implemented |
| `/expenses/*` | Agent Service | Implemented |
| `/documents` | Knowledge Base Service | Implemented |
| `/retrieve` | Knowledge Base Service | Implemented |
| `/orchestrator/*` | Orchestrator Service | Stub target |

## Runtime Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| Redis | database/cache | Rate limit counters |
| Auth Service | HTTP | Authentication endpoints |
| Agent Service | HTTP/SSE | Agent and finance routes |
| Knowledge Base Service | HTTP | Documents and retrieval |
| Orchestrator Service | HTTP/SSE | Workflow routes |
| python-jose | package | JWT validation |
| httpx | package | Async proxying |
