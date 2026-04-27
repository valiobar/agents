# Orchestrator Service Dependency Graph

## Current Dependencies

```mermaid
graph TD
    Compose["docker-compose.yml"] --> Orch["Orchestrator Stub"]
    Orch --> Health["GET /health"]
    Orch -. startup .-> Redis[("Redis")]
    Gateway["API Gateway"] -. planned proxy .-> Orch
```

Current implementation has no runtime Redis usage yet, but Docker Compose starts the service after Redis is healthy.

## Target Dependency Graph

```mermaid
graph TD
    Gateway["API Gateway"] -->|"HTTP /orchestrator"| Orch["Orchestrator Service"]

    subgraph internal ["Orchestrator Service"]
        Routes["routes/"]
        Services["services/"]
        Streams["streams/"]
        Models["models/"]
    end

    Orch --> Routes
    Routes --> Services
    Services --> Streams
    Services --> Models
    Streams --> Redis[("Redis Streams")]
    Services -. task dispatch .-> Agent["Agent Service"]
```

## Dependency Matrix

| Dependency | Type | Status | Purpose |
|------------|------|--------|---------|
| API Gateway | inbound HTTP/SSE | Planned | Workflow requests |
| Redis | stream store | Planned runtime, configured startup | Task and result streams |
| Agent Service | HTTP / worker integration | Planned | Task execution |

## Owned Data

| Store | Purpose |
|-------|---------|
| Redis `stream:*_tasks` | Task dispatch |
| Redis `stream:results` | Agent result aggregation |

The Orchestrator currently owns no MongoDB collections.
