# Parallel — development guide

**Every place has more than one story.**

Parallel is a map-first storytelling platform for discovering and sharing stories tied to real
places. A location can hold many independent story chapters — history, personal memory, legend,
fiction, and editorial.

This guide is the self-contained reference for running, configuring, and extending the codebase.
It replaces the separate architecture, backend-implementation, and integrations notes.

---

## Architecture

```text
Browser ──> Next.js web app ──> FastAPI ──> Neon PostgreSQL (PostGIS)
                                   │
                                   ├──> Neon Object Storage  (image/audio bytes, S3-compatible)
                                   └──> OpenRouter / ElevenLabs / Sentry  (optional)
```

| Component | Owns |
| --- | --- |
| `apps/frontend` | Next.js App Router UI, routing, MapLibre rendering, TanStack Query data layer |
| `apps/backend` | FastAPI routes, authorization, SQLAlchemy models, Pydantic contracts, service policy |
| Neon PostgreSQL | Source of truth. PostGIS for geography. Auth-owned tables are excluded from Alembic. |
| Neon Object Storage | Image and audio bytes. Postgres stores object keys + metadata only, never bytes. |
| Neon Auth | Managed Better Auth. Users and sessions live in the `neon_auth` schema. |

**Core principle:** the frontend never talks to the database directly, and ordinary public reads
must keep working when AI, audio, or storage are unavailable.

---

## Prerequisites

- Node.js 22+ and npm
- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Docker Desktop — only if you use the local PostGIS container

You do **not** need Docker when `DATABASE_URL` points at Neon.

---

## Setup

```powershell
Copy-Item .env.example .env
Copy-Item apps/frontend/.env.local.example apps/frontend/.env.local
```

