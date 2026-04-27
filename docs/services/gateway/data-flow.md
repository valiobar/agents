# API Gateway Data Flow

## Request Lifecycle

```mermaid
sequenceDiagram
    participant Client
    participant AuthMW as JWTAuthMiddleware
    participant RateMW as RateLimitMiddleware
    participant Redis
    participant Proxy
    participant Service as Target Service

    Client->>AuthMW: HTTP request
    AuthMW->>AuthMW: skip or validate JWT
    AuthMW->>RateMW: request with user_id if authenticated
    RateMW->>Redis: INCR rate key if authenticated
    Redis-->>RateMW: current count
    RateMW->>Proxy: allowed request
    Proxy->>Service: forward request with x-user-id
    Service-->>Proxy: upstream response
    Proxy-->>Client: response
```

## Public Auth Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Auth

    Client->>Gateway: POST /auth/login
    Gateway->>Gateway: skip JWT auth
    Gateway->>Gateway: skip rate limiting because no user_id
    Gateway->>Auth: proxy /auth/login
    Auth-->>Gateway: token pair
    Gateway-->>Client: token pair
```

## Protected Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Redis
    participant Service

    Client->>Gateway: GET /agents + Bearer access token
    Gateway->>Gateway: validate JWT and extract sub
    Gateway->>Redis: INCR rate:{user_id}:{hour}
    Redis-->>Gateway: count within limit
    Gateway->>Service: forward with x-user-id
    Service-->>Gateway: JSON response
    Gateway-->>Client: JSON response + rate limit headers
```

## SSE Proxy Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Service

    Client->>Gateway: POST route with Accept: text/event-stream
    Gateway->>Service: open upstream streaming request
    loop chunks
        Service-->>Gateway: SSE bytes
        Gateway-->>Client: same SSE bytes
    end
```

## Data Written By Gateway

| Data | Store | Purpose |
|------|-------|---------|
| `rate:{user_id}:{hour_bucket}` | Redis | Per-user hourly rate counter |

The gateway owns no MongoDB collections and should not persist domain data.
