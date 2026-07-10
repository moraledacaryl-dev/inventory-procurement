import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

def uid(): return str(uuid.uuid4())
def utcnow(): return datetime.now(timezone.utc)

class DataImportJob(Base):
    __tablename__='data_import_jobs'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    import_type:Mapped[str]=mapped_column(String(60),index=True)
    filename:Mapped[str]=mapped_column(String(240))
    status:Mapped[str]=mapped_column(String(30),default='validated',index=True)
    summary:Mapped[dict]=mapped_column(JSON,default=dict)
    errors:Mapped[list]=mapped_column(JSON,default=list)
    created_by_user_id:Mapped[str]=mapped_column(String(36),ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,index=True)
    applied_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class AcceptanceRun(Base):
    __tablename__='acceptance_runs'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    run_number:Mapped[str]=mapped_column(String(60),unique=True,index=True)
    environment:Mapped[str]=mapped_column(String(60),default='production-candidate')
    status:Mapped[str]=mapped_column(String(30),default='running',index=True)
    results:Mapped[dict]=mapped_column(JSON,default=dict)
    notes:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_by_user_id:Mapped[str]=mapped_column(String(36),ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,index=True)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
