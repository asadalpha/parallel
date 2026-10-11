# Parallel

**Every place has more than one story.**

Parallel is a map-first storytelling platform for discovering and sharing stories connected to real
places. A location can hold many independent story chapters.

## Project structure

```text
parallel/
├── apps/
│   ├── backend/       # FastAPI API (Python)
│   └── frontend/      # Next.js App Router (TypeScript)
├── docs/guide.md      # Development, configuration, and integration guide
├── .env.example
├── docker-compose.yml # Optional local PostGIS database
└── SETUP.md
```

## Quick start

Prerequisites: Node.js 22+, npm, Python 3.12+, `uv`, and Git. Docker Desktop is only needed if you
run the local PostGIS container.

1. Copy `.env.example` to `.env` and `apps/frontend/.env.local.example` to `apps/frontend/.env.local`.
2. Start the API: in `apps/backend`, run `uv sync --extra dev`, `uv run alembic upgrade head`, then `uv run uvicorn app.main:app --reload`.
3. Start the web app: in `apps/frontend`, run `npm install`, then `npm run dev`.
4. Open <http://localhost:3000>. The API health endpoint is <http://localhost:8000/api/v1/health>.

If `DATABASE_URL` points at a hosted database you can skip `docker compose up -d db`.

See [SETUP.md](./SETUP.md) for day-to-day commands, and
[docs/guide.md](./docs/guide.md) for configuration, credentials, the API surface, and known gaps.

## Architecture

- **Frontend:** Next.js App Router, React, TypeScript, Tailwind CSS, MapLibre GL JS, and TanStack Query.
- **API:** FastAPI, Pydantic, and SQLAlchemy 2 async.
- **Database:** PostgreSQL with PostGIS. Neon PostgreSQL for hosted environments.
- **Media:** Neon Object Storage (S3-compatible) for image and audio bytes; Postgres stores object keys and metadata, never the bytes.
- **Authentication:** Neon Auth (Managed Better Auth). FastAPI verifies issued JWTs against the branch JWKS endpoint.

The initial app and API are intentionally small. Ask before changing the stack or expanding scope.
