import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def uid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OperationalDimension(Base):
    """Editable master data used to classify inventory and future property records.

    ``dimension_type`` identifies the master (workspace, record_class, item_type,
    department, outlet, cost_center, and future asset/property controls).
    ``behavior_key`` is a protected machine meaning; labels and codes remain editable.
    """

    __tablename__ = "operational_dimensions"
    __table_args__ = (
        UniqueConstraint("dimension_type", "code", name="uq_operational_dimension_type_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    dimension_type: Mapped[str] = mapped_column(String(50), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    behavior_key: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("operational_dimensions.id"), nullable=True, index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("operational_dimensions.id"), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ItemWorkspaceAssignment(Base):
    __tablename__ = "item_workspace_assignments"
    __table_args__ = (
        UniqueConstraint("item_id", "workspace_id", name="uq_item_workspace_assignment"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("operational_dimensions.id"), index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
