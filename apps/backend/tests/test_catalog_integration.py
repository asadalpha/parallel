import os
import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.main import app
from app.models import Location, Story
from app.services.catalog import list_stories

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_INTEGRATION") != "1",
        reason="set RUN_DB_INTEGRATION=1 to run against local PostGIS",
    ),
]


@pytest.mark.asyncio
async def test_postgis_public_map_query_excludes_unpublished_stories() -> None:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    marker = f"integration-{uuid.uuid4()}"

    async with session_factory() as session:
        try:
            location = Location(
                name=marker,
                latitude=47.6062,
                longitude=-122.3321,
                city="Seattle",
                country="United States",
                visibility_status="public",
            )
            session.add(location)
            await session.flush()

            for title, state in (
                ("Public chapter one", "published"),
                ("Public chapter two", "published"),
                ("Private draft", "draft"),
            ):
                session.add(
                    Story(
                        location_id=location.id,
                        author_id="integration-user",
                        title=f"{marker} {title}",
                        body="A test story used only inside a rolled-back transaction.",
                        category="memory",
                        story_type="personal_memory",
                        read_minutes=1,
                        publication_status=state,
                        published_at=datetime.now(UTC) if state == "published" else None,
                    )
                )
            await session.flush()

            rows, total = await list_stories(
                session,
                page=1,
                page_size=20,
                location_id=location.id,
                origin=(47.6062, -122.3321),
                radius_meters=1_000,
                multiple_chapters=True,
            )

            assert total == 2
            assert len(rows) == 2
            assert all(story.publication_status == "published" for story, *_ in rows)
            assert all(distance == 0 for _, _, distance, *_ in rows)
        finally:
            await session.rollback()
            await engine.dispose()


@pytest.mark.asyncio
async def test_live_readiness_endpoint_connects_to_postgis() -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}
