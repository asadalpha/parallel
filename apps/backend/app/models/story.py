from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.location import Location

STORY_TYPES = ("history", "personal_memory", "legend", "fiction", "editorial")
PUBLICATION_STATES = ("draft", "submitted", "approved", "published", "rejected", "removed")


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class Story(Base):
    __tablename__ = "stories"
    __table_args__ = (
        CheckConstraint(f"story_type IN ({_sql_values(STORY_TYPES)})", name="story_type_allowed"),
        CheckConstraint(
            f"publication_status IN ({_sql_values(PUBLICATION_STATES)})",
            name="publication_status_allowed",
        ),
        CheckConstraint("read_minutes > 0", name="read_minutes_positive"),
        Index("ix_stories_location_status", "location_id", "publication_status"),
        Index("ix_stories_status_created", "publication_status", "created_at"),
        Index("ix_stories_author_status", "author_id", "publication_status"),
        {"comment": "Independent narratives associated with a real-world location."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False
    )
    # Better Auth owns users and their IDs; the API must not create a parallel user table.
    author_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(String(600), nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    story_type: Mapped[str] = mapped_column(String(32), nullable=False)
    vibe_tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), nullable=False, default=list, server_default=text("'{}'")
    )
    read_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    publication_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="draft", server_default=text("'draft'")
    )
    is_curated: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default=text("false")
    )
    is_featured: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default=text("false")
    )
    historical_sources: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    ai_assisted: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    audio_consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    location: Mapped[Location] = relationship(back_populates="stories")
    media: Mapped[list[StoryMedia]] = relationship(
        back_populates="story", cascade="all, delete-orphan", passive_deletes=True
    )


class StoryMedia(Base):
    __tablename__ = "story_media"
    __table_args__ = (
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        Index("ix_story_media_story_order", "story_id", "sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    media_type: Mapped[str] = mapped_column(String(24), nullable=False, default="image")
    media_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    caption: Mapped[str | None] = mapped_column(String(500), nullable=True)
    alt_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    story: Mapped[Story] = relationship(back_populates="media")


class StoryAudio(Base):
    __tablename__ = "story_audio"
    __table_args__ = (
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds > 0", name="duration_positive"
        ),
        CheckConstraint(
            "generation_status IN ('pending', 'ready', 'failed', 'revoked')",
            name="generation_status_allowed",
        ),
        Index("ix_story_audio_story_status", "story_id", "generation_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    audio_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    voice_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    generation_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="ready", server_default=text("'ready'")
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(
        nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    story: Mapped[Story] = relationship()


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'reviewed', 'dismissed')", name="status_allowed"),
        Index("ix_reports_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    reporter_id: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="open", server_default=text("'open'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModerationRecord(Base):
    __tablename__ = "moderation_records"
    __table_args__ = (Index("ix_moderation_story_created", "story_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_id: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Visit(Base):
    __tablename__ = "visits"
    __table_args__ = (
        Index("ix_visits_location_created", "location_id", "created_at"),
        Index("ix_visits_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
