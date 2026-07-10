import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

def uid(): return str(uuid.uuid4())
def utcnow(): return datetime.now(timezone.utc)

class Recipe(Base):
    __tablename__='recipes'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    code:Mapped[str]=mapped_column(String(60),unique=True,index=True)
    name:Mapped[str]=mapped_column(String(180),index=True)
    output_item_id:Mapped[str]=mapped_column(String(36),ForeignKey('items.id'),index=True)
    yield_quantity:Mapped[Decimal]=mapped_column(Numeric(18,4),default=1)
    version:Mapped[int]=mapped_column(default=1)
    status:Mapped[str]=mapped_column(String(30),default='draft',index=True)
    notes:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_by_user_id:Mapped[str]=mapped_column(String(36),ForeignKey('users.id'))
    approved_by_user_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('users.id'),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    approved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    lines:Mapped[list['RecipeLine']]=relationship(back_populates='recipe',cascade='all, delete-orphan')

class RecipeLine(Base):
    __tablename__='recipe_lines'
    __table_args__=(UniqueConstraint('recipe_id','ingredient_item_id',name='uq_recipe_ingredient'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    recipe_id:Mapped[str]=mapped_column(String(36),ForeignKey('recipes.id'),index=True)
    ingredient_item_id:Mapped[str]=mapped_column(String(36),ForeignKey('items.id'),index=True)
    quantity:Mapped[Decimal]=mapped_column(Numeric(18,6))
    waste_factor:Mapped[Decimal]=mapped_column(Numeric(8,4),default=0)
    optional:Mapped[bool]=mapped_column(Boolean,default=False)
    recipe:Mapped[Recipe]=relationship(back_populates='lines')

class ProductionBatch(Base):
    __tablename__='production_batches'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    batch_number:Mapped[str]=mapped_column(String(60),unique=True,index=True)
    recipe_id:Mapped[str]=mapped_column(String(36),ForeignKey('recipes.id'),index=True)
    location_id:Mapped[str]=mapped_column(String(36),ForeignKey('locations.id'))
    planned_quantity:Mapped[Decimal]=mapped_column(Numeric(18,4))
    actual_quantity:Mapped[Decimal|None]=mapped_column(Numeric(18,4),nullable=True)
    status:Mapped[str]=mapped_column(String(30),default='planned',index=True)
    notes:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_by_user_id:Mapped[str]=mapped_column(String(36),ForeignKey('users.id'))
    completed_by_user_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('users.id'),nullable=True)
    stock_document_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('stock_documents.id'),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class PosProductMapping(Base):
    __tablename__='pos_product_mappings'
    __table_args__=(UniqueConstraint('pos_system','external_product_id',name='uq_pos_product_mapping'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    pos_system:Mapped[str]=mapped_column(String(60),default='hidden-oasis-pos')
    external_product_id:Mapped[str]=mapped_column(String(120),index=True)
    recipe_id:Mapped[str]=mapped_column(String(36),ForeignKey('recipes.id'),index=True)
    location_id:Mapped[str]=mapped_column(String(36),ForeignKey('locations.id'))
    is_active:Mapped[bool]=mapped_column(Boolean,default=True)

class PosSaleEvent(Base):
    __tablename__='pos_sale_events'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    external_event_id:Mapped[str]=mapped_column(String(140),unique=True,index=True)
    event_type:Mapped[str]=mapped_column(String(30),index=True)
    external_sale_id:Mapped[str]=mapped_column(String(120),index=True)
    pos_system:Mapped[str]=mapped_column(String(60))
    payload:Mapped[dict]=mapped_column(JSON)
    status:Mapped[str]=mapped_column(String(30),default='processed',index=True)
    stock_document_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('stock_documents.id'),nullable=True)
    reversal_of_event_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('pos_sale_events.id'),nullable=True)
    error:Mapped[str|None]=mapped_column(Text,nullable=True)
    processed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
