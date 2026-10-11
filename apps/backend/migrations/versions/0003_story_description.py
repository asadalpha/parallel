"""Add an author-approved short description to stories.

Revision ID: 0003_story_description
Revises: 0002_moderation_audio_visits
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_story_description"
down_revision: str | None = "0002_moderation_audio_visits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stories", sa.Column("description", sa.String(600), nullable=True))


def downgrade() -> None:
    op.drop_column("stories", "description")
