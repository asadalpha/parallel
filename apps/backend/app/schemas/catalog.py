from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

StoryType = Literal["history", "personal_memory", "legend", "fiction", "editorial"]
VibeTag = Annotated[str, Field(min_length=1, max_length=40)]


class Page[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int


class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    latitude: float
    longitude: float
    city: str | None
    country: str | None
    place_kind: str | None
    accessibility_status: str | None
    indoor_outdoor: str | None


class MediaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    media_type: str
    media_url: str
    caption: str | None
    alt_text: str | None
    sort_order: int


class MediaInput(BaseModel):
    media_type: Literal["image"] = "image"
    object_key: str = Field(min_length=1, max_length=512)
    caption: str | None = Field(default=None, max_length=500)
    alt_text: str | None = Field(default=None, max_length=500)
    sort_order: int = Field(default=0, ge=0)


class AudioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    audio_url: str
    voice_identifier: str
    duration_seconds: int | None
    is_synthetic: bool
    created_at: datetime


class StorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    location_id: uuid.UUID
    title: str
    category: str
    story_type: StoryType
    cover_image_url: str | None
    vibe_tags: list[VibeTag]
    read_minutes: int
    is_curated: bool
    is_featured: bool
    location: LocationRead
    distance_meters: float | None = None
    audio_available: bool = False
    other_chapter_count: int = 0


class StoryRead(StorySummary):
    author_id: str | None
    body: str
    description: str | None = None
    publication_status: str
    created_at: datetime
    updated_at: datetime
    historical_sources: list[dict[str, str]]
    published_at: datetime | None
    media: list[MediaRead] = Field(default_factory=list)
    audio: list[AudioRead] = Field(default_factory=list)
    other_chapter_count: int = 0


class LocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    city: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    place_kind: str | None = Field(default=None, max_length=80)
    accessibility_status: str | None = Field(default=None, max_length=40)
    indoor_outdoor: str | None = Field(default=None, max_length=24)


class LocationPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    city: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    place_kind: str | None = Field(default=None, max_length=80)
    accessibility_status: str | None = Field(default=None, max_length=40)
    indoor_outdoor: str | None = Field(default=None, max_length=24)
    visibility_status: Literal["public", "hidden", "removed"] | None = None

    @model_validator(mode="after")
    def validate_location_fields(self) -> LocationPatch:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        nullable_fields = {
            "description",
            "city",
            "country",
            "place_kind",
            "accessibility_status",
            "indoor_outdoor",
        }
        for field in self.model_fields_set:
            if field not in nullable_fields and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        if (self.latitude is None) != (self.longitude is None):
            if "latitude" in self.model_fields_set or "longitude" in self.model_fields_set:
                raise ValueError("latitude and longitude must be updated together")
        return self


class StoryCreate(BaseModel):
    location_id: uuid.UUID
    title: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1, max_length=100_000)
    description: str | None = Field(default=None, max_length=600)
    category: str = Field(min_length=1, max_length=80)
    story_type: StoryType
    cover_image_object_key: str | None = Field(default=None, max_length=512)
    vibe_tags: list[VibeTag] = Field(default_factory=list, max_length=12)
    historical_sources: list[dict[str, str]] = Field(default_factory=list, max_length=30)
    media: list[MediaInput] = Field(default_factory=list, max_length=10)


class CuratedStoryCreate(StoryCreate):
    is_featured: bool = False


class StoryPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    body: str | None = Field(default=None, min_length=1, max_length=100_000)
    description: str | None = Field(default=None, max_length=600)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    story_type: StoryType | None = None
    location_id: uuid.UUID | None = None
    cover_image_object_key: str | None = Field(default=None, max_length=512)
    vibe_tags: list[VibeTag] | None = Field(default=None, max_length=12)
    historical_sources: list[dict[str, str]] | None = Field(default=None, max_length=30)
    media: list[MediaInput] | None = Field(default=None, max_length=10)

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> StoryPatch:
        for field in (
            "title",
            "body",
            "category",
            "story_type",
            "location_id",
            "vibe_tags",
            "historical_sources",
            "media",
        ):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class CuratedStoryPatch(StoryPatch):
    is_featured: bool | None = None


class ReportCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class ModerationDecision(BaseModel):
    decision: Literal["approve", "reject", "remove"]
    reason: str | None = Field(default=None, max_length=1000)


class ReportDecision(BaseModel):
    status: Literal["reviewed", "dismissed"]


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    story_id: uuid.UUID
    reporter_id: str
    reason: str
    status: str
    created_at: datetime
    resolved_at: datetime | None


class ModerationRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    story_id: uuid.UUID
    reviewer_id: str
    decision: str
    reason: str | None
    created_at: datetime


class ConciergeRequest(BaseModel):
    mood: Literal["cozy", "curious", "spooky", "reflective", "surprise"]
    time_available_minutes: int = Field(ge=1, le=480)
    travel_preference: Literal["walking_nearby", "a_little_farther", "any_distance"]
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    search_radius_meters: int | None = Field(default=None, ge=100, le=50_000)

    @model_validator(mode="after")
    def validate_search_origin(self) -> ConciergeRequest:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        if self.latitude is None and not self.city:
            raise ValueError("provide a city or both latitude and longitude")
        return self


class AnotherAngleRequest(BaseModel):
    location_id: uuid.UUID
    exclude_story_id: uuid.UUID


class RecommendationRead(BaseModel):
    story: StorySummary
    explanation: str
    audio_available: bool
    other_chapter_count: int
    fallback_used: bool


class StoryAssistRequest(BaseModel):
    task: Literal["title", "polish"]
    title: str | None = Field(default=None, max_length=240)
    body: str = Field(min_length=1, max_length=20_000)


class StoryAssistRead(BaseModel):
    suggestion: str
    task: Literal["title", "polish"]


class AudioGenerationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    audio_url: str
    voice_identifier: str
    duration_seconds: int | None
    is_synthetic: bool
    created_at: datetime


class MediaUploadRead(BaseModel):
    object_key: str
    url: str
    content_type: str


class DescriptionDraftRead(BaseModel):
    description: str
    is_ai_draft: bool = True


class AudioConsentRequest(BaseModel):
    granted: bool


class AudioConsentRead(BaseModel):
    granted: bool
    consented_at: datetime | None


class VisitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    location_id: uuid.UUID
    created_at: datetime


class Bounds(BaseModel):
    min_lat: float = Field(ge=-90, le=90)
    min_lon: float = Field(ge=-180, le=180)
    max_lat: float = Field(ge=-90, le=90)
    max_lon: float = Field(ge=-180, le=180)

    @model_validator(mode="after")
    def validate_order(self) -> Bounds:
        if self.min_lat > self.max_lat or self.min_lon > self.max_lon:
            raise ValueError("minimum bounds must not exceed maximum bounds")
        return self
