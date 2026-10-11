from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import CheckConstraint, Computed, DateTime, Float, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.story import Story


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="latitude_in_range"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="longitude_in_range"),
        CheckConstraint(
            "visibility_status IN ('public', 'hidden', 'removed')",
            name="visibility_status_allowed",
        ),
        Index("ix_locations_geom", "geom", postgresql_using="gist"),
        Index(
            "ix_locations_geom_geography",
            text("(geom::geography)"),
            postgresql_using="gist",
        ),
        Index("ix_locations_city_country", "city", "country"),
        {"comment": "Real-world places that can hold multiple independent stories."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        Computed("ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)", persisted=True),
        nullable=False,
    )
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    place_kind: Mapped[str | None] = mapped_column(String(80), nullable=True)
    accessibility_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    indoor_outdoor: Mapped[str | None] = mapped_column(String(24), nullable=True)
    visibility_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="public", server_default=text("'public'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    stories: Mapped[list[Story]] = relationship(back_populates="location", passive_deletes="all")
