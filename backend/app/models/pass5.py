import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

def uid(): return str(uuid.uuid4())
def utcnow(): return datetime.now(timezone.utc)

class MaintenancePlan(Base):
    __tablename__='maintenance_plans'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    code:Mapped[str]=mapped_column(String(60),unique=True,index=True)
    name:Mapped[str]=mapped_column(String(160))
    asset_id:Mapped[str]=mapped_column(String(36),ForeignKey('fixed_assets.id'),index=True)
    interval_days:Mapped[int]=mapped_column(default=30)
    checklist:Mapped[str|None]=mapped_column(Text,nullable=True)
    assigned_user_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('users.id'),nullable=True)
    next_due_date:Mapped[date]=mapped_column(Date,index=True)
    is_active:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class WorkOrder(Base):
    __tablename__='maintenance_work_orders'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    work_order_number:Mapped[str]=mapped_column(String(60),unique=True,index=True)
    asset_id:Mapped[str]=mapped_column(String(36),ForeignKey('fixed_assets.id'),index=True)
    plan_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('maintenance_plans.id'),nullable=True,index=True)
    title:Mapped[str]=mapped_column(String(180))
    description:Mapped[str|None]=mapped_column(Text,nullable=True)
    priority:Mapped[str]=mapped_column(String(20),default='normal',index=True)
    status:Mapped[str]=mapped_column(String(30),default='open',index=True)
    assigned_user_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('users.id'),nullable=True)
    contractor:Mapped[str|None]=mapped_column(String(180),nullable=True)
    scheduled_date:Mapped[date|None]=mapped_column(Date,nullable=True)
    started_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    labor_cost:Mapped[Decimal]=mapped_column(Numeric(18,2),default=0)
    external_cost:Mapped[Decimal]=mapped_column(Numeric(18,2),default=0)
    downtime_hours:Mapped[Decimal]=mapped_column(Numeric(12,2),default=0)
    completion_notes:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_by_user_id:Mapped[str]=mapped_column(String(36),ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    parts:Mapped[list['WorkOrderPart']]=relationship(back_populates='work_order',cascade='all, delete-orphan')

class WorkOrderPart(Base):
    __tablename__='maintenance_work_order_parts'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    work_order_id:Mapped[str]=mapped_column(String(36),ForeignKey('maintenance_work_orders.id',ondelete='CASCADE'),index=True)
    item_id:Mapped[str]=mapped_column(String(36),ForeignKey('items.id'))
    quantity:Mapped[Decimal]=mapped_column(Numeric(18,6))
    unit_cost:Mapped[Decimal]=mapped_column(Numeric(18,4),default=0)
    work_order:Mapped[WorkOrder]=relationship(back_populates='parts')

class PurchaseLineTreatment(Base):
    __tablename__='purchase_line_treatments'
    __table_args__=(UniqueConstraint('source_type','source_line_id',name='uq_purchase_line_treatment_source'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    source_type:Mapped[str]=mapped_column(String(30),index=True)
    source_line_id:Mapped[str]=mapped_column(String(36),index=True)
    treatment:Mapped[str]=mapped_column(String(30),index=True)
    workspace_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('operational_dimensions.id'),nullable=True)
    department_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('operational_dimensions.id'),nullable=True)
    cost_center_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('operational_dimensions.id'),nullable=True)
    intended_location_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('locations.id'),nullable=True)
    asset_class_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('operational_dimensions.id'),nullable=True)
    accounting_mapping_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('accounting_mappings.id'),nullable=True)
    project_reference:Mapped[str|None]=mapped_column(String(120),nullable=True)
    notes:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class AccountingMapping(Base):
    __tablename__='accounting_mappings'
    __table_args__=(UniqueConstraint('event_key','dimension_id',name='uq_accounting_mapping_event_dimension'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    event_key:Mapped[str]=mapped_column(String(100),index=True)
    dimension_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('operational_dimensions.id'),nullable=True,index=True)
    debit_account:Mapped[str]=mapped_column(String(80))
    credit_account:Mapped[str]=mapped_column(String(80))
    description:Mapped[str|None]=mapped_column(String(240),nullable=True)
    is_active:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
