"""Development-only content seeding.

Creates published stories directly so real content can be loaded without the
draft -> submit -> curate flow.

This router is UNAUTHENTICATED and must never exist in production. It is gated
twice on purpose: main.py only mounts it when ENVIRONMENT is not "production",
and every route re-checks and returns 404 there.
"""

from __future__ import annotations

import json
import math
import uuid
from datetime import UTC, datetime
from typing import Annotated, Final

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.config import get_settings
from app.db.session import get_session
from app.models import Location, Story, StoryMedia
from app.schemas.catalog import StoryRead
from app.services.catalog import to_story_read
from app.services.storage import InvalidImage, StorageNotConfigured, store_uploaded_image

router = APIRouter(prefix="/seed", tags=["development seeding"])

PRODUCTION_ENVIRONMENT: Final = "production"
SEED_OWNER_ID: Final = "curator:seed"
ALLOWED_STORY_TYPES: Final = frozenset(
    {"history", "personal_memory", "legend", "fiction", "editorial"}
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def require_development_environment() -> None:
    """Keep unauthenticated direct-publish routes local and explicitly opted in."""
    settings = get_settings()
    if settings.environment.strip().lower() == PRODUCTION_ENVIRONMENT or not settings.seed_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    database_host = make_url(settings.database_url).host or ""
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if database_host not in local_hosts and not settings.seed_allow_remote_database:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


DevDep = Annotated[None, Depends(require_development_environment)]


class SeedLocationRead(BaseModel):
    id: uuid.UUID
    name: str
    city: str | None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _parse_vibe_tags(raw: str) -> list[str]:
    tags = [tag.strip() for tag in raw.split(",") if tag.strip()]
    if len(tags) > 12:
        raise HTTPException(status_code=422, detail="At most 12 vibe tags are allowed")
    if any(len(tag) > 40 for tag in tags):
        raise HTTPException(status_code=422, detail="Each vibe tag must be 40 characters or fewer")
    return tags


def _parse_sources(raw: str) -> list[dict[str, str]]:
    if not raw.strip():
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422, detail="historical_sources must be valid JSON"
        ) from exc
    if not isinstance(parsed, list) or len(parsed) > 30:
        raise HTTPException(
            status_code=422, detail="historical_sources must be a list of at most 30 objects"
        )
    for item in parsed:
        if not isinstance(item, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in item.items()
        ):
            raise HTTPException(
                status_code=422, detail="Each historical source must map strings to strings"
            )
    return parsed


def _read_minutes(body: str) -> int:
    return max(1, math.ceil(len(body.split()) / 220))


def _validate_story_fields(
    *, title: str, body: str, category: str, story_type: str
) -> tuple[str, str, str]:
    if not title or len(title) > 240:
        raise HTTPException(
            status_code=422, detail="Title is required and must be under 240 characters"
        )
    if not body or len(body) > 100_000:
        raise HTTPException(
            status_code=422, detail="Body is required and must be under 100000 characters"
        )
    if not category or len(category) > 80:
        raise HTTPException(
            status_code=422, detail="Category is required and must be under 80 characters"
        )
    if story_type not in ALLOWED_STORY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"story_type must be one of {sorted(ALLOWED_STORY_TYPES)}",
        )
    return title, body, category


def _validate_vibe_tags(tags: list[str]) -> list[str]:
    if len(tags) > 12:
        raise HTTPException(status_code=422, detail="At most 12 vibe tags are allowed")
    if any(len(tag) > 40 for tag in tags):
        raise HTTPException(status_code=422, detail="Each vibe tag must be 40 characters or fewer")
    return tags


def _validate_sources(sources: list[dict[str, str]]) -> list[dict[str, str]]:
    if len(sources) > 30:
        raise HTTPException(
            status_code=422, detail="historical_sources must be a list of at most 30 objects"
        )
    for item in sources:
        if not all(isinstance(key, str) and isinstance(value, str) for key, value in item.items()):
            raise HTTPException(
                status_code=422, detail="Each historical source must map strings to strings"
            )
    return sources


