# Deployment Guide

## Prerequisites

| Tool | Minimum Version | Check |
|------|:--------------:|-------|
| Docker | 24.0 | `docker --version` |
| Docker Compose | 2.20 | `docker compose version` |
| Git | any | `git --version` |

Optional:

- GCP project with OAuth 2.0 credentials — required only if you want Google sign-in.
- MongoDB Compass — useful for inspecting the database during development.
- Docker Compose with `up --watch` support — required only for automatic dependency-file rebuilds in development mode.

## Quick Start

### 1. Clone and configure

```bash
git clone <repository-url>
cd agents
cp .env.example .env
```

Open `.env` and set at least `JWT_SECRET` to a strong random string:

```bash
# generate a random secret (macOS / Linux)
openssl rand -hex 32
```

### 2. Start the stack

```bash
docker compose up --build
```

On first run this will:

1. Pull infrastructure images (`mongo:7`, `redis:7-alpine`, `chromadb/chroma:latest`).
2. Build application images from each service's `Dockerfile`.
3. Start all containers in dependency order (see [Startup Order](#startup-order)).

For day-to-day development with hot reload, use the dev override:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Python services run `uvicorn --reload`, and the frontend runs `next dev`. Source changes are bind-mounted into the matching container.

### 3. Verify health

```bash
curl http://localhost:8000/health   # → {"status":"ok","service":"gateway"}
curl -I http://localhost:3000/login # → HTTP 200 from the frontend
```

Only the frontend and gateway are published to the host. Internal service health can be checked from inside the Docker network, for example:

```bash
docker compose exec auth python - <<'PY'
import urllib.request
print(urllib.request.urlopen("http://localhost:8001/health").read().decode())
PY

docker compose exec gateway python - <<'PY'
import urllib.request
print(urllib.request.urlopen("http://business:8005/health").read().decode())
PY
```

---

## Architecture at a Glance

```
                         ┌──────────────────────────────────────────┐
 Host :3000 ────────────►│ Frontend :3000                           │
                         │        │                                 │
 Host :8000 ────────────►│        ▼                                 │
                         │  ┌─────────┐                             │
                         │  │ Gateway  │──► Auth       (:8001)      │
                         │  │  :8000   │──► Agent      (:8002)      │
                         │  │         │──► Knowledge  (:8003)      │
                         │  │         │──► Orchestr.  (:8004)      │
                         │  │         │──► Business   (:8005)      │
                         │  └────┬────┘                             │
                         │       │                                  │
                         │  ┌────▼────┐  ┌──────────┐  ┌─────────┐ │
                         │  │  Redis  │  │ MongoDB  │  │ChromaDB │ │
                         │  │  :6379  │  │  :27017  │  │  :8000  │ │
                         │  └─────────┘  └──────────┘  └─────────┘ │
                         └──────────────────────────────────────────┘
```

Every container sits on a single Docker bridge network (`agents-network`). Service names (`gateway`, `auth`, `redis`, `mongodb`, etc.) are DNS hostnames on that network, so `http://auth:8001` resolves inside any container.

---

## Port Mapping

| Service | Internal Port | Host Port | Exposed to clients |
|---------|:------------:|:---------:|:------------------:|
| Frontend | 3000 | 3000 | **Yes** |
| Gateway | 8000 | 8000 | **Yes** |
| Auth | 8001 | not published | No |
| Agent | 8002 | not published | No |
| Knowledge | 8003 | not published | No |
| Orchestrator | 8004 | not published | No |
| Business | 8005 | not published | No |
| MongoDB | 27017 | not published | No |
| Redis | 6379 | not published | No |
| ChromaDB | 8000 | not published | No |

Only the frontend and gateway are exposed for the user-facing path. All other services are reachable by Docker DNS names on `agents-network`.

> **ChromaDB port note:** ChromaDB listens on port 8000 inside the container, but it is not published to the host in the default compose file. Containers use `CHROMADB_HOST=chromadb` and `CHROMADB_PORT=8000`.

---

## Startup Order

Docker Compose `depends_on` with health-check conditions guarantees the following boot sequence:

```
Phase 1 — Infrastructure
  mongodb   ← starts first, health check: mongosh ping
  redis     ← starts first, health check: redis-cli ping
  chromadb  ← starts independently (no health check)

Phase 2 — Application services (only after their deps are healthy)
  auth         ← waits for mongodb (healthy)
  business     ← waits for mongodb (healthy)
  gateway      ← waits for redis (healthy) + auth (started) + business (started)
  agent        ← waits for mongodb (healthy)
  knowledge    ← waits for mongodb (healthy) + chromadb (started)
  orchestrator ← waits for redis (healthy)
  frontend     ← waits for gateway (started)
```

**`service_healthy`** means the container's health check command is returning success. For MongoDB that is `mongosh --eval "db.runCommand('ping').ok"` (runs every 10 s, up to 5 retries). For Redis it is `redis-cli ping` expecting `PONG`.

**`service_started`** means the container process is running — a weaker guarantee used for services that do not define a health check in the compose file (ChromaDB, Auth when depended upon by Gateway).

---

## Volumes

| Volume | Mounted in | Path inside container | Purpose |
|--------|-----------|----------------------|---------|
| `mongodb_data` | mongodb | `/data/db` | Database files |
| `redis_data` | redis | `/data` | RDB/AOF persistence |
| `chroma_data` | chromadb | `/chroma/chroma` | Vector embeddings |

Volumes survive `docker compose down`. Data is only deleted when you explicitly pass `-v`:

```bash
docker compose down      # containers removed, data kept
docker compose down -v   # containers AND volumes removed — full reset
```

### Targeted Company-Scope Test Data Reset

The company-scope rollout includes a one-off Agent Service utility for local or test environments where existing MongoDB records are disposable. It deletes user-scoped Agent/Knowledge metadata that may not have `company_id`, then optionally creates a fresh `Default Company` for each reset user.

This command is destructive and must not be wired into service startup or run against production data. It only resets MongoDB collections, including Business-owned company, partner, invoice, expense, and counter data; use `docker compose down -v` when you also need to clear Redis or ChromaDB volumes.

Preview the records that would be deleted for one user:

```bash
docker compose exec agent python -m app.scripts.reset_test_data \
  --user-id "$USER_ID" \
  --dry-run
```

Reset one user's test data and seed a default company:

```bash
docker compose exec agent python -m app.scripts.reset_test_data \
  --user-id "$USER_ID" \
  --confirm-destroy-test-data
```

Reset all users without seeding default companies:

```bash
docker compose exec agent python -m app.scripts.reset_test_data \
  --all-users \
  --no-seed-default-company \
  --confirm-destroy-test-data
```

The utility deletes user-scoped records from `conversations`, `agents`, `invoices`, `expenses`, `documents`, `partners`, and `companies`, plus invoice counter records whose keys belong to the reset user.

---

## Environment Variables

All application services read from a single `.env` file via `env_file: .env` in `docker-compose.yml`.

| Variable | Default | Used by | Description |
|----------|---------|---------|-------------|
| `MONGODB_URL` | `mongodb://mongodb:27017` | auth, agent, business, knowledge | MongoDB connection string |
| `DB_NAME` | `agents` | auth, agent, business, knowledge | Database name |
| `REDIS_URL` | `redis://redis:6379` | gateway, orchestrator | Redis connection string |
| `CHROMADB_HOST` | `chromadb` | knowledge | ChromaDB hostname |
| `CHROMADB_PORT` | `8000` | knowledge | ChromaDB internal port used by containers |
| `JWT_SECRET` | *(must set)* | auth, gateway | Signing key for JWTs — must match in both services |
| `JWT_ACCESS_EXPIRE_MINUTES` | `30` | auth | Access token TTL |
| `JWT_REFRESH_EXPIRE_DAYS` | `7` | auth | Refresh token TTL |
| `GOOGLE_CLIENT_ID` | *(empty)* | auth | GCP OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | *(empty)* | auth | GCP OAuth client secret |
| `OPENAI_API_KEY` | *(empty)* | knowledge, agent (future) | OpenAI API key for embeddings and future LLM calls |
| `ANTHROPIC_API_KEY` | *(empty)* | agent (Phase 2+) | Anthropic API key |
| `RATE_LIMIT_PER_HOUR` | `50` | gateway | Max requests per user per hour |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | knowledge | OpenAI embedding model |
| `EMBEDDING_BATCH_SIZE` | `64` | knowledge | Texts per embedding request |
| `CHUNK_SIZE` | `800` | knowledge | Document chunk size |
| `CHUNK_OVERLAP` | `200` | knowledge | Overlap between chunks |
| `MAX_UPLOAD_SIZE_BYTES` | `10485760` | knowledge | Max upload size |
| `TAX_DOCS_PATH` | `data/knowledgebase/tax` | knowledge | Tax preload source directory |
| `PRELOAD_TAX_DOCS` | `false` | knowledge | Enables startup load into ChromaDB `global_tax` |
| `BUSINESS_SERVICE_URL` | `http://business:8005` | gateway, agent, knowledge | Internal Business Service URL for domain routing, Agent tools, and Knowledge company ownership validation |
| `BUSINESS_TIMEOUT_SECONDS` | `15.0` | agent | Per-request timeout for Agent-to-Business calls |
| `NEXT_PUBLIC_GATEWAY_URL` | `http://localhost:8000` | frontend browser | Public gateway URL used by client-side fetches and SSE |
| `GATEWAY_URL` | `http://gateway:8000` | frontend server runtime | Internal gateway URL for NextAuth server-side requests in Docker |
| `NEXTAUTH_URL` | `http://localhost:3000` | frontend | Public frontend URL used by NextAuth callbacks |
| `NEXTAUTH_SECRET` | *(must set)* | frontend | Secret used to sign NextAuth JWT/session cookies |

> **Critical:** `JWT_SECRET` must be identical for `auth` and `gateway`. Auth signs tokens with it; the gateway validates tokens with it. A mismatch means every authenticated request returns 401.

> **ChromaDB ports:** containers must use `CHROMADB_PORT=8000`, the ChromaDB internal port. ChromaDB is not published to the host by default.

---

## Frontend Runtime

The frontend runs on `http://localhost:3000` and all backend traffic goes through the gateway on `http://localhost:8000`.

Run locally:

```bash
cd frontend
npm install
npm run dev
```

Run with Docker Compose:

```bash
docker compose up --build frontend gateway auth business agent knowledge mongodb redis chromadb
```

Run the frontend in Docker development mode:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build frontend gateway auth business agent knowledge mongodb redis chromadb
```

Frontend verification commands:

```bash
cd frontend
npm run typecheck
npm run lint
npm run build
```

Common frontend failures:

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Browser says CORS preflight failed | Gateway is not running with CORS for `http://localhost:3000` | Rebuild/restart `gateway` |
| Login redirects back to login | `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, or `GATEWAY_URL` is missing/mismatched | Check `.env` and rebuild `frontend` |
| Chat emits SSE `error` about provider API key | Agent provider key is missing | Set `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. |
| Document upload returns 500 during embedding | `OPENAI_API_KEY` is missing or invalid | Set a valid OpenAI key before uploading |

---

## Running Knowledge Base Phase 2

Start only the services needed for authenticated Knowledge Base requests:

```bash
docker compose up --build mongodb chromadb auth business gateway knowledge
```

Required environment:

```env
MONGODB_URL=mongodb://mongodb:27017
DB_NAME=agents
CHROMADB_HOST=chromadb
CHROMADB_PORT=8000
BUSINESS_SERVICE_URL=http://business:8005
JWT_SECRET=change-me-to-a-strong-random-value
OPENAI_API_KEY=sk-...
```

Use the gateway for client requests:

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/documents?company_id=$COMPANY_ID" \
  -H "Authorization: Bearer $TOKEN"
```

Knowledge Base common failures:

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| OpenAI authentication error | Missing or invalid `OPENAI_API_KEY` | Add a valid key to `.env` before uploading or retrieving |
| Chroma connection refused | Container is using the host-mapped Chroma port | Set `CHROMADB_PORT=8000` |
| Business validation unavailable | `business` is not running or `BUSINESS_SERVICE_URL` is wrong | Start `business` and verify `http://business:8005/health` from another container |
| `415 Unsupported document type` | Unsupported upload content type | Use PDF, text, or Markdown |
| Empty retrieval from `global_tax` | No tax docs loaded or `PRELOAD_TAX_DOCS=false` | Add supported files under `TAX_DOCS_PATH` and enable preload |
| `404 Company not found` on document upload/retrieve | `company_id` is missing, invalid, or belongs to another user | Create/select an owned company through `/companies` first |
| `401` from `/documents` | Missing or invalid gateway token | Register/login through `/auth/*` and pass the access token |

---

## Common Operations

### View logs

```bash
docker compose logs              # all services
docker compose logs auth         # single service
docker compose logs -f gateway   # follow (tail) in real time
```

### Rebuild after code changes

```bash
docker compose up --build              # rebuild everything that changed
docker compose build auth && docker compose up -d auth   # rebuild + restart one service
```

Docker layer caching means only layers affected by your code change are rebuilt. `requirements.txt` is copied first (see each Dockerfile), so dependency install is cached unless you add a new package.

### Development hot reload

Use the dev override while actively editing code:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

This mounts each service's source code into its container. FastAPI services restart through `uvicorn --reload`; the frontend runs `npm run dev`.

To also rebuild the affected image automatically when dependency files or Dockerfiles change, run Compose in watch mode:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml watch
```

The watch rules rebuild only the service whose `requirements.txt`, `package.json`, `package-lock.json`, or `Dockerfile` changed.

### Restart a single service

```bash
docker compose restart auth
```

### Run a one-off command inside a container

```bash
docker compose exec mongodb mongosh                          # MongoDB shell
docker compose exec redis redis-cli                          # Redis CLI
docker compose exec auth python -c "from app.config import settings; print(settings)"
```

### Scale (for testing)

```bash
docker compose up --scale agent=3    # run 3 agent containers
```

Not useful in Phase 1 (no load balancer configured), but supported by Compose.

---

## Health Check Endpoints

Every application service exposes `GET /health`, but only the gateway health endpoint is published to the host by default:

| URL | Expected Response |
|-----|-------------------|
| `http://localhost:8000/health` | `{"status": "ok", "service": "gateway"}` |

Check internal service health from inside the Docker network or by inspecting container logs:

```bash
docker compose exec auth python - <<'PY'
import urllib.request
print(urllib.request.urlopen("http://localhost:8001/health").read().decode())
PY
```

For infrastructure containers, use the built-in checks:

```bash
docker compose exec mongodb mongosh --eval "db.runCommand('ping')"
docker compose exec redis redis-cli ping
docker compose logs chromadb
```

---

## Request Flow (end-to-end)

Understanding how a request travels through the stack:

```
Client
  │
  ▼  POST http://localhost:8000/auth/register
┌─────────┐
│ Gateway  │  1. JWTAuthMiddleware: path starts with /auth → skip auth
│  :8000   │  2. RateLimitMiddleware: no user_id yet → skip rate limit
│          │  3. Proxy: /auth → http://auth:8001/auth/register
└────┬─────┘
     │  HTTP (internal network)
     ▼
┌─────────┐
│  Auth    │  4. Creates user in MongoDB, returns JWT tokens
│  :8001   │
└────┬─────┘
     │  response bubbles back
     ▼
Client receives { access_token, refresh_token }
```

Authenticated requests add two more steps:

```
Client
  │
  ▼  GET http://localhost:8000/agents?limit=20&offset=0  (Authorization: Bearer <token>)
┌─────────┐
│ Gateway  │  1. JWTAuthMiddleware: decode token → set request.state.user_id
│  :8000   │  2. RateLimitMiddleware: INCR rate:<user_id>:<hour> in Redis
│          │  3. Proxy: /agents → http://agent:8002, inject x-user-id header
└────┬─────┘
     │
     ▼
┌─────────┐
│  Agent   │  4. Returns the user's agent list
│  :8002   │
└──────────┘
```

---

## Troubleshooting

### Container won't start / exits immediately

```bash
docker compose logs <service>   # check for Python tracebacks or config errors
docker compose ps               # shows container status (Up, Exit 1, etc.)
```

### "Connection refused" to MongoDB

MongoDB's health check takes up to 50 seconds (10 s interval × 5 retries). If an app starts before Mongo is healthy, `depends_on: condition: service_healthy` should prevent this. If you still see connection errors:

```bash
docker compose logs mongodb     # look for startup errors
docker compose restart auth     # restart the affected service
```

### JWT validation fails (401 on every request)

`JWT_SECRET` must be the same value for both `auth` and `gateway`. Both read it from the shared `.env` file, so this usually means `.env` was not created or the variable is empty.

```bash
docker compose exec auth python -c "from app.config import settings; print(settings.jwt_secret)"
docker compose exec gateway python -c "from app.config import settings; print(settings.jwt_secret)"
```

Both should print the same value.

### Rate limiting not working

The gateway depends on Redis. If Redis is down, the rate limiter middleware will throw connection errors.

```bash
docker compose logs redis
docker compose exec redis redis-cli ping   # should return PONG
```

### Port already in use

```bash
# find what's using the port (e.g. 8000)
lsof -i :8000

# either stop that process or change the host port in docker-compose.yml:
# ports:
#   - "9000:8000"   # map to 9000 on host instead
```

### Stale images after dependency changes

If you added a new Python package to `requirements.txt` but the container still can't import it:

```bash
docker compose build --no-cache <service>
docker compose up -d <service>
```

The `--no-cache` flag forces a full rebuild, ignoring Docker's layer cache.

### Full reset

```bash
docker compose down -v           # stop everything, delete all volumes
docker compose up --build        # rebuild from scratch
```

This destroys all data (MongoDB documents, Redis keys, ChromaDB embeddings).

---

## Production Considerations

This setup is designed for **local development**. For production deployment, consider:

- **Remove dev port mappings.** Only expose `gateway:8000` (and `frontend:3000` when available). Internal services and databases should not be reachable from outside the Docker network.
- **Use external managed databases.** Replace the containerized MongoDB and Redis with managed services (MongoDB Atlas, AWS ElastiCache, etc.) for reliability, backups, and scaling.
- **Set strong secrets.** Generate `JWT_SECRET` with `openssl rand -hex 64`. Never use the default placeholder.
- **Enable TLS.** Put a reverse proxy (Nginx, Traefik, Caddy) in front of the gateway to terminate HTTPS.
- **Add logging and monitoring.** Integrate structured logging (e.g., JSON logs) and forward to a log aggregation service. Add Prometheus metrics or a health-check monitoring service.
- **Container orchestration.** For multi-node deployments, migrate from Docker Compose to Kubernetes or Docker Swarm with proper resource limits, replica counts, and rolling updates.
- **CI/CD pipeline.** Automate image builds, run tests, and deploy on merge to main.
