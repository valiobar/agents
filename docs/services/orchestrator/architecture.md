# Orchestrator Service Architecture

## Current State

The Orchestrator Service is currently a stub with `GET /health` only. Docker Compose, Dockerfile, and FastAPI app shell exist; workflow coordination is planned.

## Responsibility

The Orchestrator coordinates multi-agent or long-running workflows.

Planned responsibilities:

- Accept workflow requests from the API Gateway.
- Create tasks for one or more agent workers.
- Publish tasks to Redis Streams.
- Consume result streams.
- Aggregate partial outputs.
- Stream progress back to clients when needed.

## Target Layers

```text
routes/ -> services/ -> streams/ -> models/
```

| Layer | Responsibility |
|-------|----------------|
| `routes/` | Workflow HTTP/SSE endpoints |
| `services/` | Task planning, routing, aggregation |
| `streams/` | Redis Stream producers/consumers |
| `models/` | Workflow, task, and result schemas |

## Main Patterns

- **Coordinator pattern:** orchestrates work without owning agent business logic.
- **Event-driven pattern:** Redis Streams carry task and result messages.
- **Streaming pattern:** long workflows can report progress via SSE through the gateway.

## Restrictions

- Keep agent-specific logic in the Agent Service.
- Do not introduce another queue unless an architecture decision replaces Redis Streams.
- Keep stream messages small and serializable.
- Do not put secrets, provider keys, or full prompts in stream payloads.
- Do not access MongoDB collections owned by other services directly.
