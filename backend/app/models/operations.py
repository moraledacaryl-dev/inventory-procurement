import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

def uid(): return str(uuid.uuid4())
def utcnow(): return datetime.now(timezone.utc)

class Notification(Base):
    __tablename__='notifications'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    user_id: Mapped[str|None]=mapped_column(String(36),ForeignKey('users.id'),nullable=True,index=True)
    title: Mapped[str]=mapped_column(String(180))
    message: Mapped[str]=mapped_column(Text)
    severity: Mapped[str]=mapped_column(String(20),default='info')
    is_read: Mapped[bool]=mapped_column(Boolean,default=False,index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,index=True)

class IntegrationEvent(Base):
    __tablename__='integration_events'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    direction: Mapped[str]=mapped_column(String(10))
    source_system: Mapped[str]=mapped_column(String(60))
    destination_system: Mapped[str]=mapped_column(String(60))
    event_type: Mapped[str]=mapped_column(String(120),index=True)
    aggregate_type: Mapped[str]=mapped_column(String(80))
    aggregate_id: Mapped[str]=mapped_column(String(100),index=True)
    idempotency_key: Mapped[str]=mapped_column(String(120),unique=True,index=True)
    payload: Mapped[dict]=mapped_column(JSON)
    status: Mapped[str]=mapped_column(String(30),default='pending',index=True)
    attempts: Mapped[int]=mapped_column(default=0)
    last_error: Mapped[str|None]=mapped_column(Text,nullable=True)
    available_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    processed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,index=True)

class BackupRecord(Base):
    __tablename__='backup_records'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    filename: Mapped[str]=mapped_column(String(240),unique=True)
    status: Mapped[str]=mapped_column(String(30),default='completed')
    size_bytes: Mapped[int]=mapped_column(default=0)
    checksum_sha256: Mapped[str|None]=mapped_column(String(64),nullable=True)
    created_by_user_id: Mapped[str|None]=mapped_column(String(36),ForeignKey('users.id'),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,index=True)
