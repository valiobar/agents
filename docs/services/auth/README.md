# Auth Service

## Overview

Handles user registration, login, Google OAuth, and JWT issuance. Runs on port **8001** behind the API Gateway.

- **Framework:** FastAPI 0.115
- **Database:** MongoDB (via Motor async driver)
- **Password hashing:** bcrypt (via passlib)
- **JWT:** python-jose with HS256

All endpoints are prefixed with `/auth`. Clients reach them through the gateway at `http://localhost:8010/auth/*` (droplet: `http://159.89.26.67:8010/auth/*`). The gateway proxies to `http://auth:8001` internally.

---

## Endpoints

### POST /auth/register

Creates a new user with email/password credentials.

**Request:**

```json
{
  "email": "user@example.com",
  "password": "min8chars",
  "name": "John Doe"
}
```

| Field | Type | Constraints |
|-------|------|-------------|
| `email` | string | Valid email format |
| `password` | string | Min 8 characters |
| `name` | string | 1–100 characters |

**Response (201):**

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

**Errors:**

| Status | Detail |
|--------|--------|
| 409 | Email already registered |
| 422 | Validation error (missing/invalid fields) |

---

### POST /auth/login

Authenticates with email/password.

**Request:**

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response (200):**

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

**Errors:**

| Status | Detail |
|--------|--------|
| 401 | Invalid credentials (wrong password, no account, or Google-only user) |
| 422 | Validation error |

---

### POST /auth/refresh

Exchanges a valid refresh token for a new access + refresh token pair.

**Request:**

```json
{
  "refresh_token": "eyJ..."
}
```

**Response (200):**

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

**Errors:** 401 (invalid, expired, or wrong token type)

---

### POST /auth/oauth/google

Authenticates or registers via Google OAuth. Called by NextAuth on the frontend after Google consent.

**Request:**

```json
{
  "id_token": "eyJ..."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id_token` | string | yes | Google ID token (JWT) from the OAuth flow |

**Response (200):**

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

**Behavior:**

1. Verify `id_token` server-side with Google and extract user claims (`sub`, `email`, `name`, `picture`).
2. If `sub` (Google user ID) matches an existing user → issue tokens for that user.
3. If `email` matches an existing credentials user → link Google account (set `auth_provider: "both"`, store `google_id = sub`) → issue tokens.
4. Otherwise → create new user with `auth_provider: "google"` → issue tokens.

---

### GET /auth/me

Returns the current user's profile. Requires a valid access token.

**Headers:**

```
Authorization: Bearer <access_token>
```

**Response (200):**

```json
{
  "id": "665f...",
  "email": "user@example.com",
  "name": "John Doe",
  "image": null,
  "auth_provider": "credentials"
}
```

**Errors:**

| Status | Detail |
|--------|--------|
| 401 | Missing, malformed, or expired token |
| 404 | User not found (token is valid but user was deleted) |

---

### GET /health

Service health check.

**Response (200):**

```json
{
  "status": "ok",
  "service": "auth"
}
```

---

## Auth Flows

### Email/Password Registration

```
Client → POST /auth/register { email, password, name }
  Auth Service:
    1. Check if email already exists → 409 if so
    2. Hash password with bcrypt
    3. Insert user into MongoDB (auth_provider: "credentials")
    4. Generate access + refresh JWT tokens
    5. Return TokenResponse
```

### Email/Password Login

```
Client → POST /auth/login { email, password }
  Auth Service:
    1. Look up user by email → 401 if not found
    2. Check user has a password_hash (not Google-only) → 401 if null
    3. Verify bcrypt hash → 401 on mismatch
    4. Generate access + refresh JWT tokens
    5. Return TokenResponse
```

### Google OAuth

```
Client → Google Consent Screen → Frontend receives Google profile
Frontend → POST /auth/oauth/google { id_token }
  Auth Service:
    1. Verify id_token with Google, extract claims (sub/email/name/picture)
    2. Find user by google_id (sub) → if found, issue tokens (existing Google user)
    3. Find user by email → if found, link accounts (set auth_provider="both", store google_id), issue tokens
    4. Otherwise → create new user (auth_provider="google"), issue tokens
```

