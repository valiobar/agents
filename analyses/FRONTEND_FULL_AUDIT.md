# Frontend Full Audit

## 1. Overview

This audit reviews the current `frontend/` Next.js application against the intended frontend architecture and system contracts.

Docs reviewed:

- `docs/architecture/overview.md`
- `docs/architecture/dependency-graph.md`
- `docs/frontend/architecture.md`
- `docs/frontend/data-flow.md`
- `docs/frontend/dependency-graph.md`
- `docs/api/README.md`
- `docs/deployment/README.md`
- `docs/services/gateway/architecture.md`
- `docs/services/gateway/data-flow.md`
- `docs/services/auth/README.md`
- `docs/services/agent/README.md`

Frontend files reviewed:

- `frontend/package.json`
- `frontend/tsconfig.json`
- `frontend/eslint.config.mjs`
- `frontend/.eslintrc.json`
- `frontend/next.config.mjs`
- `frontend/tailwind.config.ts`
- `frontend/components.json`
- `frontend/src/app/layout.tsx`
- `frontend/src/app/page.tsx`
- `frontend/src/app/globals.css`
- `frontend/src/shared/config/env.ts`
- `frontend/src/shared/config/routes.ts`
- `frontend/src/shared/lib/cn.ts`
- `frontend/src/shared/lib/format.ts`
- `frontend/src/shared/ui/*`
- `docker-compose.yml`

Verification run:

```bash
npm run lint && npm run typecheck && npm run build
```

Result: lint, TypeScript, and production build all pass.

## 2. Architecture Context

The system architecture says the frontend is the user-facing entry point for auth, dashboard, agent management, chat, invoices, expenses, and document upload. All backend communication must go through the API Gateway on port `8000`; the frontend must not call internal services directly or own backend data.

The frontend target architecture is Feature-Sliced Design:

```text
app/ -> widgets/ -> features/ -> entities/ -> shared/
```

The docs describe these key frontend responsibilities:

- Next.js 14 App Router application on port `3000`.
- Auth through NextAuth plus the implemented Auth Service via the gateway.
- Route protection for dashboard routes.
- `shared/api/client.ts` as the single HTTP facade for gateway calls.
- TanStack Query for server state.
- React Hook Form + Zod for forms.
- Zustand for cross-feature UI state.
- SSE support for `POST /agents/{agent_id}/chat`.
- Server Components by default; Client Components only where interactivity requires them.

Important implementation status note: the architecture docs still mark the frontend as "planned but not started", but the repository now contains a small Next.js application with shared UI primitives and configuration.

## 3. Findings

### Finding 1 - Home Page Redirects To A Missing Dashboard

**Category:** Bug  
**Severity:** Critical  
**Effort:** Low

**Problem:** The only real application route redirects every visitor from `/` to `/dashboard`, but no dashboard route exists in `frontend/src/app`.

**Impact:** The app builds successfully, but the first user-visible page lands on a 404. This makes the frontend unusable even though lint, typecheck, and build pass.

**Evidence:**

```tsx
// frontend/src/app/page.tsx:1-5
import { redirect } from "next/navigation";

export default function HomePage() {
  redirect("/dashboard");
}
```

Current app route files:

```text
frontend/src/app/layout.tsx
frontend/src/app/page.tsx
frontend/src/app/globals.css
```

The target docs expect a dashboard route:

```text
// docs/frontend/architecture.md:89-99
│   ├── (dashboard)/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── agents/
│   │   ├── invoices/
│   │   └── expenses/
```

**Recommendation:** Replace the unconditional redirect with a real landing page or create the minimal `app/(dashboard)/page.tsx` route before redirecting there. If auth is expected first, redirect unauthenticated users to `/login` after session checks are implemented.

### Finding 2 - Auth Is Installed But Not Wired Into The App

**Category:** Security issue / Missing best practice  
**Severity:** High  
**Effort:** Medium

