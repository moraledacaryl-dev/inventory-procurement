import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


def uid(): return str(uuid.uuid4())
def utcnow(): return datetime.now(timezone.utc)


class OperationalAccessScope(Base):
    __tablename__='operational_access_scopes'
    __table_args__=(UniqueConstraint('user_id','workspace_id','department_id','location_id','record_class_id',name='uq_operational_access_scope'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    user_id:Mapped[str]=mapped_column(String(36),ForeignKey('users.id'),index=True)
    workspace_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('operational_dimensions.id'),nullable=True,index=True)
    department_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('operational_dimensions.id'),nullable=True,index=True)
    location_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('locations.id'),nullable=True,index=True)
    record_class_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('operational_dimensions.id'),nullable=True,index=True)
    approval_limit:Mapped[Decimal]=mapped_column(Numeric(18,2),default=0)
    is_active:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


class SavedView(Base):
    __tablename__='saved_views'
    __table_args__=(UniqueConstraint('user_id','module_key','name',name='uq_saved_view_user_module_name'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    user_id:Mapped[str]=mapped_column(String(36),ForeignKey('users.id'),index=True)
    module_key:Mapped[str]=mapped_column(String(80),index=True)
    name:Mapped[str]=mapped_column(String(120))
    filters:Mapped[dict]=mapped_column(JSON,default=dict)
    columns:Mapped[list]=mapped_column(JSON,default=list)
    is_default:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
