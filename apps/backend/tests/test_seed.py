import json
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routes import seed as seed_routes
from app.core.config import get_settings
from app.main import app
from app.models import Location, Story, StoryMedia

VALID_STORY = {
    "title": "A seeded story",
    "body": "A body long enough to be a real paragraph of prose for the seed form.",
    "category": "architecture",
    "story_type": "history",
    "name": "Somewhere",
    "latitude": 28.6315,
    "longitude": 77.2167,
    "city": "New Delhi",
    "country": "India",
}


@pytest.fixture(autouse=True)
def seed_guard_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run seed tests as if the dev tool were explicitly opted in, pointing at localhost."""
    settings = get_settings().model_copy(
        update={
            "seed_enabled": True,
            "seed_allow_remote_database": False,
            "database_url": "postgresql+asyncpg://parallel:parallel@localhost:5433/parallel",
        }
    )
    monkeypatch.setattr(seed_routes, "get_settings", lambda: settings)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_seed_routes_are_inert_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings().model_copy(
        update={
            "environment": "Production ",
            "seed_enabled": True,
            "seed_allow_remote_database": False,
        }
    )
    monkeypatch.setattr(seed_routes, "get_settings", lambda: settings)

    async with _client() as client:
        listed = await client.get("/api/v1/seed/locations")
        created = await client.post("/api/v1/seed/story", data=VALID_STORY)

    assert listed.status_code == 404
    assert created.status_code == 404
    assert created.json() == {"detail": "Not found"}


async def test_seed_routes_inert_without_explicit_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings().model_copy(update={"seed_enabled": False})
    monkeypatch.setattr(seed_routes, "get_settings", lambda: settings)

    async with _client() as client:
        listed = await client.get("/api/v1/seed/locations")

    assert listed.status_code == 404


async def test_seed_routes_reject_remote_database_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings().model_copy(
        update={
            "seed_enabled": True,
            "seed_allow_remote_database": False,
            "database_url": "postgresql+asyncpg://u:p@ep-host.neon.tech/db",
        }
    )
    monkeypatch.setattr(seed_routes, "get_settings", lambda: settings)

    async with _client() as client:
        listed = await client.get("/api/v1/seed/locations")

    assert listed.status_code == 404


async def test_seed_rejects_unknown_story_type() -> None:
    async with _client() as client:
        response = await client.post(
            "/api/v1/seed/story", data={**VALID_STORY, "story_type": "gossip"}
        )

    assert response.status_code == 422
    assert "story_type" in response.json()["detail"]


JSON_STORY = {**VALID_STORY, "vibe_tags": ["cozy", "quiet"], "is_featured": True}


async def test_seed_json_rejects_invalid_payload() -> None:
    async with _client() as client:
        response = await client.post("/api/v1/seed/story-json", data={"payload": "{not json"})

    assert response.status_code == 422
    assert "valid JSON" in response.json()["detail"]


async def test_seed_json_rejects_unknown_story_type() -> None:
    async with _client() as client:
        response = await client.post(
            "/api/v1/seed/story-json",
            data={"payload": json.dumps({**JSON_STORY, "story_type": "gossip"})},
        )

    assert response.status_code == 422
    assert "story_type" in response.json()["detail"]


async def test_seed_json_requires_location() -> None:
    payload = {key: value for key, value in JSON_STORY.items() if key != "name"}
    async with _client() as client:
        response = await client.post(
            "/api/v1/seed/story-json", data={"payload": json.dumps(payload)}
        )

    assert response.status_code == 422
    assert "existing_location_id" in response.json()["detail"]


async def test_seed_requires_location_name_or_id() -> None:
    payload = {key: value for key, value in VALID_STORY.items() if key != "name"}
    async with _client() as client:
        response = await client.post("/api/v1/seed/story", data=payload)

    assert response.status_code == 422
    assert "existing location" in response.json()["detail"]


async def test_seed_requires_coordinates_for_new_location() -> None:
    payload = {key: value for key, value in VALID_STORY.items() if key != "latitude"}
    async with _client() as client:
        response = await client.post("/api/v1/seed/story", data=payload)

    assert response.status_code == 422
    assert "Latitude and longitude" in response.json()["detail"]


async def test_seed_rejects_malformed_sources() -> None:
    async with _client() as client:
        response = await client.post(
            "/api/v1/seed/story",
            data={**VALID_STORY, "historical_sources": "{not json"},
        )

    assert response.status_code == 422
    assert "valid JSON" in response.json()["detail"]


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="set RUN_DB_INTEGRATION=1 to run against a real database",
)
async def test_seed_creates_a_published_curated_story() -> None:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    marker = f"seed-{uuid.uuid4()}"

    async with session_factory() as session:
        try:
            async with _client() as client:
                response = await client.post(
                    "/api/v1/seed/story",
                    data={**VALID_STORY, "title": marker, "vibe_tags": "circular, imperial"},
                )
            assert response.status_code == 201

            stored = await session.get(Story, uuid.UUID(response.json()["id"]))
            assert stored is not None
            assert stored.publication_status == "published"
            assert stored.is_curated is True
            assert stored.read_minutes > 0
            assert stored.vibe_tags == ["circular", "imperial"]
            assert stored.published_at is not None

            location = await session.get(Location, stored.location_id)
            assert location is not None
            assert location.geom is not None

            media = await session.scalars(
                select(StoryMedia).where(StoryMedia.story_id == stored.id)
            )
            assert media.all() == []
        finally:
            await session.execute(Story.__table__.delete().where(Story.__table__.c.title == marker))
            await session.execute(
                Location.__table__.delete().where(Location.__table__.c.name == VALID_STORY["name"])
            )
            await session.commit()
            await engine.dispose()


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="set RUN_DB_INTEGRATION=1 to run against a real database",
)
async def test_seed_json_creates_a_published_story() -> None:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    marker = f"seed-json-{uuid.uuid4()}"

    async with session_factory() as session:
        try:
            async with _client() as client:
                response = await client.post(
                    "/api/v1/seed/story-json",
                    data={"payload": json.dumps({**JSON_STORY, "title": marker})},
                )
            assert response.status_code == 201, response.text

            stored = await session.get(Story, uuid.UUID(response.json()["id"]))
            assert stored is not None
            assert stored.publication_status == "published"
            assert stored.is_featured is True
            assert stored.vibe_tags == ["cozy", "quiet"]
        finally:
            await session.execute(Story.__table__.delete().where(Story.__table__.c.title == marker))
            await session.execute(
                Location.__table__.delete().where(Location.__table__.c.name == VALID_STORY["name"])
            )
            await session.commit()
            await engine.dispose()
