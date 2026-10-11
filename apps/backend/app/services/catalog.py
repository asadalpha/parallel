from __future__ import annotations

import uuid

from geoalchemy2 import Geography
from sqlalchemy import Select, cast, func, not_, null, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models import Location, Story, StoryAudio
from app.schemas.catalog import AudioRead, LocationRead, MediaRead, StoryRead, StorySummary
from app.services.storage import StorageNotConfigured, resolve_object_url


def _public_location_filter():
    return Location.visibility_status == "public"


def _published_story_filter():
    return Story.publication_status == "published"


def _bbox_predicate(min_lat: float, min_lon: float, max_lat: float, max_lon: float):
    envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
    return func.ST_Intersects(Location.geom, envelope)


def _distance_expression(latitude: float, longitude: float):
    origin = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
    return func.ST_Distance(
        cast(Location.geom, Geography(geometry_type="POINT", srid=4326)),
        cast(origin, Geography(geometry_type="POINT", srid=4326)),
    )


def _within_radius_predicate(latitude: float, longitude: float, radius_meters: int):
    origin = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
    return func.ST_DWithin(
        cast(Location.geom, Geography(geometry_type="POINT", srid=4326)),
        cast(origin, Geography(geometry_type="POINT", srid=4326)),
        radius_meters,
    )


