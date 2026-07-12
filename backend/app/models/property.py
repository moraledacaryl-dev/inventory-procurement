import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def uid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PropertyBalance(Base):
    __tablename__ = "property_balances"
    __table_args__ = (UniqueConstraint("item_id", "location_id", "condition_id", name="uq_property_balance_bucket"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id"), index=True)
    location_id: Mapped[str] = mapped_column(String(36), ForeignKey("locations.id"), index=True)
    condition_id: Mapped[str] = mapped_column(String(36), ForeignKey("operational_dimensions.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PropertyMovement(Base):
    __tablename__ = "property_movements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    movement_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    source_location_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("locations.id"), nullable=True, index=True)
    destination_location_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("locations.id"), nullable=True, index=True)
    source_condition_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("operational_dimensions.id"), nullable=True)
    destination_condition_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("operational_dimensions.id"), nullable=True)
    movement_reason_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("operational_dimensions.id"), nullable=True)
    assignee_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class HotelParProfile(Base):
    __tablename__ = "hotel_par_profiles"
    __table_args__ = (UniqueConstraint("code", name="uq_hotel_par_profile_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160))
    profile_type: Mapped[str] = mapped_column(String(40), default="room_type")
    location_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("locations.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HotelParLine(Base):
    __tablename__ = "hotel_par_lines"
    __table_args__ = (UniqueConstraint("profile_id", "item_id", name="uq_hotel_par_line_item"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("hotel_par_profiles.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id"), index=True)
    par_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
