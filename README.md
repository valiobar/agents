# Agents

Microservice platform for creating and orchestrating AI agents (starting with an **Accountant Agent**).

- **Frontend**: Next.js + NextAuth *(planned)*
- **Backend**: FastAPI microservices
- **Data**: MongoDB (structured) + ChromaDB (vector search for RAG)
- **Infra**: Redis (rate limiting now; Streams for future orchestration)
- **AI runtime**: LangChain `AgentExecutor` with provider support for OpenAI, Anthropic, DeepSeek, and Ollama

### Architecture (high level)

All frontend traffic goes through the **API Gateway**. The gateway validates JWTs, enforces rate limits, injects `x-user-id`, and proxies requests to internal services. Internal services should not be exposed to the host.

- **Frontend** → **Gateway** → {Auth, Agent, Knowledge, Orchestrator}
- The **Agent Service** owns agent CRUD, conversation persistence, and SSE chat streaming.
- During chat, LangChain `AgentExecutor` executes model-requested `rag_search` or `calculator` tool calls, feeds tool results back to the model, and streams final user-facing chunks.
- New conversations are created only after provider/runtime setup succeeds; `done` is emitted only after messages are persisted.

### Services and ports

| Service | Port | Exposed to host | Purpose |
|---|---:|:---:|---|
| `frontend` | 3000 | ✅ | Web app (dashboard, chat, forms) |
| `gateway` | 8000 | ✅ | JWT validation, routing, rate limiting, SSE pass-through |
| `auth` | 8001 | ❌ | Register/login, Google OAuth callback, JWT issuance |
| `agent` | 8002 | ❌ | Agent CRUD, LangChain chat runtime, RAG/calculator tools, conversations |
| `knowledge` | 8003 | ❌ | Document ingestion, ChromaDB management, RAG retrieval |
| `orchestrator` | 8004 | ❌ | Multi-agent coordination (stub) |
| `mongodb` | 27017 | ❌ | Users, agents, conversations, document metadata |
| `redis` | 6379 | ❌ | Gateway rate limiting now; Streams later |
| `chromadb` | 8005 | ❌ | Vector store for embeddings (RAG) |

### Repository structure

```
gateway/          # FastAPI API gateway (JWT, proxy, rate limit, SSE pass-through)
services/
  auth/           # Auth Service (FastAPI)
  agent/          # Agent Service (FastAPI + LangChain)
  knowledge/      # Knowledge Base Service (FastAPI + ChromaDB)
  orchestrator/   # Orchestrator Service stub
frontend/         # Next.js app (planned)
docs/             # Architecture, API, service, and data-model documentation
plans/            # Implementation plans
```

### Current status (what exists in this repo today)

- **Implemented**:
  - Docker Compose infrastructure for MongoDB, Redis, ChromaDB, and services.
  - Auth Service: registration, login, Google OAuth callback, JWT issuance, refresh.
  - API Gateway: JWT validation, rate limiting, proxy routing, SSE pass-through.
  - Knowledge Base Service: document ingestion, ChromaDB vectors, retrieval.
  - Agent Service core: agent CRUD, conversations, provider factory, Accountant Agent runtime, `rag_search`, `calculator`, SSE chat.
- **Planned**:
  - Frontend implementation.
  - Invoice/expense APIs and LangChain financial tools.
  - Orchestrator activation with Redis Streams.

### Running locally

Preferred full-stack startup:

```bash
cp .env.example .env
docker compose up --build
```

Docker development mode with hot reload:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Use `npm run dev:docker:watch` from `frontend/`, or `docker compose -f docker-compose.yml -f docker-compose.dev.yml watch` from the repo root, to automatically rebuild the affected service when dependency files or Dockerfiles change.

For focused service work, run services individually.

Auth service:

```bash
cd services/auth
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Agent service:

```bash
cd services/agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

Gateway:

```bash
cd gateway
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

### Docs

- **System architecture**: [`docs/architecture/overview.md`](docs/architecture/overview.md)
- **System dependency graph**: [`docs/architecture/dependency-graph.md`](docs/architecture/dependency-graph.md)
- **API reference**: [`docs/api/README.md`](docs/api/README.md)
- **Agent Service overview**: [`docs/services/agent/README.md`](docs/services/agent/README.md)
- **Agent Service architecture**: [`docs/services/agent/architecture.md`](docs/services/agent/architecture.md)
- **Agent Service data flow**: [`docs/services/agent/data-flow.md`](docs/services/agent/data-flow.md)
- **Agent Service dependencies**: [`docs/services/agent/dependency-graph.md`](docs/services/agent/dependency-graph.md)
- **Agent data models**: [`docs/data-models/agent.md`](docs/data-models/agent.md)
- **Knowledge Base docs**: [`docs/services/knowledge/README.md`](docs/services/knowledge/README.md)
- **Frontend architecture**: [`docs/frontend/architecture.md`](docs/frontend/architecture.md)