**Problem:** `next-auth` is installed, but there is no NextAuth route handler, no auth config, no session provider, no middleware, and no login/register routes.

**Impact:** The frontend cannot obtain or attach gateway bearer tokens, cannot refresh sessions, and cannot protect dashboard routes. When API calls are added, protected backend endpoints will return `401` unless each feature invents its own auth handling.

**Evidence:**

```json
// frontend/package.json:22-30
"next": "14.2.15",
"next-auth": "4.24.11",
"next-themes": "0.4.4",
"react": "18.3.1",
"react-dom": "18.3.1",
"react-hook-form": "7.53.2",
"tailwind-merge": "2.5.5",
"tailwindcss-animate": "1.0.7",
"zod": "3.23.8",
```

Root layout has no providers:

```tsx
// frontend/src/app/layout.tsx:9-18
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

The docs require auth/session integration and route protection:

```text
// docs/frontend/architecture.md:594-597
Authentication is handled by NextAuth.js with two providers: Google OAuth and Credentials.
The JWT is stored in an HTTP-only cookie. Components access session data via useSession().
```

```text
// docs/frontend/architecture.md:721
Route protection is enforced by Next.js middleware that checks for a valid session before allowing access to (dashboard)/* routes.
```

**Recommendation:** Add `shared/lib/auth.ts`, `app/api/auth/[...nextauth]/route.ts`, `middleware.ts`, a client `Providers` wrapper for `SessionProvider`, and minimal `login`/`register` pages. Keep token issuance in the Auth Service and call it through the gateway.

### Finding 3 - There Is No API Facade Or SSE Client

**Category:** Architecture violation / Missing best practice  
**Severity:** High  
**Effort:** Medium

**Problem:** The frontend has no `shared/api/client.ts`, no query hooks, no mutation hooks, and no SSE helper.

**Impact:** The implemented backend features cannot be reached from the UI. Without a shared client, future slices are likely to duplicate `fetch` calls, error parsing, auth header handling, refresh behavior, and SSE parsing.

**Evidence:** The current `src` tree has only `app/` and `shared/` primitives:

```text
frontend/src/app/page.tsx
frontend/src/app/layout.tsx
frontend/src/app/globals.css
frontend/src/shared/config/env.ts
frontend/src/shared/config/routes.ts
frontend/src/shared/lib/cn.ts
frontend/src/shared/lib/format.ts
frontend/src/shared/ui/*
```

The docs explicitly require a single gateway-facing facade:

```text
// docs/frontend/architecture.md:746-749
A single shared/api/client.ts wraps all HTTP calls to the API Gateway.
Every entities/*/api/ and features/*/api/ module uses this client -- never raw fetch.
```

The API contract requires bearer auth and SSE support:

```http
// docs/api/README.md:3-8
All client traffic goes through the API Gateway at http://localhost:8000.
Authenticated endpoints require:

Authorization: Bearer <access_token>
```

```http
// docs/api/README.md:152-158
POST /agents/{agent_id}/chat
Accept: text/event-stream
Content-Type: application/json
```

**Recommendation:** Introduce `shared/api/client.ts` early, even before all features exist. It should centralize base URL selection, bearer token injection, JSON error normalization, query string handling, `FormData` uploads, and POST-based SSE streaming for chat.

### Finding 4 - Docker Compose Still Does Not Run The Frontend

**Category:** Deployment inconsistency  
**Severity:** High  
**Effort:** Low

**Problem:** `docker-compose.yml` still has the frontend service commented out, and there is no `frontend/Dockerfile`.

**Impact:** `docker compose up --build` starts the backend stack but not the user-facing app. This conflicts with the dependency graph that lists the frontend as an exposed service and makes local end-to-end setup incomplete.

**Evidence:**

```yaml
# docker-compose.yml:110-120
# frontend:
#   build:
#     context: ./frontend
#     dockerfile: Dockerfile
#   ports:
#     - "3000:3000"
#   env_file: .env
#   depends_on:
#     - gateway
#   networks:
#     - agents-network
```

No `frontend/Dockerfile` exists.

The dependency docs expect the frontend to start after the gateway:

```text
// docs/architecture/dependency-graph.md:150-157
| Frontend | Gateway | service_started | All API calls go through the gateway |
```

**Recommendation:** Add a production-ready Next.js Dockerfile and enable the `frontend` service in compose. Use `depends_on: gateway: condition: service_started`, expose only `3000`, and pass `NEXT_PUBLIC_GATEWAY_URL` explicitly.

### Finding 5 - Feature-Sliced Structure Is Only Partially Established

**Category:** Architecture violation / Missing best practice  
**Severity:** Medium  
**Effort:** Medium

**Problem:** The current code has `app/` and `shared/`, but no `widgets/`, `features/`, or `entities/` slices.

**Impact:** This is acceptable for a starter shell, but it means the first real feature could easily land in the wrong layer. Without slice folders and public APIs, the codebase has no physical guardrail for the documented FSD dependency rules.

**Evidence:**

```text
frontend/src/
  app/
  shared/
```

The intended hierarchy is larger and domain-oriented:

```text
// docs/frontend/architecture.md:30-37
Layer 7:  app/
Layer 5:  widgets/
Layer 4:  features/
Layer 3:  entities/
Layer 2:  shared/
```

**Recommendation:** Create the first vertical slice deliberately instead of adding files ad hoc. A good first slice is auth: `entities/user`, `features/auth/login`, `features/auth/register`, and `shared/api/client.ts`. Add README or index conventions per layer if the team wants stricter import hygiene.

### Finding 6 - Shared UI Components Are Over-Marked As Client Components

**Category:** Performance issue  
**Severity:** Medium  
**Effort:** Low

**Problem:** Every shared UI primitive starts with `"use client"`, including purely presentational components that do not use hooks, browser APIs, event handlers, or Radix primitives.

**Impact:** Any Server Component that imports these primitives becomes unable to keep that subtree server-only. This grows client bundles earlier than necessary and conflicts with the project rule to prefer React Server Components.

**Evidence:**

```tsx
// frontend/src/shared/ui/empty-state.tsx:1-20
"use client";

import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="rounded-lg border border-dashed p-8 text-center">
      <h3 className="text-lg font-semibold">{title}</h3>
      {description ? (
        <p className="mt-2 text-sm text-muted-foreground">{description}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
```

```tsx
// frontend/src/shared/ui/spinner.tsx:1-8
"use client";

import { cn } from "@/shared/lib/cn";

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn("h-4 w-4 animate-spin text-muted-foreground", className)}
```

The frontend docs define the rendering strategy:

```text
// docs/frontend/architecture.md:843-845
Next.js App Router defaults to Server Components. The strategy is: render on the server wherever possible, drop to Client Components only for interactivity.
```

**Recommendation:** Remove `"use client"` from static primitives such as `EmptyState`, `Spinner`, simple cards, badges, and table components if they do not need browser-only behavior. Keep it on Radix components, form components, and components that genuinely require client-side interactivity.

### Finding 7 - Environment Configuration Is Not Validated

**Category:** Missing best practice / Deployment risk  
**Severity:** Medium  
**Effort:** Low

**Problem:** `shared/config/env.ts` silently falls back to `http://localhost:8000` when gateway environment variables are missing.

**Impact:** This is convenient for local development, but it can hide production misconfiguration. A deployed frontend can build and run while pointing browser traffic at the user's own `localhost:8000`, which is wrong outside local development.

**Evidence:**

```ts
// frontend/src/shared/config/env.ts:1-7
export const env = {
  gatewayUrl:
    process.env.GATEWAY_URL ??
    process.env.NEXT_PUBLIC_GATEWAY_URL ??
    "http://localhost:8000",
  publicGatewayUrl: process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://localhost:8000",
} as const;
```

The deployment docs treat environment configuration as an explicit operational concern:

```text
// docs/deployment/README.md:142-169
All application services read from a single .env file via env_file: .env in docker-compose.yml.
Critical: JWT_SECRET must be identical for auth and gateway.
```

**Recommendation:** Validate required public runtime configuration in one place. For local development, allow the default only under `NODE_ENV !== "production"`. In production, fail fast if `NEXT_PUBLIC_GATEWAY_URL` is unset.

### Finding 8 - Route Constants Include Routes That Do Not Exist

**Category:** Inconsistency  
**Severity:** Low  
**Effort:** Low

**Problem:** `shared/config/routes.ts` defines dashboard, auth, agent, invoice, and expense routes that are not implemented in `app/`.

**Impact:** Constants are useful, but today they can create false confidence. A feature can link to a typed route and still send the user to a 404.

**Evidence:**

```ts
// frontend/src/shared/config/routes.ts:1-10
export const routes = {
  home: "/",
  login: "/login",
  register: "/register",
  dashboard: "/dashboard",
  agents: "/dashboard/agents",
  agentDetail: (id: string) => `/dashboard/agents/${id}`,
  invoices: "/dashboard/invoices",
  expenses: "/dashboard/expenses",
} as const;
```

Only `/` currently exists as an application page.

**Recommendation:** Either add placeholder pages for these routes or keep route constants scoped to implemented routes until the corresponding `app/` segments exist.

### Finding 9 - Formatting Helpers Accept Invalid Values Too Quietly

**Category:** Missing best practice  
**Severity:** Low  
**Effort:** Low

**Problem:** `formatCurrency`, `formatDate`, and `formatPercent` coerce arbitrary strings/numbers without validating the result.

**Impact:** Invalid API values or form state can render as `NaN`, `Invalid Date`, or misleading percentages. This is not a current production bug because no feature uses these helpers yet, but it will matter once invoice and expense screens are added.

**Evidence:**

```ts
// frontend/src/shared/lib/format.ts:1-18
export function formatCurrency(value: string | number, currency = "EUR") {
  return new Intl.NumberFormat("bg-BG", {
    style: "currency",
    currency,
  }).format(Number(value));
}

export function formatDate(value: string | number | Date) {
  return new Intl.DateTimeFormat("bg-BG", {
    dateStyle: "medium",
  }).format(new Date(value));
}

export function formatPercent(value: string | number) {
  return new Intl.NumberFormat("bg-BG", {
    style: "percent",
    maximumFractionDigits: 2,
  }).format(Number(value));
}
```

The API serializes money values as strings and VAT/deductible rates as decimals, so display helpers will sit on a user-visible boundary:

```text
// docs/services/agent/README.md:91
Money values are modeled as Python Decimal, stored in MongoDB as BSON Decimal128, and serialized in JSON responses as strings to avoid float precision loss.
```

**Recommendation:** Decide on UI fallback behavior for invalid values. For example, return `"-"` for invalid dates and throw or return a placeholder for non-finite numbers. Document that `formatPercent(0.2)` renders `20%` so callers do not pass whole-number percentages.

## 4. What Works Well

### Positive Pattern 1 - Strict TypeScript Foundation

**Pattern:** The project enables strict TypeScript and a clean path alias.

```json
// frontend/tsconfig.json:2-20
"compilerOptions": {
  "target": "ES2022",
  "lib": ["DOM", "DOM.Iterable", "ES2022"],
  "allowJs": false,
  "skipLibCheck": true,
  "strict": true,
  "noEmit": true,
  "esModuleInterop": true,
  "module": "ESNext",
  "moduleResolution": "Bundler",
  "resolveJsonModule": true,
  "isolatedModules": true,
  "jsx": "preserve",
  "incremental": true,
  "plugins": [{ "name": "next" }],
  "baseUrl": ".",
  "paths": {
    "@/*": ["src/*"]
  }
}
```

**Why it works:** This is a good baseline for a typed frontend. It prevents implicit `any` drift and supports stable FSD imports.

**Where else to apply:** Keep all new slices under `src/` and use the `@/` alias rather than deep relative imports.

### Positive Pattern 2 - shadcn Configuration Matches FSD

**Pattern:** shadcn aliases point generated components into `shared/ui` and utilities into `shared/lib`.

```json
// frontend/components.json:13-16
"aliases": {
  "components": "@/shared/ui",
  "utils": "@/shared/lib/cn"
}
```

**Why it works:** This prevents generated UI primitives from landing in a root `components/` folder that would bypass the documented FSD structure.

**Where else to apply:** Keep design-system primitives in `shared/ui`; keep domain-specific UI in `entities/*/ui`, `features/*/ui`, or `widgets/*/ui`.

### Positive Pattern 3 - Accessible Primitive Choices

**Pattern:** Interactive primitives use Radix and preserve refs/display names.

```tsx
// frontend/src/shared/ui/dialog.tsx:29-51
export const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-lg",
        className,
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring disabled:pointer-events-none">
        <X className="h-4 w-4" />
        <span className="sr-only">Close</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPortal>
));
DialogContent.displayName = DialogPrimitive.Content.displayName;
```

**Why it works:** Radix handles focus management and accessibility details that are easy to get wrong in custom modal/select components.

**Where else to apply:** Use the same pattern for menus, popovers, tabs, and tooltips instead of hand-rolled interactive primitives.

### Positive Pattern 4 - Class Composition Is Centralized

**Pattern:** `cn()` combines `clsx` and `tailwind-merge`.

```ts
// frontend/src/shared/lib/cn.ts:1-6
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

