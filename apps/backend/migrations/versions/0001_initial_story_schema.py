"""Create the initial location and story schema.

Revision ID: 0001_initial_story_schema
Revises:
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_story_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
            sa.Computed("ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)", persisted=True),
            nullable=False,
        ),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("place_kind", sa.String(length=80), nullable=True),
        sa.Column("accessibility_status", sa.String(length=40), nullable=True),
        sa.Column("indoor_outdoor", sa.String(length=24), nullable=True),
        sa.Column(
            "visibility_status", sa.String(length=32), server_default="public", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="latitude_in_range"),
        sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="longitude_in_range"),
        sa.CheckConstraint(
            "visibility_status IN ('public', 'hidden', 'removed')",
            name="visibility_status_allowed",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_locations"),
        comment="Real-world places that can hold multiple independent stories.",
    )
    op.create_index("ix_locations_geom", "locations", ["geom"], postgresql_using="gist")
    op.create_index(
        "ix_locations_geom_geography",
        "locations",
        [sa.text("(geom::geography)")],
        postgresql_using="gist",
    )
    op.create_index("ix_locations_city_country", "locations", ["city", "country"])

    op.create_table(
        "stories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("cover_image_url", sa.String(length=2048), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("story_type", sa.String(length=32), nullable=False),
        sa.Column(
            "vibe_tags",
            postgresql.ARRAY(sa.String(length=40)),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
        ),
        sa.Column("read_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "publication_status", sa.String(length=24), server_default="draft", nullable=False
        ),
        sa.Column("is_curated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_featured", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "historical_sources",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("ai_assisted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "story_type IN ('history', 'personal_memory', 'legend', 'fiction', 'editorial')",
            name="story_type_allowed",
        ),
        sa.CheckConstraint(
            "publication_status IN "
            "('draft', 'submitted', 'approved', 'published', 'rejected', 'removed')",
            name="publication_status_allowed",
        ),
        sa.CheckConstraint("read_minutes > 0", name="read_minutes_positive"),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            ondelete="RESTRICT",
            name="fk_stories_location_id_locations",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stories"),
        comment="Independent narratives associated with a real-world location.",
    )
    op.create_index("ix_stories_location_status", "stories", ["location_id", "publication_status"])
    op.create_index("ix_stories_status_created", "stories", ["publication_status", "created_at"])
    op.create_index("ix_stories_author_status", "stories", ["author_id", "publication_status"])

    op.create_table(
        "story_media",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("media_type", sa.String(length=24), nullable=False),
        sa.Column("media_url", sa.String(length=2048), nullable=False),
        sa.Column("caption", sa.String(length=500), nullable=True),
        sa.Column("alt_text", sa.String(length=500), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        sa.ForeignKeyConstraint(
            ["story_id"], ["stories.id"], ondelete="CASCADE", name="fk_story_media_story_id_stories"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_story_media"),
    )
    op.create_index("ix_story_media_story_order", "story_media", ["story_id", "sort_order"])


def downgrade() -> None:
    op.drop_index("ix_story_media_story_order", table_name="story_media")
    op.drop_table("story_media")
    op.drop_index("ix_stories_author_status", table_name="stories")
    op.drop_index("ix_stories_status_created", table_name="stories")
    op.drop_index("ix_stories_location_status", table_name="stories")
    op.drop_table("stories")
    op.drop_index("ix_locations_city_country", table_name="locations")
    op.drop_index("ix_locations_geom_geography", table_name="locations")
    op.drop_index("ix_locations_geom", table_name="locations")
    op.drop_table("locations")
