from sqlalchemy import CheckConstraint

from app.db.base import Base
from app.models import Location, Story, StoryMedia


def test_initial_domain_tables_are_registered_in_metadata() -> None:
    assert set(Base.metadata.tables) == {
        "locations",
        "stories",
        "story_media",
        "story_audio",
        "reports",
        "moderation_records",
        "visits",
    }
    assert Location.__tablename__ == "locations"
    assert Story.__tablename__ == "stories"
    assert StoryMedia.__tablename__ == "story_media"


def test_location_uses_wgs84_point_with_spatial_index() -> None:
    geometry = Location.__table__.c.geom.type

    assert geometry.geometry_type == "POINT"
    assert geometry.srid == 4326
    assert "ST_MakePoint(longitude, latitude)" in str(Location.__table__.c.geom.computed.sqltext)
    assert any(index.name == "ix_locations_geom" for index in Location.__table__.indexes)
    assert any(index.name == "ix_locations_geom_geography" for index in Location.__table__.indexes)


def test_story_constraints_match_publication_contract() -> None:
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in Story.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "'published'" in checks["ck_stories_publication_status_allowed"]
    assert "'submitted'" in checks["ck_stories_publication_status_allowed"]
    assert "read_minutes > 0" == checks["ck_stories_read_minutes_positive"]
