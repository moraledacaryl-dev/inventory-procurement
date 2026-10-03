import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
def uid(): return str(uuid.uuid4())
def utcnow(): return datetime.now(timezone.utc)
class MenuItem(Base):
    __tablename__="menu_items"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    name:Mapped[str]=mapped_column(String(180),index=True)
    display_name:Mapped[str]=mapped_column(String(180))
    category:Mapped[str]=mapped_column(String(100),index=True)
    description:Mapped[str|None]=mapped_column(Text,nullable=True)
    prep_station:Mapped[str]=mapped_column(String(40),default="bar")
    sort_order:Mapped[int]=mapped_column(Integer,default=0)
    is_active:Mapped[bool]=mapped_column(Boolean,default=True)
    pos_visible:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,onupdate=utcnow)
    variants:Mapped[list["MenuVariant"]]=relationship(back_populates="menu_item",cascade="all, delete-orphan",order_by="MenuVariant.sort_order")
class MenuVariant(Base):
    __tablename__="menu_variants"
    __table_args__=(UniqueConstraint("sku",name="uq_menu_variant_sku"),UniqueConstraint("barcode",name="uq_menu_variant_barcode"))
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    menu_item_id:Mapped[str]=mapped_column(String(36),ForeignKey("menu_items.id",ondelete="CASCADE"),index=True)
    name:Mapped[str]=mapped_column(String(120),default="Regular")
    sku:Mapped[str]=mapped_column(String(80),index=True)
    barcode:Mapped[str]=mapped_column(String(100),index=True)
    price:Mapped[Decimal]=mapped_column(Numeric(12,2))
    with_drink_price:Mapped[Decimal|None]=mapped_column(Numeric(12,2),nullable=True)
    recipe_id:Mapped[str|None]=mapped_column(String(36),ForeignKey("recipes.id"),nullable=True,index=True)
    inventory_item_id:Mapped[str|None]=mapped_column(String(36),ForeignKey("items.id"),nullable=True,index=True)
    sort_order:Mapped[int]=mapped_column(Integer,default=0)
    is_active:Mapped[bool]=mapped_column(Boolean,default=True)
    menu_item:Mapped[MenuItem]=relationship(back_populates="variants")