async def _build_story_with_image(
    session: AsyncSession,
    *,
    location_input: dict[str, object],
    story_input: dict[str, object],
    image: UploadFile | None,
) -> Story:
    """Shared story creation for the form (field-by-field) and JSON seed inputs."""
    location: Location
    existing_location_id = location_input.get("existing_location_id")
    if existing_location_id:
        try:
            location_uuid = uuid.UUID(str(existing_location_id))
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="existing_location_id must be a UUID"
            ) from exc
        location = await session.scalar(
            select(Location).where(
                Location.id == location_uuid, Location.visibility_status == "public"
            )
        )
        if location is None:
            raise HTTPException(status_code=404, detail="Location not found")
    else:
        clean_name = _clean(location_input.get("name"))  # type: ignore[arg-type]
        if not clean_name or len(clean_name) > 200:
            raise HTTPException(
                status_code=422,
                detail="Provide an existing location or a name of 200 characters or fewer",
            )
        latitude = location_input.get("latitude")
        longitude = location_input.get("longitude")
        if latitude is None or longitude is None:
            raise HTTPException(
                status_code=422,
                detail="Latitude and longitude are required when creating a new location",
            )
        location = Location(
            id=uuid.uuid4(),
            name=clean_name,
            description=_clean(location_input.get("description")),
            latitude=float(str(latitude)),
            longitude=float(str(longitude)),
            city=_clean(location_input.get("city")),
            country=_clean(location_input.get("country")),
            place_kind=_clean(location_input.get("place_kind")),
            indoor_outdoor=_clean(location_input.get("indoor_outdoor")),
            visibility_status="public",
        )
        session.add(location)

    clean_title, clean_body, clean_category = _validate_story_fields(
        title=str(story_input.get("title") or "").strip(),
        body=str(story_input.get("body") or "").strip(),
        category=str(story_input.get("category") or "").strip(),
        story_type=str(story_input.get("story_type") or ""),
    )
    vibe_tags = list(story_input.get("vibe_tags") or [])
    historical_sources = list(story_input.get("historical_sources") or [])

    cover_key: str | None = None
    media_items: list[StoryMedia] = []
    if image is not None and image.filename:
        payload = await image.read()
        if not payload:
            raise HTTPException(status_code=422, detail="Uploaded image was empty")
        try:
            cover_key = await store_uploaded_image(payload, SEED_OWNER_ID)
        except InvalidImage as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except StorageNotConfigured as exc:
            raise HTTPException(status_code=503, detail="Object storage is not configured") from exc
        media_items.append(
            StoryMedia(
                media_type="image",
                media_url=cover_key,
                caption=_clean(story_input.get("image_caption")),
                alt_text=_clean(story_input.get("image_alt_text")),
                sort_order=0,
            )
        )

    return Story(
        location_id=location.id,
        author_id=_clean(story_input.get("author_id")) or SEED_OWNER_ID,
        title=clean_title,
        body=clean_body,
        category=clean_category,
        story_type=str(story_input.get("story_type") or ""),
        cover_image_url=cover_key,
        vibe_tags=_validate_vibe_tags(vibe_tags),
        historical_sources=_validate_sources(historical_sources),
        read_minutes=_read_minutes(clean_body),
        publication_status="published",
        is_curated=True,
        is_featured=bool(story_input.get("is_featured") or False),
        published_at=datetime.now(UTC),
        media=media_items,
    )


@router.get("/locations", response_model=list[SeedLocationRead])
async def list_seed_locations(_: DevDep, session: SessionDep) -> list[SeedLocationRead]:
    result = await session.execute(
        select(Location)
        .where(Location.visibility_status == "public")
        .order_by(Location.city, Location.name)
        .limit(200)
    )
    return [
        SeedLocationRead(id=location.id, name=location.name, city=location.city)
        for location in result.scalars()
    ]


class SeedStoryJSONPayload(BaseModel):
    """Everything except the cover-image file can arrive as one JSON object."""

    # Location: either reference an existing one, or describe a new place.
    existing_location_id: str | None = None
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    city: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    place_kind: str | None = Field(default=None, max_length=80)
    indoor_outdoor: str | None = Field(default=None, max_length=24)

    # Story.
    title: str
    body: str
    category: str
    story_type: str
    vibe_tags: list[str] = Field(default_factory=list, max_length=12)
    historical_sources: list[dict[str, str]] = Field(default_factory=list, max_length=30)
    author_id: str | None = SEED_OWNER_ID
    is_featured: bool = False

    # Image metadata (the image file itself is uploaded separately).
    image_caption: str | None = None
    image_alt_text: str | None = None

    @model_validator(mode="after")
    def require_location(self) -> SeedStoryJSONPayload:
        if not self.existing_location_id and not (self.name and self.latitude is not None):
            raise ValueError("Provide existing_location_id, or name with latitude and longitude")
        return self


@router.post("/story-json", response_model=StoryRead, status_code=status.HTTP_201_CREATED)
async def seed_story_json(
    _: DevDep,
    session: SessionDep,
    payload: Annotated[str, Form(description="The full seed story as a JSON object")],
    image: Annotated[UploadFile | None, File()] = None,
) -> StoryRead:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="payload must be valid JSON") from exc
    if not isinstance(raw, dict):
        raise HTTPException(status_code=422, detail="payload must be a JSON object")

    try:
        parsed = SeedStoryJSONPayload.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()[0]["msg"]) from exc

    data = parsed.model_dump(exclude_none=False)
    story = await _build_story_with_image(
        session, location_input=data, story_input=data, image=image
    )
    session.add(story)
    await session.commit()

    created = await session.scalar(
        select(Story)
        .options(joinedload(Story.location), selectinload(Story.media))
        .where(Story.id == story.id)
    )
    assert created is not None
    return await to_story_read(session, created)


