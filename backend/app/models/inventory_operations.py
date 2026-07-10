import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

def uid(): return str(uuid.uuid4())
def utcnow(): return datetime.now(timezone.utc)

class ItemBarcode(Base):
    __tablename__='item_barcodes'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    item_id:Mapped[str]=mapped_column(String(36),ForeignKey('items.id'),index=True)
    barcode:Mapped[str]=mapped_column(String(100),unique=True,index=True)
    barcode_type:Mapped[str]=mapped_column(String(30),default='EAN13')
    is_primary:Mapped[bool]=mapped_column(Boolean,default=False)

class UnitConversion(Base):
    __tablename__='unit_conversions'
    __table_args__=(UniqueConstraint('item_id','from_unit_id','to_unit_id',name='uq_item_unit_conversion'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    item_id:Mapped[str]=mapped_column(String(36),ForeignKey('items.id'),index=True)
    from_unit_id:Mapped[str]=mapped_column(String(36),ForeignKey('units_of_measure.id'))
    to_unit_id:Mapped[str]=mapped_column(String(36),ForeignKey('units_of_measure.id'))
    multiplier:Mapped[Decimal]=mapped_column(Numeric(18,6))
    is_active:Mapped[bool]=mapped_column(Boolean,default=True)

class ItemLocationSetting(Base):
    __tablename__='item_location_settings'
    __table_args__=(UniqueConstraint('item_id','location_id',name='uq_item_location_setting'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    item_id:Mapped[str]=mapped_column(String(36),ForeignKey('items.id'),index=True)
    location_id:Mapped[str]=mapped_column(String(36),ForeignKey('locations.id'),index=True)
    minimum_stock:Mapped[Decimal]=mapped_column(Numeric(18,4),default=0)
    reorder_quantity:Mapped[Decimal]=mapped_column(Numeric(18,4),default=0)
    maximum_stock:Mapped[Decimal|None]=mapped_column(Numeric(18,4),nullable=True)
    preferred_supplier_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('suppliers.id'),nullable=True)
    cycle_count_days:Mapped[int]=mapped_column(default=30)
    is_active:Mapped[bool]=mapped_column(Boolean,default=True)

class InventoryLot(Base):
    __tablename__='inventory_lots'
    __table_args__=(UniqueConstraint('item_id','lot_number',name='uq_item_lot_number'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    item_id:Mapped[str]=mapped_column(String(36),ForeignKey('items.id'),index=True)
    lot_number:Mapped[str]=mapped_column(String(100),index=True)
    manufactured_date:Mapped[date|None]=mapped_column(Date,nullable=True)
    expiry_date:Mapped[date|None]=mapped_column(Date,nullable=True,index=True)
    supplier_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('suppliers.id'),nullable=True)
    status:Mapped[str]=mapped_column(String(30),default='active',index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class LotBalance(Base):
    __tablename__='lot_balances'
    __table_args__=(UniqueConstraint('lot_id','location_id',name='uq_lot_location_balance'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    lot_id:Mapped[str]=mapped_column(String(36),ForeignKey('inventory_lots.id'),index=True)
    location_id:Mapped[str]=mapped_column(String(36),ForeignKey('locations.id'),index=True)
    quantity:Mapped[Decimal]=mapped_column(Numeric(18,4),default=0)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,onupdate=utcnow)

class StockReservation(Base):
    __tablename__='stock_reservations'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    reservation_number:Mapped[str]=mapped_column(String(60),unique=True,index=True)
    item_id:Mapped[str]=mapped_column(String(36),ForeignKey('items.id'),index=True)
    location_id:Mapped[str]=mapped_column(String(36),ForeignKey('locations.id'),index=True)
    quantity:Mapped[Decimal]=mapped_column(Numeric(18,4))
    reference_type:Mapped[str]=mapped_column(String(60))
    reference_id:Mapped[str]=mapped_column(String(100))
    status:Mapped[str]=mapped_column(String(30),default='active',index=True)
    expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_by_user_id:Mapped[str]=mapped_column(String(36),ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class TransferOrder(Base):
    __tablename__='transfer_orders'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    transfer_number:Mapped[str]=mapped_column(String(60),unique=True,index=True)
    source_location_id:Mapped[str]=mapped_column(String(36),ForeignKey('locations.id'))
    destination_location_id:Mapped[str]=mapped_column(String(36),ForeignKey('locations.id'))
    status:Mapped[str]=mapped_column(String(30),default='draft',index=True)
    notes:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_by_user_id:Mapped[str]=mapped_column(String(36),ForeignKey('users.id'))
    dispatched_by_user_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('users.id'),nullable=True)
    received_by_user_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('users.id'),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    dispatched_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    received_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    stock_document_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('stock_documents.id'),nullable=True)
    lines:Mapped[list['TransferOrderLine']]=relationship(back_populates='transfer_order',cascade='all, delete-orphan')

class TransferOrderLine(Base):
    __tablename__='transfer_order_lines'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    transfer_order_id:Mapped[str]=mapped_column(String(36),ForeignKey('transfer_orders.id'),index=True)
    item_id:Mapped[str]=mapped_column(String(36),ForeignKey('items.id'))
    quantity:Mapped[Decimal]=mapped_column(Numeric(18,4))
    transfer_order:Mapped[TransferOrder]=relationship(back_populates='lines')

class CycleCountSchedule(Base):
    __tablename__='cycle_count_schedules'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    item_id:Mapped[str]=mapped_column(String(36),ForeignKey('items.id'),index=True)
    location_id:Mapped[str]=mapped_column(String(36),ForeignKey('locations.id'),index=True)
    frequency_days:Mapped[int]=mapped_column(default=30)
    next_count_date:Mapped[date]=mapped_column(Date,index=True)
    last_count_date:Mapped[date|None]=mapped_column(Date,nullable=True)
    is_active:Mapped[bool]=mapped_column(Boolean,default=True)
