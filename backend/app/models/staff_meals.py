import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def uid():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


class StaffMeal(Base):
    __tablename__ = "staff_meals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    meal_number: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    meal_name: Mapped[str] = mapped_column(String(180))
    meal_period: Mapped[str | None] = mapped_column(String(40), nullable=True)
    servings: Mapped[int] = mapped_column(Integer)
    location_id: Mapped[str] = mapped_column(String(36), ForeignKey("locations.id"), index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="posted", index=True)
    posted_document_id: Mapped[str] = mapped_column(String(36), ForeignKey("stock_documents.id"), unique=True)
    reversal_document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stock_documents.id"), unique=True, nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    reversed_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list["StaffMealLine"]] = relationship(
        back_populates="meal", cascade="all, delete-orphan", order_by="StaffMealLine.line_number"
    )


class StaffMealLine(Base):
    __tablename__ = "staff_meal_lines"
    __table_args__ = (UniqueConstraint("staff_meal_id", "line_number", name="uq_staff_meal_line"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    staff_meal_id: Mapped[str] = mapped_column(String(36), ForeignKey("staff_meals.id"), index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4))

    meal: Mapped[StaffMeal] = relationship(back_populates="lines")
