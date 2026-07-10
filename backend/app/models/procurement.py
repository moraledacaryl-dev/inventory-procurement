import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

def uid(): return str(uuid.uuid4())
def utcnow(): return datetime.now(timezone.utc)

class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    contact_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_terms_days: Mapped[int] = mapped_column(default=0)
    tax_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class SupplierItem(Base):
    __tablename__ = "supplier_items"
    __table_args__ = (UniqueConstraint("supplier_id", "item_id", name="uq_supplier_item"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    supplier_id: Mapped[str] = mapped_column(String(36), ForeignKey("suppliers.id"), index=True)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id"), index=True)
    supplier_sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    lead_time_days: Mapped[int] = mapped_column(default=0)
    minimum_order_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=1)
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False)

class PurchaseRequisition(Base):
    __tablename__ = "purchase_requisitions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    requisition_number: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    department: Mapped[str] = mapped_column(String(100))
    needed_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    requested_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    approved_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    lines: Mapped[list["PurchaseRequisitionLine"]] = relationship(back_populates="requisition", cascade="all, delete-orphan")

class PurchaseRequisitionLine(Base):
    __tablename__ = "purchase_requisition_lines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    requisition_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_requisitions.id"), index=True)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    estimated_unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    notes: Mapped[str | None] = mapped_column(String(240), nullable=True)
    requisition: Mapped[PurchaseRequisition] = relationship(back_populates="lines")

class SupplierQuotation(Base):
    __tablename__ = "supplier_quotations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    quotation_number: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    requisition_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_requisitions.id"), index=True)
    supplier_id: Mapped[str] = mapped_column(String(36), ForeignKey("suppliers.id"), index=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_days: Mapped[int] = mapped_column(default=0)
    payment_terms_days: Mapped[int] = mapped_column(default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="submitted")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    lines: Mapped[list["SupplierQuotationLine"]] = relationship(back_populates="quotation", cascade="all, delete-orphan")

class SupplierQuotationLine(Base):
    __tablename__ = "supplier_quotation_lines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    quotation_id: Mapped[str] = mapped_column(String(36), ForeignKey("supplier_quotations.id"), index=True)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    quotation: Mapped[SupplierQuotation] = relationship(back_populates="lines")

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    purchase_order_number: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    supplier_id: Mapped[str] = mapped_column(String(36), ForeignKey("suppliers.id"), index=True)
    requisition_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("purchase_requisitions.id"), nullable=True)
    quotation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("supplier_quotations.id"), nullable=True)
    delivery_location_id: Mapped[str] = mapped_column(String(36), ForeignKey("locations.id"))
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    approved_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates="purchase_order", cascade="all, delete-orphan")

class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    purchase_order_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_orders.id"), index=True)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id"))
    ordered_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    returned_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="lines")

class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    goods_receipt_number: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    purchase_order_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_orders.id"), index=True)
    stock_document_id: Mapped[str] = mapped_column(String(36), ForeignKey("stock_documents.id"), unique=True)
    delivery_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    received_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    lines: Mapped[list["GoodsReceiptLine"]] = relationship(back_populates="goods_receipt", cascade="all, delete-orphan")

class GoodsReceiptLine(Base):
    __tablename__ = "goods_receipt_lines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    goods_receipt_id: Mapped[str] = mapped_column(String(36), ForeignKey("goods_receipts.id"), index=True)
    purchase_order_line_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_order_lines.id"))
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id"))
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    accepted_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    rejected_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    goods_receipt: Mapped[GoodsReceipt] = relationship(back_populates="lines")

class PurchaseReturn(Base):
    __tablename__ = "purchase_returns"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    return_number: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    purchase_order_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_orders.id"), index=True)
    stock_document_id: Mapped[str] = mapped_column(String(36), ForeignKey("stock_documents.id"), unique=True)
    reason: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
