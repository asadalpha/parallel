import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.security import Principal, require_roles
from app.db.session import get_session
from app.models import Location, ModerationRecord, Report, Story, StoryAudio, StoryMedia
from app.schemas.catalog import (
    AudioGenerationRead,
    CuratedStoryCreate,
    CuratedStoryPatch,
    LocationCreate,
    LocationPatch,
    LocationRead,
    ModerationDecision,
    ModerationRecordRead,
    Page,
    ReportDecision,
    ReportRead,
    StoryCreate,
    StoryRead,
)
from app.services.catalog import to_story_read
from app.services.elevenlabs import VoiceServiceUnavailable, synthesize_story
from app.services.storage import (
    StorageNotConfigured,
    is_owned_upload_key,
    resolve_object_url,
    store_bytes,
)

router = APIRouter(prefix="/admin", tags=["administration"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
CuratorDep = Annotated[Principal, Depends(require_roles("curator", "admin"))]
AdminDep = Annotated[Principal, Depends(require_roles("admin"))]


def _validate_admin_media(principal: Principal, payload: StoryCreate) -> None:
    keys = [payload.cover_image_object_key, *(item.object_key for item in payload.media)]
    if any(key and not is_owned_upload_key(key, principal.user_id) for key in keys):
        raise HTTPException(status_code=422, detail="Media must be uploaded by the current account")


@router.post("/locations", response_model=LocationRead, status_code=status.HTTP_201_CREATED)
async def create_location(
    payload: LocationCreate, session: SessionDep, _: AdminDep
) -> LocationRead:
    location = Location(**payload.model_dump(), visibility_status="public")
    session.add(location)
    await session.commit()
    await session.refresh(location)
    return LocationRead.model_validate(location)


@router.patch("/locations/{location_id}", response_model=LocationRead)
async def update_location(
    location_id: uuid.UUID,
    payload: LocationPatch,
    session: SessionDep,
    _: AdminDep,
) -> LocationRead:
    location = await session.get(Location, location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(location, key, value)
    await session.commit()
    await session.refresh(location)
    return LocationRead.model_validate(location)


@router.post("/stories/curated", response_model=StoryRead, status_code=status.HTTP_201_CREATED)
async def create_curated_story(
    payload: CuratedStoryCreate, session: SessionDep, principal: AdminDep
) -> StoryRead:
    location = await session.scalar(
        select(Location).where(
            Location.id == payload.location_id, Location.visibility_status == "public"
        )
    )
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")
    _validate_admin_media(principal, payload)
    now = datetime.now(UTC)
    story = Story(
        location_id=payload.location_id,
        author_id=None,
        title=payload.title.strip(),
        body=payload.body.strip(),
        category=payload.category.strip(),
        story_type=payload.story_type,
        cover_image_url=payload.cover_image_object_key,
        vibe_tags=payload.vibe_tags,
        historical_sources=payload.historical_sources,
        read_minutes=max(1, (len(payload.body.split()) + 219) // 220),
        publication_status="published",
        is_curated=True,
        is_featured=payload.is_featured,
        published_at=now,
        media=[
            StoryMedia(
                media_type=item.media_type,
                media_url=item.object_key,
                caption=item.caption,
                alt_text=item.alt_text,
                sort_order=item.sort_order,
            )
            for item in payload.media
        ],
    )
    session.add(story)
    await session.commit()
    loaded = await session.scalar(
        select(Story)
        .options(joinedload(Story.location), selectinload(Story.media))
        .where(Story.id == story.id)
    )
    assert loaded is not None
    return await to_story_read(session, loaded)


@router.patch("/stories/{story_id}", response_model=StoryRead)
async def update_curated_story(
    story_id: uuid.UUID,
    payload: CuratedStoryPatch,
    session: SessionDep,
    principal: CuratorDep,
) -> StoryRead:
    story = await session.scalar(
        select(Story)
        .options(joinedload(Story.location), selectinload(Story.media))
        .where(Story.id == story_id, Story.is_curated.is_(True))
    )
    if story is None:
        raise HTTPException(status_code=404, detail="Curated story not found")

    changes = payload.model_dump(exclude_unset=True)
    media = changes.pop("media", None)
    cover_key = changes.get("cover_image_object_key", story.cover_image_url)
    _validate_admin_media(principal, payload) if media is not None else None
    if media is not None:
        story.media = [
            StoryMedia(
                media_type=item["media_type"],
                media_url=item["object_key"],
                caption=item.get("caption"),
                alt_text=item.get("alt_text"),
                sort_order=item.get("sort_order", 0),
            )
            for item in media
        ]
    if "cover_image_object_key" in changes:
        if cover_key and not is_owned_upload_key(cover_key, principal.user_id):
            raise HTTPException(
                status_code=422, detail="Media must be uploaded by the current account"
            )
        changes["cover_image_url"] = changes.pop("cover_image_object_key")
    if "location_id" in changes:
        location = await session.scalar(
            select(Location).where(
                Location.id == changes["location_id"], Location.visibility_status == "public"
            )
        )
        if location is None:
            raise HTTPException(status_code=404, detail="Location not found")
    changes.pop("is_featured", None)
    for key, value in changes.items():
        setattr(story, key, value)
    if "body" in changes:
        story.read_minutes = max(1, (len(story.body.split()) + 219) // 220)
    if "is_featured" in payload.model_fields_set and payload.is_featured is not None:
        story.is_featured = payload.is_featured

    await session.commit()
    updated = await session.scalar(
        select(Story)
        .options(joinedload(Story.location), selectinload(Story.media))
        .where(Story.id == story.id)
    )
    assert updated is not None
    return await to_story_read(session, updated)


@router.post("/stories/{story_id}/audio", response_model=AudioGenerationRead)
async def generate_story_audio(
    story_id: uuid.UUID, session: SessionDep, _: CuratorDep
) -> AudioGenerationRead:
    story = await session.scalar(
        select(Story).where(
            Story.id == story_id,
            Story.publication_status == "published",
        )
    )
    if story is None:
        raise HTTPException(status_code=404, detail="Published story not found")
    if not story.is_curated and story.audio_consent_at is None:
        raise HTTPException(status_code=409, detail="Author consent is required before narration")

    cached = await session.scalar(
        select(StoryAudio)
        .where(StoryAudio.story_id == story.id, StoryAudio.generation_status == "ready")
        .order_by(StoryAudio.created_at.desc())
    )
    if cached is not None:
        return AudioGenerationRead.model_validate(cached).model_copy(
            update={"audio_url": await resolve_object_url(cached.audio_url)}
        )

    if len(story.body) > 10_000:
        raise HTTPException(status_code=422, detail="Story is too long for one narration request")
    try:
        audio_bytes, voice_id = await synthesize_story(story.body)
        object_key = await store_bytes(
            f"audio/{story.id}/{uuid.uuid4()}.mp3", audio_bytes, "audio/mpeg"
        )
    except VoiceServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail="Audio generation is unavailable") from exc
    except StorageNotConfigured as exc:
        raise HTTPException(status_code=503, detail="Audio storage is unavailable") from exc

    audio = StoryAudio(
        story_id=story.id,
        audio_url=object_key,
        voice_identifier=voice_id,
        generation_status="ready",
        is_synthetic=True,
    )
    session.add(audio)
    await session.commit()
    await session.refresh(audio)
    return AudioGenerationRead.model_validate(audio).model_copy(
        update={"audio_url": await resolve_object_url(object_key)}
    )


@router.get("/moderation", response_model=Page[StoryRead])
async def moderation_queue(
    session: SessionDep,
    _: CuratorDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> Page[StoryRead]:
    filters = Story.publication_status == "submitted"
    total = int(await session.scalar(select(func.count(Story.id)).where(filters)) or 0)
    stories = await session.scalars(
        select(Story)
        .options(joinedload(Story.location), selectinload(Story.media))
        .where(filters)
        .order_by(Story.created_at, Story.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [await to_story_read(session, story) for story in stories.all()]
    return Page(items=items, page=page, page_size=page_size, total=total)


@router.post("/stories/{story_id}/decision", response_model=StoryRead)
async def decide_story(
    story_id: uuid.UUID,
    payload: ModerationDecision,
    session: SessionDep,
    principal: CuratorDep,
) -> StoryRead:
    story = await session.scalar(
        select(Story)
        .options(joinedload(Story.location), selectinload(Story.media))
        .where(Story.id == story_id)
    )
    if story is None:
        raise HTTPException(status_code=404, detail="Story not found")
    if payload.decision in {"approve", "reject"} and story.publication_status != "submitted":
        raise HTTPException(status_code=409, detail="Only submitted stories can be reviewed")
    if payload.decision == "remove":
        if principal.role != "admin":
            raise HTTPException(status_code=403, detail="Only admins can remove published stories")
        if story.publication_status not in {"published", "submitted", "approved"}:
            raise HTTPException(
                status_code=409, detail="Story cannot be removed from its current state"
            )
        story.publication_status = "removed"
        decision = "removed"
    elif payload.decision == "approve":
        story.publication_status = "published"
        story.published_at = datetime.now(UTC)
        decision = "approved"
    else:
        story.publication_status = "rejected"
        decision = "rejected"

    session.add(
        ModerationRecord(
            story_id=story.id,
            reviewer_id=principal.user_id,
            decision=decision,
            reason=payload.reason,
        )
    )
    await session.commit()
    return await to_story_read(session, story)


@router.get("/reports", response_model=Page[ReportRead])
async def reports_list(
    session: SessionDep,
    _: CuratorDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
    status_filter: Annotated[
        str, Query(alias="status", pattern="^(open|reviewed|dismissed)$")
    ] = "open",
) -> Page[ReportRead]:
    filters = Report.status == status_filter
    total = int(await session.scalar(select(func.count(Report.id)).where(filters)) or 0)
    reports = await session.scalars(
        select(Report)
        .where(filters)
        .order_by(Report.created_at, Report.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return Page(
        items=[ReportRead.model_validate(report) for report in reports.all()],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/reports/{report_id}/decision", response_model=ReportRead)
async def decide_report(
    report_id: uuid.UUID,
    payload: ReportDecision,
    session: SessionDep,
    _: CuratorDep,
) -> ReportRead:
    report = await session.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    report.status = payload.status
    report.resolved_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(report)
    return ReportRead.model_validate(report)


@router.get("/stories/{story_id}/moderation", response_model=list[ModerationRecordRead])
async def moderation_history(
    story_id: uuid.UUID, session: SessionDep, _: CuratorDep
) -> list[ModerationRecordRead]:
    records = await session.scalars(
        select(ModerationRecord)
        .where(ModerationRecord.story_id == story_id)
        .order_by(ModerationRecord.created_at, ModerationRecord.id)
    )
    return [ModerationRecordRead.model_validate(record) for record in records.all()]
