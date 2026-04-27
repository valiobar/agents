# Auth Service Architecture

## Current State

The Auth Service is implemented. It supports registration, login, token refresh, Google ID token verification, JWT issuance, and profile lookup.

## Responsibility

The Auth Service owns identity and user account records.

Implemented responsibilities:

- Register users with email/password.
- Hash passwords with bcrypt.
- Authenticate credentials users.
- Verify Google ID tokens server-side.
- Link Google identities to existing email accounts.
- Issue access and refresh JWTs.
- Validate refresh tokens.
- Return current user profile.

## Layers

```text
routes/auth.py -> services/auth_service.py -> repositories/user_repo.py -> MongoDB
                                  \-> utils/jwt.py
                                  \-> utils/security.py
```

| Layer | Responsibility |
|-------|----------------|
| `routes/` | FastAPI endpoints and dependency injection |
| `services/` | Auth business rules and token issuance |
| `repositories/` | User collection access |
| `models/` | Pydantic request/response/database schemas |
| `utils/` | JWT, password hashing, and database lifecycle helpers |
| `config.py` | Environment-driven settings |

## Main Patterns

- **Layered architecture:** routes do not access MongoDB directly.
- **Repository pattern:** `UserRepository` owns user persistence.
- **Token service utility:** JWT creation/decoding lives outside routes.
- **Explicit error handling:** invalid credentials, duplicate email, and token failures return defined HTTP errors.

## Restrictions

- Never store plaintext passwords.
- `JWT_SECRET` must match the gateway.
- Refresh tokens must have `type == "refresh"`.
- Access tokens must have `type == "access"`.
- Google OAuth requests must use `id_token`; the service verifies it with Google.
- Ensure `email` has a unique MongoDB index.