Fill in `.env` (see [Configuration](#configuration)). Both files are git-ignored.

Install and migrate:

```powershell
cd apps/backend
uv sync --extra dev
uv run alembic upgrade head
```

`alembic upgrade head` is an explicit step — migrations are never run from API startup.

---

## Running

Two terminals.

```powershell
# terminal 1 — API on :8000
cd apps/backend
uv run uvicorn app.main:app --reload
```

```powershell
# terminal 2 — web app on :3000
cd apps/frontend
npm install
npm run dev
```

| URL | What |
| --- | --- |
| <http://localhost:3000> | Web app |
| <http://localhost:8000/api/v1/health> | Liveness — does **not** touch the database |
| <http://localhost:8000/api/v1/health/ready> | Readiness — checks DB, returns 503 on failure |
| <http://localhost:8000/docs> | Interactive OpenAPI docs |

### Local PostGIS (optional)

```powershell
docker compose up -d db     # listens on localhost:5433, PostGIS enabled
```

Stop without losing data with `docker compose down`; add `-v` to wipe the volume.

---

## Checks

```powershell
# backend
cd apps/backend
uv run pytest
uv run ruff check .

# frontend
cd apps/frontend
npm run lint
npm run typecheck
npm test
npm run build
```

Baseline at time of writing: **16 passed, 2 skipped**; ruff clean.

---

## Configuration

Secrets belong in `.env` / `.env.local` or your host's secret manager. Never in source control.

### Database

| Variable | Required | Notes |
| --- | --- | --- |
| `DATABASE_URL` | yes | Must use the **`postgresql+asyncpg://`** scheme — the backend runs SQLAlchemy async. Request TLS with `?ssl=require`. The psycopg-style `sslmode=` / `channel_binding=` parameters make asyncpg raise `TypeError`. |
| `POSTGRES_*` | no | Feed `docker-compose.yml` only. Ignored when `DATABASE_URL` is hosted. |

### API

| Variable | Required | Notes |
| --- | --- | --- |
| `CORS_ORIGINS` | yes | Comma-separated exact origins, no trailing slash. Must match the web origin. |
| `ENVIRONMENT` | yes | `development` / `staging` / `production`. |

### Neon Auth (Managed Better Auth)

Protected routes return `503 Authentication is not configured` until all three are set.

| Variable | Required | Notes |
| --- | --- | --- |
| `AUTH_JWKS_URL` | yes | The branch Auth URL + `/.well-known/jwks.json`. |
| `AUTH_ISSUER` | yes | The branch Auth URL (includes its path). |
| `AUTH_AUDIENCE` | yes | The branch Auth URL. Verify against a real token — see [Known gaps](#known-gaps). |
| `AUTH_JWT_ALGORITHMS` | no | `EdDSA`. Neon Auth signs Ed25519. |
| `AUTH_USER_ID_CLAIM` | no | `id`. |
| `AUTH_ROLE_CLAIM` | no | `role`. Read this one carefully — see [Known gaps](#known-gaps). |

Neon Auth pre-approves localhost origins, so no trusted domain is needed in development. Register
your production and preview origins before pointing real users at them.

### Neon Object Storage

Use a **private** bucket. The API returns short-lived signed read URLs; nothing is public.

| Variable | Required | Notes |
| --- | --- | --- |
| `AWS_ENDPOINT_URL_S3` | for uploads | Neon exposes S3 credentials under the `AWS_*` names. |
| `AWS_ACCESS_KEY_ID` | for uploads | Scoped credential with `storage:read` + `storage:write`. |
| `AWS_SECRET_ACCESS_KEY` | for uploads | |
| `AWS_REGION` | for uploads | |
| `OBJECT_STORAGE_BUCKET` | no | Defaults to `parrellel-b1`. Note the spelling. |
| `OBJECT_STORAGE_URL_TTL_SECONDS` | no | Signed-link lifetime, default 3600. |

Leave `OBJECT_STORAGE_PUBLIC_BASE_URL` unset for a private bucket. Clients should refetch story
data when a signed URL expires. Postgres stores object keys and metadata — never image bytes.

### Optional providers

| Variable | Effect if unset |
| --- | --- |
| `OPENROUTER_API_KEY` / `AI_*` | Concierge falls back to deterministic grounded ranking. Public reads unaffected. |
| `ELEVENLABS_API_KEY` / `ELEVENLABS_VOICE_ID` | Narration generation unavailable. Playback of stored audio still works. |
| `SENTRY_DSN` | No error reporting. |
| `NEXT_PUBLIC_MAP_STYLE_URL` | Map falls back to the MapLibre demo style. |
| `NEXT_PUBLIC_API_BASE_URL` | Falls back to `http://localhost:8000/api/v1`. |

Generation calls send draft text to the third-party provider — disclose this in the UI before
enabling writing assistance.

---

## API surface

Prefix: `/api/v1`.

| Access | Routes |
| --- | --- |
| Public | `GET /health`, `GET /health/ready`, `GET /locations`, `GET /locations/{id}`, `GET /locations/{id}/chapters`, `GET /stories`, `GET /stories/{id}`, `GET /stories/{id}/audio` |
| Signed-in | `POST /stories`, `PATCH /stories/{id}`, `POST /stories/{id}/submit`, `GET /me/stories`, `POST /stories/{id}/report`, `POST /stories/{id}/audio-consent`, `POST /locations/{id}/visits`, `POST /media/upload`, `POST /ai/story-assist` |
| Curator | `GET /admin/moderation`, `POST /admin/stories/{id}/decision`, `GET /admin/reports`, `POST /admin/reports/{id}/decision`, `GET /admin/stories/{id}/moderation`, `PATCH /admin/stories/{id}`, `POST /admin/stories/{id}/audio` |
| Admin | Curator routes plus `POST /admin/locations`, `PATCH /admin/locations/{id}`, `POST /admin/stories/curated` |
| AI discovery | `POST /concierge/recommend`, `POST /concierge/another-angle` — deterministic, no model key needed |

### Conventions

- Use Pydantic request/response schemas; never serialize ORM objects directly.
- Stable UUIDs for Parallel locations, stories, and media. Keep external auth IDs as strings.
- Return 404 when a public resource is absent **or** unpublished — do not reveal that a private
  record exists.
- 401 absent/invalid credentials · 403 authenticated but not permitted · 409 invalid state
  transition · 422 invalid input.
- Bound query limits and return deterministic ordering for map and chapter responses.
- Never accept an author ID, reviewer ID, or role from a request body as the authority. Derive
  identity and permissions from the verified token.

---

## Data model

| Table | Responsibility |
| --- | --- |
| `locations` | Place metadata, validated lat/lon, a generated PostGIS point, city/country, visibility |
| `stories` | One narrative per location: author id, type, category, body, publication state, tags, sources |
| `story_media` | Ordered image object keys with captions and alt text |

**Story states:** `draft` → `submitted` → `approved` → `published`, plus `rejected` and `removed`.
Public reads return exactly `published`.

**Story types:** `history`, `personal_memory`, `legend`, `fiction`, `editorial`.

Auth-owned tables stay under Better Auth's migration mechanism. Alembic owns only Parallel tables
and must never alter auth-owned tables.

### Content rules

- No invented or seed story records. Curated content must be real and sourced. Use clearly
  identified fixtures in tests.
- Visits are self-reported and must never be presented as verified presence.
- Never accept identity or role from a request body.

---

## Layout

```text
apps/backend/
├── app/
│   ├── api/routes/     # HTTP route modules, versioned router
│   ├── core/           # settings, security, shared errors
│   ├── db/             # engine, sessions, declarative base
│   ├── models/         # SQLAlchemy domain models
│   ├── schemas/        # Pydantic contracts
│   └── services/       # policy, query composition, use cases
├── migrations/         # Alembic — application tables only
└── tests/              # unit + API tests

apps/frontend/
├── app/                # App Router pages and layouts
├── components/         # UI components
└── lib/                # API client and helpers
```

Routes validate transport input and delegate to services. Services enforce publication rules,
ownership, and role permissions. Repositories are not introduced until query complexity warrants
one.

---

## Deployment

`render.yaml` defines the API web service and health check. Connect the repo in Render and set
secrets in the dashboard — no Render API key is needed to keep the blueprint in the repo.

Minimum required secrets: `DATABASE_URL`, exact production `CORS_ORIGINS`, and the Neon Auth
issuer/audience/JWKS values.

Run `uv run alembic upgrade head` against the target database as a controlled step before routing
traffic to schema-dependent routes.

---

## Known gaps

Track these before relying on the affected feature.

**1. The `role` claim is never populated.** Neon Auth Managed JWTs carry no custom claims, so
`AUTH_ROLE_CLAIM=role` resolves to the `"user"` default on every token and every curator/admin
route returns 403 permanently. No environment variable fixes this. Resolve roles by querying the
`neon_auth` schema by user id instead of trusting the token, or move to self-managed Better Auth.

**2. `AUTH_AUDIENCE` is unverified.** Neon documents the issuer as the branch Auth URL but does not
state the audience, so it is currently set equal to the issuer. If Neon issues a different
audience, every token is rejected as 401. Confirm by decoding a real token.

**3. Map search is not geocoding.** Location search only matches places already stored in the
database. Arbitrary city or neighbourhood search needs a geocoding provider.

**4. Tiles are OpenFreeMap.** No key and no signup, which suits development and light traffic.
Move to a paid provider before real launch if you need limits or an SLA.

---

## Working agreements

- `SETUP.md` and this guide are the sources of truth for how the project is built and run. Ask
  before changing the selected stack or expanding MVP scope.
- Keep the web app in `apps/frontend` and the API in `apps/backend`. Never couple the frontend
  directly to the database.
- Preserve the published-versus-draft distinction in any public API work.
- Keep AI, maps, and audio integrations optional. Core browsing must survive their absence.
- Run the frontend typecheck/linter and backend tests/linter for changes in those apps.
