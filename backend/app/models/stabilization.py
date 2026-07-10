import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

def uid(): return str(uuid.uuid4())
def utcnow(): return datetime.now(timezone.utc)

class StaffFeedback(Base):
    __tablename__='staff_feedback'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    category:Mapped[str]=mapped_column(String(40),index=True)
    severity:Mapped[str]=mapped_column(String(20),default='normal',index=True)
    page:Mapped[str|None]=mapped_column(String(180),nullable=True)
    message:Mapped[str]=mapped_column(Text)
    context:Mapped[dict]=mapped_column(JSON,default=dict)
    status:Mapped[str]=mapped_column(String(30),default='open',index=True)
    submitted_by_user_id:Mapped[str]=mapped_column(String(36),ForeignKey('users.id'))
    assigned_to_user_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('users.id'),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,index=True)
    resolved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class OperationalIncident(Base):
    __tablename__='operational_incidents'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    incident_number:Mapped[str]=mapped_column(String(60),unique=True,index=True)
    source:Mapped[str]=mapped_column(String(60),index=True)
    severity:Mapped[str]=mapped_column(String(20),index=True)
    title:Mapped[str]=mapped_column(String(180))
    details:Mapped[str]=mapped_column(Text)
    request_id:Mapped[str|None]=mapped_column(String(100),nullable=True,index=True)
    status:Mapped[str]=mapped_column(String(30),default='open',index=True)
    metadata_json:Mapped[dict]=mapped_column(JSON,default=dict)
    created_by_user_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('users.id'),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,index=True)
    acknowledged_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    resolved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
