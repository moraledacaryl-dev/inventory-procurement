import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

def uid(): return str(uuid.uuid4())
def utcnow(): return datetime.now(timezone.utc)

class Category(Base):
    __tablename__ = "categories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class UnitOfMeasure(Base):
    __tablename__ = "units_of_measure"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    precision: Mapped[int] = mapped_column(default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Location(Base):
    __tablename__ = "locations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    location_type: Mapped[str] = mapped_column(String(40), default="storeroom")
    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("locations.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Item(Base):
    __tablename__ = "items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    sku: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[str] = mapped_column(String(36), ForeignKey("categories.id"))
    base_unit_id: Mapped[str] = mapped_column(String(36), ForeignKey("units_of_measure.id"))
    track_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_negative_stock: Mapped[bool] = mapped_column(Boolean, default=False)
    minimum_stock: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    standard_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class StockDocument(Base):
    __tablename__ = "stock_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_number: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    document_type: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(20), default="posted")
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    posted_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    reversed_document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stock_documents.id"), nullable=True)
    movements: Mapped[list["StockMovement"]] = relationship(back_populates="document", cascade="all, delete-orphan")

class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (UniqueConstraint("document_id", "line_number", name="uq_stock_document_line"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("stock_documents.id"), index=True)
    line_number: Mapped[int] = mapped_column()
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id"), index=True)
    location_id: Mapped[str] = mapped_column(String(36), ForeignKey("locations.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    document: Mapped[StockDocument] = relationship(back_populates="movements")

class StockBalance(Base):
    __tablename__ = "stock_balances"
    __table_args__ = (UniqueConstraint("item_id", "location_id", name="uq_stock_balance_item_location"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id"), index=True)
    location_id: Mapped[str] = mapped_column(String(36), ForeignKey("locations.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    average_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class CountSession(Base):
    __tablename__ = "count_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    count_number: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    location_id: Mapped[str] = mapped_column(String(36), ForeignKey("locations.id"))
    status: Mapped[str] = mapped_column(String(20), default="open")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    posted_document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stock_documents.id"), nullable=True)
    lines: Mapped[list["CountLine"]] = relationship(back_populates="session", cascade="all, delete-orphan")

class CountLine(Base):
    __tablename__ = "count_lines"
    __table_args__ = (UniqueConstraint("count_session_id", "item_id", name="uq_count_session_item"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    count_session_id: Mapped[str] = mapped_column(String(36), ForeignKey("count_sessions.id"))
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id"))
    system_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    counted_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    note: Mapped[str | None] = mapped_column(String(240), nullable=True)
    session: Mapped[CountSession] = relationship(back_populates="lines")
