# Auth Data Models

Source files:

- `services/auth/app/models/user.py`
- `services/auth/app/repositories/user_repo.py`
- `services/auth/app/utils/jwt.py`

## Pydantic Request Models

### `UserCreate`

Used by `POST /auth/register`.

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `email` | `EmailStr` | yes | Valid email address |
| `password` | `str` | yes | Minimum length: 8 |
| `name` | `str` | yes | 1-100 characters |

Example:

```json
{
  "email": "user@example.com",
  "password": "secret123",
  "name": "John Doe"
}
```

### `UserLogin`

Used by `POST /auth/login`.

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `email` | `EmailStr` | yes | Valid email address |
| `password` | `str` | yes | Non-empty string expected |

Example:

```json
{
  "email": "user@example.com",
  "password": "secret123"
}
```

### `RefreshRequest`

Used by `POST /auth/refresh`.

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `refresh_token` | `str` | yes | Must be a valid, unexpired JWT with `type: "refresh"` |

Example:

```json
{
  "refresh_token": "eyJ..."
}
```

### `GoogleOAuthRequest`

Used by `POST /auth/oauth/google`.

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `id_token` | `str` | yes | Google ID token verified server-side against `GOOGLE_CLIENT_ID` |

Example:

```json
{
  "id_token": "eyJ..."
}
```

## Pydantic Response Models

### `TokenResponse`

Returned by registration, login, Google OAuth, and refresh.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `access_token` | `str` | yes | JWT with `type: "access"` |
| `refresh_token` | `str` | yes | JWT with `type: "refresh"` |
| `token_type` | `str` | yes | Defaults to `"bearer"` |

Example:

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### `UserResponse`

Returned by `GET /auth/me`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id` | `str` | yes | MongoDB ObjectId serialized as string |
| `email` | `str` | yes | User email address |
| `name` | `str` | yes | Display name |
| `image` | `str \| null` | no | Profile image URL, usually from Google |
| `auth_provider` | `str` | yes | `"credentials"`, `"google"`, or `"both"` |

Example:

```json
{
  "id": "665f1a2b3c4d5e6f7a8b9c0d",
  "email": "user@example.com",
  "name": "John Doe",
  "image": null,
  "auth_provider": "credentials"
}
```

## Database Model

### `UserInDB`

Internal model for documents in MongoDB `users`.

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `_id` | `ObjectId` in MongoDB, `str` in Pydantic | yes | generated | Exposed as `id` in `UserInDB` through alias |
| `email` | `str` | yes | none | Should be unique |
| `password_hash` | `str \| null` | no | `null` | bcrypt hash for credentials users |
| `name` | `str` | yes | none | Display name |
| `image` | `str \| null` | no | `null` | Profile image URL |
| `google_id` | `str \| null` | no | `null` | Google `sub` claim |
| `auth_provider` | `str` | yes | none | `"credentials"`, `"google"`, or `"both"` |
| `created_at` | `datetime` | yes | current UTC time | Set by `UserRepository.create()` |

Credentials user example:

```json
{
  "_id": "665f1a2b3c4d5e6f7a8b9c0d",
  "email": "user@example.com",
  "password_hash": "$2b$12$...",
  "name": "John Doe",
  "image": null,
  "google_id": null,
  "auth_provider": "credentials",
  "created_at": "2026-04-26T12:00:00Z"
}
```

Google user example:

```json
{
  "_id": "665f1a2b3c4d5e6f7a8b9c0d",
  "email": "user@gmail.com",
  "password_hash": null,
  "name": "Jane Doe",
  "image": "https://lh3.googleusercontent.com/...",
  "google_id": "google-sub-123",
  "auth_provider": "google",
  "created_at": "2026-04-26T12:00:00Z"
}
```

## Indexes

| Collection | Index | Requirement |
|------------|-------|-------------|
| `users` | `email` unique | Required to prevent duplicate accounts |
| `users` | `google_id` | Recommended for Google login lookup |

## JWT Payloads

JWTs are signed with HS256 using `JWT_SECRET`.

### Access Token

| Claim | Type | Value |
|-------|------|-------|
| `sub` | `str` | User ID |
| `exp` | timestamp | Now + `JWT_ACCESS_EXPIRE_MINUTES` |
| `type` | `str` | `"access"` |

Example decoded payload:

```json
{
  "sub": "665f1a2b3c4d5e6f7a8b9c0d",
  "exp": 1777200000,
  "type": "access"
}
```

### Refresh Token

| Claim | Type | Value |
|-------|------|-------|
| `sub` | `str` | User ID |
| `exp` | timestamp | Now + `JWT_REFRESH_EXPIRE_DAYS` |
| `type` | `str` | `"refresh"` |

Example decoded payload:

```json
{
  "sub": "665f1a2b3c4d5e6f7a8b9c0d",
  "exp": 1777800000,
  "type": "refresh"
}
```

## Provider State Transitions

| Starting State | Event | Result |
|----------------|-------|--------|
| No user | Register with email/password | New user with `auth_provider: "credentials"` |
| No user | Google OAuth with verified ID token | New user with `auth_provider: "google"` |
| Credentials user | Google OAuth with matching email | Existing user updated to `auth_provider: "both"` and `google_id` set |
| Google user | Login with email/password | Rejected because `password_hash` is `null` |
