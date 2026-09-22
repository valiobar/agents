# Production deploy (Compose-on-VPS)

Agents deploys the same way as [Hint](https://github.com/valiobar/hint) and [vbar-viber-bot](https://github.com/valiobar/vbar-viber-bot): GitHub Actions builds images, pushes them to GHCR, then SSH-runs `deploy.sh` on a DigitalOcean droplet. **The VPS never builds app images.**

| Piece | Path |
|---|---|
| Workflow | `.github/workflows/deploy.yml` |
| Server script | `deploy.sh` (repo root) |
| Production compose | `infrastructure/docker-compose.yml` |
| Env template | `.env.example` |
| Local compose | `docker-compose.yml` (`docker compose up --build`) |

Local development still builds from source. Production pulls `ghcr.io/valiobar/agents-<service>:${IMAGE_TAG}`.

Target droplet for this stack: **159.89.26.67** (the same host as Hint and vbar-viber-bot). Checkout path: `~/agents`.

## Images

| Compose service | GHCR image |
|---|---|
| `gateway` | `ghcr.io/valiobar/agents-gateway` |
| `auth` | `ghcr.io/valiobar/agents-auth` |
| `business` | `ghcr.io/valiobar/agents-business` |
| `agent` | `ghcr.io/valiobar/agents-agent` |
| `knowledge` | `ghcr.io/valiobar/agents-knowledge` |
| `orchestrator` | `ghcr.io/valiobar/agents-orchestrator` |
| `frontend` | `ghcr.io/valiobar/agents-frontend` |
| `mongodb` | public `mongo:7` |
| `redis` | public `redis:7-alpine` |
| `chromadb` | public `chromadb/chroma:0.6.3` |

Tags: git SHA and `latest`. CI sets `IMAGE_TAG` to the commit SHA on the droplet `.env`.

The frontend image inlines `NEXT_PUBLIC_GATEWAY_URL=/gateway-api` and `GATEWAY_URL=http://gateway:8000` at **image build** time. Browser calls stay on the frontend origin and Next.js proxies them to the gateway over the Docker network. `NEXTAUTH_URL` is read at **container start** from the droplet `.env`.

Container names are prefixed (`agents-mongodb`, `agents-redis`, `agents-chromadb`, `agents-gateway`, …). The Docker network is `agents-network`. Volumes are `agents-mongodb-data`, `agents-redis-data`, and `agents-chroma-data`. Those names do not overlap Hint (`hint-mongo`, `hint-network`) or vbar (`vbar-mongodb`, `vbar-network`).

## Host ports

Only the gateway and frontend are published. MongoDB, Redis, and ChromaDB stay on `agents-network`.

| Service | Host → container | Public URL |
|---|---|---|
| Gateway | `8010:8000` | http://159.89.26.67:8010/health |
| Frontend | `3010:3000` | http://159.89.26.67:3010 |
| Auth, business, agent, knowledge, orchestrator | not published | Docker DNS only |
| MongoDB `27017`, Redis `6379`, ChromaDB `8000` | not published | Docker DNS only |

Internal container ports are unchanged (`gateway` still listens on 8000, `frontend` on 3000, ChromaDB on 8000).

### Shared droplet port map

| Stack | Service | Host bind | Agents |
|---|---|---|---|
| Hint | backend | `8000:8000` | was `8000:8000` — **moved to `8010:8000`** |
| Hint | admin | `3001:80` | no overlap |
| Hint | widget | `1337:80` | no overlap |
| Hint | demo | `3002:80` | no overlap |
| vbar-viber-bot | admin | `3000:3000` | was `3000:3000` — **moved to `3010:3000`** |
| vbar-viber-bot | viber | `3001:3001` | no overlap |
| vbar-viber-bot | ai | `127.0.0.1:3002:3002` | no overlap |
| vbar-viber-bot | chromadb | `127.0.0.1:8000:8000` | agents ChromaDB is **not published** |
| vbar-viber-bot | mongodb | `127.0.0.1:27017:27017` | agents MongoDB is **not published** |
| vbar-viber-bot | rabbitmq | `127.0.0.1:5672`, `127.0.0.1:15672` | agents does not use RabbitMQ |
| **agents** | gateway | **`8010:8000`** | free on this host |
| **agents** | frontend | **`3010:3000`** | free on this host |

Do not run `docker-compose.dev.yml` on this droplet. That override publishes auth/business/agent/knowledge/orchestrator ports for local debugging. It does **not** publish MongoDB, Redis, or ChromaDB.

---

## Operator checklist (first deploy)

### 1. Droplet bootstrap (one-time)

SSH in with your own key (`~/.ssh/digitalocean`), not a key from this repo.

1. Install Docker Engine and the Compose plugin (already present if Hint or vbar is running).
2. Clone this repo to a stable path (must contain `deploy.sh`, `infrastructure/`, and `.env`):

   ```bash
   git clone git@github.com:valiobar/agents.git ~/agents
   cd ~/agents
   ```

3. Create the server env file:

   ```bash
   cp .env.example .env
   # Set at least:
   #   JWT_SECRET       — long random string (openssl rand -hex 32)
   #   NEXTAUTH_SECRET  — long random string, different from JWT_SECRET
   #   NEXTAUTH_URL=http://159.89.26.67:3010
   #   IMAGE_TAG=latest — CI overwrites this with the git SHA
   #   OPENAI_API_KEY   — required for chat and embeddings; health checks can pass without it
   ```

   `deploy.sh` refuses the example placeholders for `JWT_SECRET` and `NEXTAUTH_SECRET`.

4. Add the **public** half of the deploy key to `~/.ssh/authorized_keys` for `DEPLOY_USER` (often `root`). The matching **private** key is a GitHub secret only — never commit it.

5. Log in to GHCR so `docker compose pull` can fetch private packages:

   ```bash
   echo "$GHCR_TOKEN" | docker login ghcr.io -u USERNAME --password-stdin
   ```

   Use a PAT (or fine-grained token) with `read:packages`. Skip this if the `agents-*` packages are public.

6. Open (or firewall) host ports `8010` and `3010` if you are not putting a reverse proxy in front yet. Do not open `27017`, `6379`, or a second `8000`.

Do **not** run `docker compose up --build` on the droplet. First start happens via GitHub Actions after secrets are set, or manually with `IMAGE_TAG=<sha> bash deploy.sh` after images exist.

### 2. GitHub Actions secrets

Repo → Settings → Secrets and variables → Actions:

| Secret | Example / notes |
|---|---|
| `DEPLOY_HOST` | `159.89.26.67` |
| `DEPLOY_USER` | `root` (or a user that can run Docker) |
| `DEPLOY_SSH_KEY` | Private key whose public key is on the droplet |
| `DEPLOY_PATH` | `~/agents` (optional; defaults to `~/agents`) |

The application `.env` stays on the server. CI only updates `IMAGE_TAG`. No frontend URL secret is required: `NEXT_PUBLIC_GATEWAY_URL` is the relative path `/gateway-api`.

### 3. Droplet `.env` keys

| Variable | Required by `deploy.sh` | Notes |
|---|---|---|
| `JWT_SECRET` | yes | Shared by auth and gateway. Not an example placeholder |
| `NEXTAUTH_SECRET` | yes | NextAuth cookie signing. Not an example placeholder |
| `NEXTAUTH_URL` | yes | `http://159.89.26.67:3010` |
| `IMAGE_TAG` | set by CI | Git SHA. `latest` is only a bootstrap value |
| `MONGODB_URL` | no | Default `mongodb://mongodb:27017` matches Compose DNS |
| `REDIS_URL` | no | Default `redis://redis:6379` |
| `CHROMADB_HOST` / `CHROMADB_PORT` | no | `chromadb` / `8000` (internal) |
| `CORS_ORIGINS` | no | Default includes `http://159.89.26.67:3010` |
| `GATEWAY_URL` | no | Keep `http://gateway:8000` inside Compose |
| `NEXT_PUBLIC_GATEWAY_URL` | no | Keep `/gateway-api` |
| `OPENAI_API_KEY` | no | Chat and embeddings fail closed without it |
| `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY` | no | Only if those providers are selected |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | no | Google sign-in |
| `COMPANYBOOK_API_KEY` | no | Accountant registry lookup |

### 4. First deploy

Push to `main` or run the **Deploy** workflow (`workflow_dispatch`).

1. Matrix job builds and pushes `agents-gateway`, `agents-auth`, `agents-business`, `agents-agent`, `agents-knowledge`, `agents-orchestrator`, and `agents-frontend` (`:sha` and `:latest`).
2. SSH job writes `IMAGE_TAG=<sha>` into `~/agents/.env` and runs `bash deploy.sh`.
3. `deploy.sh` validates required env, `compose pull`, `compose up -d` (no `--build`), then curls gateway `:8010` and frontend `:3010`.

### Verify

On the droplet:

```bash
curl http://127.0.0.1:8010/health
# {"status":"ok","service":"gateway"}
curl -I http://127.0.0.1:3010/login
```

From a browser or another machine:

- Gateway: http://159.89.26.67:8010/health
- Frontend: http://159.89.26.67:3010

Hint (`:8000`, `:3001`, `:1337`, `:3002`) and vbar (`:3000`, `:3001`) should still answer on their own ports.

### Later deploys

Every push to `main` repeats build → push → SSH → `deploy.sh`. To redeploy the current `main` without a new commit, use **Run workflow**.

CI does not `git pull` on the droplet (same as Hint and vbar). After compose or `deploy.sh` changes land on `main`, fast-forward the checkout once:

```bash
cd ~/agents
git pull --ff-only origin main
```

Manual on the droplet (images must already be in GHCR):

```bash
cd ~/agents
IMAGE_TAG=<sha-or-latest> bash deploy.sh
```

## Useful commands (on the droplet)

```bash
cd ~/agents
docker compose --env-file .env -f infrastructure/docker-compose.yml ps
docker compose --env-file .env -f infrastructure/docker-compose.yml logs -f gateway
docker compose --env-file .env -f infrastructure/docker-compose.yml down
```

`down` keeps named volumes. `down -v` deletes `agents-mongodb-data`, `agents-redis-data`, and `agents-chroma-data`.

## Local vs droplet URLs

| | Frontend | Gateway |
|---|---|---|
| `npm run dev` | http://localhost:3000 | http://localhost:8010 when Compose is up (`frontend/.env`) |
| Docker Compose on a laptop | http://localhost:3010 | http://localhost:8010 |
| Droplet | http://159.89.26.67:3010 | http://159.89.26.67:8010 |
| Inside the Docker network | `frontend:3000` | `gateway:8000` |

`CHROMADB_PORT` stays `8000` everywhere. That is the container port, not a host publish.
