import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.catalog import AudioRead, LocationRead, Page, StoryRead, StorySummary, StoryType
from app.services.catalog import (
    get_public_location,
    get_public_story,
    list_locations,
    list_stories,
    to_story_read,
    to_story_summary,
)

router = APIRouter(tags=["catalog"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _bounds(
    min_lat: float | None,
    min_lon: float | None,
    max_lat: float | None,
    max_lon: float | None,
) -> tuple[float, float, float, float] | None:
    values = (min_lat, min_lon, max_lat, max_lon)
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise HTTPException(status_code=422, detail="All four map bounds are required together")
    if min_lat > max_lat or min_lon > max_lon:
        raise HTTPException(status_code=422, detail="Minimum bounds must not exceed maximum bounds")
    return min_lat, min_lon, max_lat, max_lon


@router.get("/locations", response_model=Page[LocationRead])
async def locations_list(
    session: SessionDep,
    query: Annotated[str | None, Query(max_length=120)] = None,
    city: Annotated[str | None, Query(max_length=120)] = None,
    min_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    min_lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    max_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    max_lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Page[LocationRead]:
    rows, total = await list_locations(
        session,
        page=page,
        page_size=page_size,
        query=query,
        city=city,
        bounds=_bounds(min_lat, min_lon, max_lat, max_lon),
    )
    return Page(
        items=[LocationRead.model_validate(location) for location in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/locations/{location_id}", response_model=LocationRead)
async def location_detail(location_id: uuid.UUID, session: SessionDep) -> LocationRead:
    location = await get_public_location(session, location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")
    return LocationRead.model_validate(location)


@router.get("/locations/{location_id}/chapters", response_model=Page[StorySummary])
async def location_chapters(
    location_id: uuid.UUID,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Page[StorySummary]:
    location = await get_public_location(session, location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")
    rows, total = await list_stories(
        session,
        page=page,
        page_size=page_size,
        location_id=location_id,
    )
    items = [
        await to_story_summary(
            story,
            chapter_location,
            distance,
            audio_available=has_audio,
            other_chapter_count=max(0, total_at_location - 1),
        )
        for story, chapter_location, distance, total_at_location, has_audio in rows
    ]
    return Page(items=items, page=page, page_size=page_size, total=total)


@router.get("/stories", response_model=Page[StorySummary])
async def stories_list(
    session: SessionDep,
    location_id: uuid.UUID | None = None,
    story_type: StoryType | None = None,
    category: Annotated[str | None, Query(max_length=80)] = None,
    vibe: Annotated[str | None, Query(max_length=40)] = None,
    query: Annotated[str | None, Query(max_length=120)] = None,
    city: Annotated[str | None, Query(max_length=120)] = None,
    accessibility_status: Annotated[str | None, Query(max_length=40)] = None,
    indoor_outdoor: Annotated[str | None, Query(max_length=24)] = None,
    has_audio: bool | None = None,
    multiple_chapters: bool | None = None,
    latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
    radius_meters: Annotated[int | None, Query(ge=100, le=50_000)] = None,
    min_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    min_lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    max_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    max_lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> Page[StorySummary]:
    if (latitude is None) != (longitude is None):
        raise HTTPException(status_code=422, detail="Latitude and longitude are required together")
    rows, total = await list_stories(
        session,
        page=page,
        page_size=page_size,
        location_id=location_id,
        story_type=story_type,
        category=category,
        vibe=vibe,
        query=query,
        city=city,
        accessibility_status=accessibility_status,
        indoor_outdoor=indoor_outdoor,
        has_audio=has_audio,
        multiple_chapters=multiple_chapters,
        bounds=_bounds(min_lat, min_lon, max_lat, max_lon),
        origin=(latitude, longitude) if latitude is not None else None,
        radius_meters=(radius_meters or 5_000) if latitude is not None else None,
    )
    items = [
        await to_story_summary(
            story,
            location,
            distance,
            audio_available=has_audio,
            other_chapter_count=max(0, total_at_location - 1),
        )
        for story, location, distance, total_at_location, has_audio in rows
    ]
    return Page(items=items, page=page, page_size=page_size, total=total)


@router.get("/stories/{story_id}", response_model=StoryRead)
async def story_detail(story_id: uuid.UUID, session: SessionDep) -> StoryRead:
    story = await get_public_story(session, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="Story not found")
    return await to_story_read(session, story)


@router.get("/stories/{story_id}/audio", response_model=list[AudioRead])
async def story_audio(story_id: uuid.UUID, session: SessionDep) -> list[AudioRead]:
    story = await get_public_story(session, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="Story not found")
    return (await to_story_read(session, story)).audio