async def list_locations(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    query: str | None = None,
    city: str | None = None,
    bounds: tuple[float, float, float, float] | None = None,
) -> tuple[list[Location], int]:
    filters = [_public_location_filter()]
    if query:
        pattern = f"%{query.strip()}%"
        filters.append(
            or_(
                Location.name.ilike(pattern),
                Location.city.ilike(pattern),
                Location.country.ilike(pattern),
            )
        )
    if city:
        filters.append(Location.city.ilike(city.strip()))
    if bounds:
        filters.append(_bbox_predicate(*bounds))

    count = await session.scalar(select(func.count(Location.id)).where(*filters))
    result = await session.scalars(
        select(Location)
        .where(*filters)
        .order_by(Location.name, Location.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.all()), int(count or 0)


async def list_stories(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    location_id: uuid.UUID | None = None,
    story_type: str | None = None,
    category: str | None = None,
    vibe: str | None = None,
    query: str | None = None,
    city: str | None = None,
    accessibility_status: str | None = None,
    indoor_outdoor: str | None = None,
    has_audio: bool | None = None,
    multiple_chapters: bool | None = None,
    bounds: tuple[float, float, float, float] | None = None,
    origin: tuple[float, float] | None = None,
    radius_meters: int | None = None,
) -> tuple[list[tuple[Story, Location, float | None, int, bool]], int]:
    filters = [_published_story_filter(), _public_location_filter()]
    if location_id:
        filters.append(Story.location_id == location_id)
    if story_type:
        filters.append(Story.story_type == story_type)
    if category:
        filters.append(Story.category == category)
    if vibe:
        filters.append(Story.vibe_tags.contains([vibe]))
    if query:
        pattern = f"%{query.strip()}%"
        filters.append(or_(Story.title.ilike(pattern), Story.body.ilike(pattern)))
    if city:
        filters.append(Location.city.ilike(city.strip()))
    if accessibility_status:
        filters.append(Location.accessibility_status == accessibility_status)
    if indoor_outdoor:
        filters.append(Location.indoor_outdoor == indoor_outdoor)
    if bounds:
        filters.append(_bbox_predicate(*bounds))

    audio_exists = select(StoryAudio.id).where(
        StoryAudio.story_id == Story.id, StoryAudio.generation_status == "ready"
    )
    audio_available = audio_exists.exists()
    if has_audio is True:
        filters.append(audio_available)
    elif has_audio is False:
        filters.append(not_(audio_available))

    if multiple_chapters is not None:
        chapter_count_for_location = (
            select(func.count(Story.id))
            .where(
                Story.location_id == Location.id,
                Story.publication_status == "published",
            )
            .correlate(Location)
            .scalar_subquery()
        )
        has_multiple_chapters = chapter_count_for_location > 1
        filters.append(has_multiple_chapters if multiple_chapters else not_(has_multiple_chapters))

    distance = None
    if origin:
        distance = _distance_expression(*origin)
        if radius_meters is not None:
            filters.append(_within_radius_predicate(*origin, radius_meters))

    count_query = select(func.count(Story.id)).join(Location).where(*filters)
    count = await session.scalar(count_query)

    published_chapter_count = (
        select(func.count(Story.id))
        .where(Story.location_id == Location.id, Story.publication_status == "published")
        .correlate(Location)
        .scalar_subquery()
    )

    statement: Select = (
        select(
            Story,
            Location,
            distance.label("distance_meters")
            if distance is not None
            else null().label("distance_meters"),
            published_chapter_count.label("chapter_count"),
            audio_available.label("audio_available"),
        )
        .join(Location, Story.location_id == Location.id)
        .options(selectinload(Story.media), joinedload(Story.location))
        .where(*filters)
    )
    if distance is not None:
        statement = statement.order_by(
            distance, Story.is_featured.desc(), Story.published_at.desc()
        )
    else:
        statement = statement.order_by(
            Story.is_featured.desc(), Story.published_at.desc(), Story.id
        )
    result = await session.execute(statement.offset((page - 1) * page_size).limit(page_size))
    rows = [
        (story, location, meters, int(chapters), bool(has_audio))
        for story, location, meters, chapters, has_audio in result.all()
    ]
    return rows, int(count or 0)


async def get_public_location(session: AsyncSession, location_id: uuid.UUID) -> Location | None:
    return await session.scalar(
        select(Location).where(Location.id == location_id, _public_location_filter())
    )


async def get_public_story(session: AsyncSession, story_id: uuid.UUID) -> Story | None:
    return await session.scalar(
        select(Story)
        .join(Location, Story.location_id == Location.id)
        .options(joinedload(Story.location), selectinload(Story.media))
        .where(Story.id == story_id, _published_story_filter(), _public_location_filter())
    )


async def list_chapters(
    session: AsyncSession, location_id: uuid.UUID, *, offset: int = 0, limit: int = 50
) -> tuple[list[Story], int]:
    filters = (
        Story.location_id == location_id,
        _published_story_filter(),
        Story.location.has(_public_location_filter()),
    )
    count = await session.scalar(select(func.count(Story.id)).where(*filters))
    result = await session.scalars(
        select(Story)
        .where(*filters)
        .options(selectinload(Story.media), joinedload(Story.location))
        .order_by(Story.is_featured.desc(), Story.published_at.desc(), Story.id)
        .offset(offset)
        .limit(limit)
    )
    return list(result.all()), int(count or 0)


async def audio_for_story(session: AsyncSession, story_id: uuid.UUID) -> list[StoryAudio]:
    result = await session.scalars(
        select(StoryAudio)
        .where(StoryAudio.story_id == story_id, StoryAudio.generation_status == "ready")
        .order_by(StoryAudio.created_at.desc())
    )
    return list(result.all())


async def chapter_count(session: AsyncSession, location_id: uuid.UUID) -> int:
    count = await session.scalar(
        select(func.count(Story.id)).where(
            Story.location_id == location_id, _published_story_filter()
        )
    )
    return int(count or 0)


async def _public_media_url(object_key: str | None) -> str | None:
    if not object_key:
        return None
    try:
        return await resolve_object_url(object_key)
    except StorageNotConfigured:
        return None


async def to_story_summary(
    story: Story,
    location: Location,
    distance_meters: float | None = None,
    *,
    audio_available: bool = False,
    other_chapter_count: int = 0,
) -> StorySummary:
    return StorySummary(
        id=story.id,
        location_id=story.location_id,
        title=story.title,
        category=story.category,
        story_type=story.story_type,
        cover_image_url=await _public_media_url(story.cover_image_url),
        vibe_tags=story.vibe_tags,
        read_minutes=story.read_minutes,
        is_curated=story.is_curated,
        is_featured=story.is_featured,
        location=LocationRead.model_validate(location),
        distance_meters=distance_meters,
        audio_available=audio_available,
        other_chapter_count=other_chapter_count,
    )


async def to_story_read(session: AsyncSession, story: Story) -> StoryRead:
    audio = await audio_for_story(session, story.id)
    total_chapters = await chapter_count(session, story.location_id)
    result = StoryRead.model_validate(story)
    media = []
    for item in story.media:
        media_read = MediaRead.model_validate(item)
        resolved_url = await _public_media_url(item.media_url)
        if resolved_url:
            media.append(media_read.model_copy(update={"media_url": resolved_url}))

    audio_read = []
    for item in audio:
        resolved_url = await _public_media_url(item.audio_url)
        if resolved_url:
            audio_read.append(
                AudioRead.model_validate(item).model_copy(update={"audio_url": resolved_url})
            )

    return result.model_copy(
        update={
            "cover_image_url": await _public_media_url(story.cover_image_url),
            "media": media,
            "audio": audio_read,
            "audio_available": bool(audio_read),
            "other_chapter_count": max(0, total_chapters - 1),
        }
    )
