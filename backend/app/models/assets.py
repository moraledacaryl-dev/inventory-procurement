import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def uid() -> str: return str(uuid.uuid4())
def utcnow() -> datetime: return datetime.now(timezone.utc)


class FixedAsset(Base):
    __tablename__ = "fixed_assets"
    asset_tag: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id"), index=True)
    asset_class_id: Mapped[str] = mapped_column(String(36), ForeignKey("operational_dimensions.id"), index=True)
    depreciation_method_id: Mapped[str] = mapped_column(String(36), ForeignKey("operational_dimensions.id"), index=True)
    location_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("locations.id"), index=True)
    department_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("operational_dimensions.id"), index=True)
    cost_center_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("operational_dimensions.id"), index=True)
    custodian_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    supplier_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("suppliers.id"))
    purchase_order_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("purchase_orders.id"))
    goods_receipt_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("goods_receipts.id"))
    serial_number: Mapped[str | None] = mapped_column(String(160), index=True)
    model_number: Mapped[str | None] = mapped_column(String(160))
    acquisition_date: Mapped[date] = mapped_column(Date)
    placed_in_service_date: Mapped[date | None] = mapped_column(Date)
    acquisition_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    capitalized_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    residual_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    useful_life_months: Mapped[int] = mapped_column(default=60)
    accumulated_depreciation: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    impairment_loss: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    status: Mapped[str] = mapped_column(String(40), default="candidate", index=True)
    condition: Mapped[str] = mapped_column(String(40), default="good")
    warranty_expiry: Mapped[date | None] = mapped_column(Date)
    disposal_date: Mapped[date | None] = mapped_column(Date)
    disposal_proceeds: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class DepreciationRun(Base):
    __tablename__ = "depreciation_runs"
    __table_args__ = (UniqueConstraint("period", name="uq_depreciation_run_period"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    period: Mapped[str] = mapped_column(String(7), index=True)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    posted_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DepreciationLine(Base):
    __tablename__ = "depreciation_lines"
    __table_args__ = (UniqueConstraint("run_id", "asset_id", name="uq_depreciation_line_asset"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("depreciation_runs.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("fixed_assets.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    opening_accumulated: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    closing_accumulated: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    closing_net_book_value: Mapped[Decimal] = mapped_column(Numeric(18, 2))


class AssetEvent(Base):
    __tablename__ = "asset_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("fixed_assets.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    event_date: Mapped[date] = mapped_column(Date)
    from_location_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("locations.id"))
    to_location_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("locations.id"))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