@router.post("/story", response_model=StoryRead, status_code=status.HTTP_201_CREATED)
async def seed_story(
    _: DevDep,
    session: SessionDep,
    title: Annotated[str, Form()],
    body: Annotated[str, Form()],
    category: Annotated[str, Form()],
    story_type: Annotated[str, Form()],
    existing_location_id: Annotated[str | None, Form()] = None,
    name: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    latitude: Annotated[float | None, Form()] = None,
    longitude: Annotated[float | None, Form()] = None,
    city: Annotated[str | None, Form()] = None,
    country: Annotated[str | None, Form()] = None,
    place_kind: Annotated[str | None, Form()] = None,
    indoor_outdoor: Annotated[str | None, Form()] = None,
    vibe_tags: Annotated[str, Form()] = "",
    historical_sources: Annotated[str, Form()] = "",
    author_id: Annotated[str, Form()] = SEED_OWNER_ID,
    is_featured: Annotated[bool, Form()] = False,
    image: Annotated[UploadFile | None, File()] = None,
    image_caption: Annotated[str | None, Form()] = None,
    image_alt_text: Annotated[str | None, Form()] = None,
) -> StoryRead:
    clean_title = title.strip()
    clean_body = body.strip()
    clean_category = category.strip()

    if not clean_title or len(clean_title) > 240:
        raise HTTPException(
            status_code=422, detail="Title is required and must be under 240 characters"
        )
    if not clean_body or len(clean_body) > 100_000:
        raise HTTPException(
            status_code=422, detail="Body is required and must be under 100000 characters"
        )
    if not clean_category or len(clean_category) > 80:
        raise HTTPException(
            status_code=422, detail="Category is required and must be under 80 characters"
        )
    if story_type not in ALLOWED_STORY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"story_type must be one of {sorted(ALLOWED_STORY_TYPES)}",
        )

    if existing_location_id:
        try:
            location_uuid = uuid.UUID(existing_location_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="existing_location_id must be a UUID"
            ) from exc
        location = await session.scalar(
            select(Location).where(
                Location.id == location_uuid, Location.visibility_status == "public"
            )
        )
        if location is None:
            raise HTTPException(status_code=404, detail="Location not found")
    else:
        clean_name = _clean(name)
        if not clean_name or len(clean_name) > 200:
            raise HTTPException(
                status_code=422,
                detail="Provide an existing location or a name of 200 characters or fewer",
            )
        if latitude is None or longitude is None:
            raise HTTPException(
                status_code=422,
                detail="Latitude and longitude are required when creating a new location",
            )
        location = Location(
            id=uuid.uuid4(),
            name=clean_name,
            description=_clean(description),
            latitude=latitude,
            longitude=longitude,
            city=_clean(city),
            country=_clean(country),
            place_kind=_clean(place_kind),
            indoor_outdoor=_clean(indoor_outdoor),
            visibility_status="public",
        )
        session.add(location)

    cover_key: str | None = None
    media_items: list[StoryMedia] = []
    if image is not None and image.filename:
        payload = await image.read()
        if not payload:
            raise HTTPException(status_code=422, detail="Uploaded image was empty")
        try:
            cover_key = await store_uploaded_image(payload, SEED_OWNER_ID)
        except InvalidImage as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except StorageNotConfigured as exc:
            raise HTTPException(status_code=503, detail="Object storage is not configured") from exc
        media_items.append(
            StoryMedia(
                media_type="image",
                media_url=cover_key,
                caption=_clean(image_caption),
                alt_text=_clean(image_alt_text),
                sort_order=0,
            )
        )

    story = Story(
        location_id=location.id,
        author_id=_clean(author_id) or SEED_OWNER_ID,
        title=clean_title,
        body=clean_body,
        category=clean_category,
        story_type=story_type,
        cover_image_url=cover_key,
        vibe_tags=_parse_vibe_tags(vibe_tags),
        historical_sources=_parse_sources(historical_sources),
        read_minutes=_read_minutes(clean_body),
        publication_status="published",
        is_curated=True,
        is_featured=is_featured,
        published_at=datetime.now(UTC),
        media=media_items,
    )
    session.add(story)
    await session.commit()

    created = await session.scalar(
        select(Story)
        .options(joinedload(Story.location), selectinload(Story.media))
        .where(Story.id == story.id)
    )
    assert created is not None
    return await to_story_read(session, created)
