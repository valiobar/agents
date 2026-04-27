# Orchestrator Service Data Flow

## Current Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Orch as Orchestrator

    Client->>Gateway: GET /orchestrator/health
    Gateway->>Orch: proxy to Orchestrator Service
    Orch-->>Gateway: {"status":"ok","service":"orchestrator"}
    Gateway-->>Client: health response
```

Only health checks are implemented.

## Planned Workflow Start Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Orch as Orchestrator
    participant Redis

    Client->>Gateway: POST /orchestrator/run + access token
    Gateway->>Orch: forward with x-user-id
    Orch->>Orch: create workflow plan
    Orch->>Redis: XADD task stream
    Orch-->>Gateway: workflow id or SSE stream
    Gateway-->>Client: workflow id or SSE stream
```

## Planned Task Execution Flow

```mermaid
sequenceDiagram
    participant Orch as Orchestrator
    participant Redis
    participant Worker as Agent Worker

    Orch->>Redis: XADD task
    Worker->>Redis: XREADGROUP task
    Worker->>Worker: execute assigned agent work
    Worker->>Redis: XADD result
    Orch->>Redis: XREADGROUP result
    Orch->>Orch: aggregate result
```

## Planned Progress Streaming Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Orch as Orchestrator
    participant Redis

    Client->>Gateway: POST /orchestrator/run, Accept: text/event-stream
    Gateway->>Orch: open upstream stream
    Orch->>Redis: publish tasks
    loop workflow progress
        Orch->>Redis: read partial results
        Orch-->>Gateway: SSE progress event
        Gateway-->>Client: SSE progress event
    end
    Orch-->>Gateway: SSE done event
    Gateway-->>Client: SSE done event
```

## Write Paths

| Data | Write Path |
|------|------------|
| Task messages | Orchestrator service -> Redis Streams |
| Result messages | Agent workers -> Redis Streams |
| Workflow history | Not owned yet; add a persistence decision before using MongoDB |
