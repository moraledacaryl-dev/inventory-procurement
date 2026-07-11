from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from app.models.operations import DocumentSequence, IntegrationEvent, Notification

def utcnow(): return datetime.now(timezone.utc)

def next_document_number(db:Session,prefix:str,width:int=6)->str:
    prefix=prefix.upper().strip()
    row=db.scalar(select(DocumentSequence).where(DocumentSequence.prefix==prefix).with_for_update())
    if row is None:
        row=DocumentSequence(prefix=prefix,next_value=2); db.add(row); value=1
    else:
        value=row.next_value; row.next_value=value+1
    db.flush()
    return f'{prefix}-{value:0{width}d}'

def add_audit(db:Session,*,actor_user_id:str|None,action:str,entity_type:str,entity_id:str|None=None,details:dict|None=None,request_id:str|None=None,ip_address:str|None=None):
    db.add(AuditLog(actor_user_id=actor_user_id,action=action,entity_type=entity_type,entity_id=entity_id,details=details or {},request_id=request_id,ip_address=ip_address))

def add_notification(db:Session,*,title:str,message:str|None=None,body:str|None=None,severity:str='info',user_id:str|None=None):
    text=message if message is not None else body
    if text is None: raise ValueError('Notification message is required')
    row=Notification(title=title,message=text,severity=severity,user_id=user_id); db.add(row); return row

def enqueue_event(db:Session,*,destination_system:str,event_type:str,aggregate_type:str,aggregate_id:str,payload:dict,idempotency_key:str,source_system:str='inventory',direction:str='outbound'):
    existing=db.scalar(select(IntegrationEvent).where(IntegrationEvent.idempotency_key==idempotency_key))
    if existing: return existing
    row=IntegrationEvent(direction=direction,source_system=source_system,destination_system=destination_system,event_type=event_type,aggregate_type=aggregate_type,aggregate_id=aggregate_id,idempotency_key=idempotency_key,payload=payload)
    db.add(row); db.flush(); return row