**Why it works:** It keeps Tailwind class merging consistent and avoids repeated utility code across components.

**Where else to apply:** Use this helper in all new UI primitives and domain components.

### Positive Pattern 5 - Current Foundation Is Build-Clean

**Pattern:** The current app passes lint, typecheck, and production build.

```text
npm run lint      -> No ESLint warnings or errors
npm run typecheck -> passes
npm run build     -> Compiled successfully
```

**Why it works:** The frontend is still small, but the baseline is clean. That makes the next feature additions easier to review because new failures will be attributable.

**Where else to apply:** Add these commands to CI before feature work accelerates.

## 5. Summary - Priority Matrix

| # | Concern | Severity | Effort |
|---|---------|----------|--------|
| 1 | Home route redirects to missing dashboard | **Critical** | Low |
| 2 | Auth is installed but not wired into the app | **High** | Medium |
| 3 | No shared API facade or SSE client exists | **High** | Medium |
| 4 | Docker Compose still does not run the frontend | **High** | Low |
| 5 | FSD structure is only partially established | **Medium** | Medium |
| 6 | Shared UI components are over-marked as client components | **Medium** | Low |
| 7 | Environment configuration is not validated | **Medium** | Low |
| 8 | Route constants include routes that do not exist | **Low** | Low |
| 9 | Formatting helpers accept invalid values too quietly | **Low** | Low |

## 6. Suggested Implementation Order

1. Fix the broken entry route first: either add a minimal dashboard page or stop redirecting `/` to a missing route. This resolves Finding 1.
2. Add auth scaffolding next: NextAuth route handler, auth config, middleware, providers, and minimal login/register pages. This resolves Finding 2 and gives the API client a token source.
3. Add `shared/api/client.ts` with gateway-only HTTP access, bearer token injection, typed error handling, multipart upload support, and POST-based SSE streaming. This resolves Finding 3.
4. Create the first real FSD vertical slices around auth and agents instead of adding more root-level files. This resolves Finding 5 and keeps future imports aligned with the docs.
5. Add a frontend Dockerfile and enable the compose service after the app can render at least login/dashboard. This resolves Finding 4.
6. Trim unnecessary `"use client"` directives from static primitives. This resolves Finding 6 and keeps the Server Component strategy intact.
7. Harden `env.ts`, then clean up route constants and formatting helpers. This resolves Findings 7, 8, and 9.

