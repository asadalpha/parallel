from __future__ import annotations

import random
import uuid
from dataclasses import dataclass

from geoalchemy2 import Geography
from sqlalchemy import cast, func, null, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location, Story
from app.schemas.catalog import ConciergeRequest

MOOD_TAGS = {
    "cozy": {"cozy", "quiet", "nostalgic"},
    "curious": {"hidden gem", "curious", "lively"},
    "spooky": {"atmospheric", "eerie", "spooky"},
    "reflective": {"nostalgic", "quiet", "reflective"},
    "surprise": set(),
}


@dataclass(frozen=True)
class Candidate:
    story: Story
    location: Location
    distance_meters: float | None


def _distance(latitude: float, longitude: float):
    origin = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
    return func.ST_Distance(
        cast(Location.geom, Geography(geometry_type="POINT", srid=4326)),
        cast(origin, Geography(geometry_type="POINT", srid=4326)),
    )


def _within_radius(latitude: float, longitude: float, radius_meters: int):
    origin = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
    return func.ST_DWithin(
        cast(Location.geom, Geography(geometry_type="POINT", srid=4326)),
        cast(origin, Geography(geometry_type="POINT", srid=4326)),
        radius_meters,
    )


async def find_candidates(
    session: AsyncSession, request: ConciergeRequest, exclude_story_id: uuid.UUID | None = None
) -> list[Candidate]:
    filters = [
        Story.publication_status == "published",
        Location.visibility_status == "public",
        Story.read_minutes <= request.time_available_minutes,
    ]
    if exclude_story_id is not None:
        filters.append(Story.id != exclude_story_id)
    if request.city:
        filters.append(Location.city.ilike(request.city.strip()))

    radius_by_preference = {
        "walking_nearby": 1_500,
        "a_little_farther": 8_000,
        "any_distance": 50_000,
    }
    radius = request.search_radius_meters or radius_by_preference[request.travel_preference]
    distance = None
    if request.latitude is not None and request.longitude is not None:
        distance = _distance(request.latitude, request.longitude)
        filters.append(_within_radius(request.latitude, request.longitude, radius))

    statement = (
        select(
            Story,
            Location,
            distance.label("distance_meters")
            if distance is not None
            else null().label("distance_meters"),
        )
        .join(Location, Story.location_id == Location.id)
        .where(*filters)
    )
    if distance is not None:
        statement = statement.order_by(distance, Story.is_featured.desc(), Story.id)
    else:
        statement = statement.order_by(
            Story.is_featured.desc(), Story.published_at.desc(), Story.id
        )
    result = await session.execute(statement.limit(50))
    return [Candidate(story, location, meters) for story, location, meters in result.all()]


def choose_candidate(request: ConciergeRequest, candidates: list[Candidate]) -> Candidate:
    if request.mood == "surprise":
        return random.SystemRandom().choice(candidates)
    wanted_tags = MOOD_TAGS[request.mood]

    def rank(candidate: Candidate) -> tuple[int, int, float, str]:
        tags = {tag.casefold() for tag in candidate.story.vibe_tags}
        mood_score = len(tags.intersection(wanted_tags))
        distance = (
            candidate.distance_meters if candidate.distance_meters is not None else float("inf")
        )
        return (mood_score, int(candidate.story.is_featured), -distance, str(candidate.story.id))

    return max(candidates, key=rank)
