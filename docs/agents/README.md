# Agents Documentation

This folder documents each concrete agent runtime and the shared contracts every agent must follow.

## Documents

| Document | Purpose |
|----------|---------|
| [`base-agent.md`](./base-agent.md) | Shared runtime contract, lifecycle, data boundaries, dependency graph, and per-agent documentation checklist. |
| [`accountant.md`](./accountant.md) | Accountant runtime workflows, tools, prompt rules, data flow, dependencies, guardrails, and verification. |
| [`inventory.md`](./inventory.md) | Inventory runtime workflows, tools, prompt rules, data flow, dependencies, guardrails, and verification. |

## Current Agent Catalog

| Agent type | Runtime class | Status | Detailed doc |
|------------|---------------|--------|--------------|
| `accountant` | `AccountantAgent` | Implemented | [`accountant.md`](./accountant.md) |
| `inventory` | `InventoryAgent` | Implemented | [`inventory.md`](./inventory.md) |
| `router` | `RouterAgent` | Implemented | [`router.md`](./router.md) |

## Documentation Standard

Every agent doc should include:

- Purpose and supported user workflows.
- Feature matrix and tool inventory.
- Runtime lifecycle and prompt rules.
- Data flow diagrams for reads, writes, and external calls.
- Dependency graph covering services, databases, providers, and external APIs.
- Data ownership boundaries.
- Configuration and environment variables.
- Guardrails, confirmations, and known limitations.
- Test coverage and manual verification steps.

Keep these docs aligned with `services/agent/app/runtime/registry.py`, the concrete runtime in `services/agent/app/runtime/`, and any tools under `services/agent/app/tools/`.
