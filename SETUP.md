# Development setup

## Requirements

- Node.js 22 or newer and npm
- Python 3.12 or newer and [uv](https://docs.astral.sh/uv/)
- Docker Desktop (for the local PostGIS database)

## Configure the environment

Copy `.env.example` to `.env` at the repository root and `apps/frontend/.env.local.example` to `apps/frontend/.env.local`. The defaults are for local development only. Keep credentials out of version control.

The backend reads `DATABASE_URL` and `CORS_ORIGINS`. The frontend-specific example includes `NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_MAP_STYLE_URL`; the map URL is intentionally blank until a tile/style provider is selected.

## Start the database

```powershell
docker compose up -d db
```

The database listens on `localhost:5433` and enables PostGIS (the container listens internally on 5432). To stop it while preserving local data, run `docker compose down`. To remove the local database data as well, run `docker compose down -v`.

## Run the API

```powershell
cd apps/backend
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Interactive API documentation is available at <http://localhost:8000/docs>.

Run backend checks with:

```powershell
uv run pytest
uv run ruff check .
```

## Run the web app

In a second terminal:

```powershell
cd apps/frontend
npm install
npm run dev
```

Open <http://localhost:3000>. Common checks:

```powershell
npm run lint
npm run typecheck
npm test
```

## First-run notes

- `/api/v1/health` is a liveness check and does not require a database connection; `/api/v1/health/ready` verifies database connectivity.
- The frontend scaffold does not need map credentials to run. Configure `NEXT_PUBLIC_MAP_STYLE_URL` when a map tile provider is chosen.
- Neon Auth is provisioned, but the `role` claim is never populated on its managed JWTs, so curator and admin routes are not usable yet. External AI and media services are optional and degrade gracefully.

See [`docs/guide.md`](docs/guide.md) for the Neon Object Storage setup, Neon Auth configuration, and optional OpenRouter, Sentry, ElevenLabs, and Render configuration.
