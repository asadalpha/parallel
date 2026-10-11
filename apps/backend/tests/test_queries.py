from typing import Any

import pytest
from sqlalchemy.dialects import postgresql

from app.services.catalog import list_stories


class EmptyResult:
    def all(self) -> list[Any]:
        return []


class RecordingSession:
    def __init__(self) -> None:
        self.statements = []

    async def scalar(self, statement: Any) -> int:
        self.statements.append(statement)
        return 0

    async def execute(self, statement: Any) -> EmptyResult:
        self.statements.append(statement)
        return EmptyResult()


@pytest.mark.asyncio
async def test_story_map_query_compiles_postgis_radius_and_bounds_filters() -> None:
    session = RecordingSession()

    rows, total = await list_stories(
        session,  # type: ignore[arg-type]
        page=1,
        page_size=20,
        origin=(47.6, -122.3),
        radius_meters=5_000,
        bounds=(47.5, -122.4, 47.7, -122.2),
        has_audio=True,
        multiple_chapters=True,
    )

    sql = str(session.statements[-1].compile(dialect=postgresql.dialect()))

    assert rows == []
    assert total == 0
    assert "ST_DWithin" in sql
    assert "ST_Intersects" in sql
    assert "geography" in sql
    assert "distance_meters" in sql
    assert "multiple_chapters" not in sql
