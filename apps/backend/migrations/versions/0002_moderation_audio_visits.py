"""Add consent, audio, reporting, moderation, and visit records.

Revision ID: 0002_moderation_audio_visits
Revises: 0001_initial_story_schema
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_moderation_audio_visits"
down_revision: str | None = "0001_initial_story_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stories", sa.Column("audio_consent_at", sa.DateTime(timezone=True)))

    op.create_table(
        "story_audio",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audio_url", sa.String(length=2048), nullable=False),
        sa.Column("voice_identifier", sa.String(length=128), nullable=False),
        sa.Column(
            "generation_status", sa.String(length=24), server_default="ready", nullable=False
        ),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds > 0", name="duration_positive"
        ),
        sa.CheckConstraint(
            "generation_status IN ('pending', 'ready', 'failed', 'revoked')",
            name="generation_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["story_id"], ["stories.id"], ondelete="CASCADE", name="fk_story_audio_story_id_stories"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_story_audio"),
    )
    op.create_index("ix_story_audio_story_status", "story_audio", ["story_id", "generation_status"])

    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reporter_id", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="open", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('open', 'reviewed', 'dismissed')", name="status_allowed"),
        sa.ForeignKeyConstraint(
            ["story_id"], ["stories.id"], ondelete="CASCADE", name="fk_reports_story_id_stories"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reports"),
    )
    op.create_index("ix_reports_status_created", "reports", ["status", "created_at"])

    op.create_table(
        "moderation_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_id", sa.String(length=255), nullable=False),
        sa.Column("decision", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["story_id"],
            ["stories.id"],
            ondelete="CASCADE",
            name="fk_moderation_records_story_id_stories",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_moderation_records"),
    )
    op.create_index("ix_moderation_story_created", "moderation_records", ["story_id", "created_at"])

    op.create_table(
        "visits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            ondelete="CASCADE",
            name="fk_visits_location_id_locations",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_visits"),
    )
    op.create_index("ix_visits_location_created", "visits", ["location_id", "created_at"])
    op.create_index("ix_visits_user_created", "visits", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_visits_user_created", table_name="visits")
    op.drop_index("ix_visits_location_created", table_name="visits")
    op.drop_table("visits")
    op.drop_index("ix_moderation_story_created", table_name="moderation_records")
    op.drop_table("moderation_records")
    op.drop_index("ix_reports_status_created", table_name="reports")
    op.drop_table("reports")
    op.drop_index("ix_story_audio_story_status", table_name="story_audio")
    op.drop_table("story_audio")
    op.drop_column("stories", "audio_consent_at")