---

## JWT Structure

| Field | Access Token | Refresh Token |
|-------|-------------|---------------|
| `sub` | user_id (MongoDB ObjectId as string) | same |
| `exp` | now + 30 min (configurable) | now + 7 days (configurable) |
| `type` | `"access"` | `"refresh"` |

- **Algorithm:** HS256
- **Signing key:** `JWT_SECRET` environment variable (must match the gateway)

**Example decoded access token payload:**

```json
{
  "sub": "665f1a2b3c4d5e6f7a8b9c0d",
  "exp": 1717200000,
  "type": "access"
}
```

---

## MongoDB Schema — `users` Collection

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `_id` | ObjectId | auto | — | Primary key |
| `email` | string | yes | — | Unique email address |
| `password_hash` | string | no | null | bcrypt hash (null for Google-only users) |
| `name` | string | yes | — | Display name |
| `image` | string | no | null | Profile image URL |
| `google_id` | string | no | null | Google account ID |
| `auth_provider` | string | yes | — | `"credentials"`, `"google"`, or `"both"` |
| `created_at` | datetime | yes | auto | UTC timestamp set on creation |

> **Index:** Ensure a **unique index** on `email` to prevent duplicate accounts and make registration conflicts deterministic.

---

## Internal Architecture

The service follows a layered architecture:

```
routes/auth.py → services/auth_service.py → repositories/user_repo.py → MongoDB
```

| Layer | File | Responsibility |
|-------|------|---------------|
| **Routes** | `app/routes/auth.py` | HTTP handlers, request validation, dependency injection |
| **Service** | `app/services/auth_service.py` | Business logic, orchestration, token issuance |
| **Repository** | `app/repositories/user_repo.py` | MongoDB CRUD operations |
| **Models** | `app/models/user.py` | Pydantic schemas (request/response/DB) |
| **Utils** | `app/utils/jwt.py` | JWT creation and decoding |
| **Utils** | `app/utils/security.py` | Password hashing and verification |
| **Utils** | `app/utils/db.py` | Motor client lifecycle (connect/close/get_database) |
| **Config** | `app/config.py` | Pydantic Settings (reads from `.env`) |

---

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `MONGODB_URL` | `mongodb://mongodb:27017` | MongoDB connection string |
| `DB_NAME` | `agents` | Database name |
| `JWT_SECRET` | `change-me-in-production` | Secret key for JWT signing (**required** — must match gateway) |
| `JWT_ACCESS_EXPIRE_MINUTES` | `30` | Access token TTL in minutes |
| `JWT_REFRESH_EXPIRE_DAYS` | `7` | Refresh token TTL in days |
| `GOOGLE_CLIENT_ID` | *(empty)* | GCP OAuth 2.0 client ID |
| `GOOGLE_CLIENT_SECRET` | *(empty)* | GCP OAuth 2.0 client secret |

> **Critical:** `JWT_SECRET` must be identical for both the auth service and the gateway. Auth signs tokens; the gateway validates them. A mismatch results in 401 on every authenticated request.

---

## Running Locally

### Via Docker Compose (recommended)

```bash
docker compose up --build auth mongodb
```

The service starts on `http://localhost:8001` and connects to MongoDB at `mongodb://mongodb:27017`.

### Standalone (development)

```bash
cd services/auth
pip install -r requirements.txt
# Make sure MongoDB is running and MONGODB_URL is set
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

---

## End-to-End Example

Register a new user and retrieve their profile:

```bash
# 1. Register
curl -X POST http://localhost:8010/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "secret1234", "name": "Alice"}'
# → {"access_token":"eyJ...","refresh_token":"eyJ...","token_type":"bearer"}

# 2. Get profile using the access token
curl http://localhost:8010/auth/me \
  -H "Authorization: Bearer eyJ..."
# → {"id":"665f...","email":"alice@example.com","name":"Alice","image":null,"auth_provider":"credentials"}
```
