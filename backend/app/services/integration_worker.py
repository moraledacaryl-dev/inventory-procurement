import json, os, socket
from datetime import datetime, timedelta, timezone
import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.models.operations import IntegrationEvent
from app.services.controls import add_audit, add_notification

def utcnow(): return datetime.now(timezone.utc)
def endpoint_map()->dict[str,str]:
    raw=os.getenv('INTEGRATION_ENDPOINTS_JSON','{}')
    try: return json.loads(raw)
    except json.JSONDecodeError: return {}

def claim_events(db:Session,worker_id:str,limit:int=25)->list[IntegrationEvent]:
    now=utcnow(); stale=now-timedelta(minutes=10)
    stmt=(select(IntegrationEvent)
        .where(IntegrationEvent.direction=='outbound',IntegrationEvent.available_at<=now,IntegrationEvent.status.in_(['pending','failed']),or_(IntegrationEvent.locked_at==None,IntegrationEvent.locked_at<stale),IntegrationEvent.attempts<IntegrationEvent.max_attempts)
        .order_by(IntegrationEvent.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True))
    rows=db.scalars(stmt).all()
    for row in rows: row.status='processing'; row.locked_at=now; row.locked_by=worker_id
    db.commit()
    return rows

def process_event(db:Session,event_id:str,worker_id:str,endpoints:dict[str,str]|None=None,client:httpx.Client|None=None)->IntegrationEvent:
    endpoints=endpoints or endpoint_map(); event=db.get(IntegrationEvent,event_id)
    if not event or event.locked_by!=worker_id or event.status!='processing': raise ValueError('Event is not claimed by this worker')
    event.attempts+=1; url=endpoints.get(event.destination_system)
    try:
        if not url: raise RuntimeError(f'No endpoint configured for {event.destination_system}')
        owns_client=client is None; client=client or httpx.Client(timeout=15)
        try:
            response=client.post(url,json={'id':event.id,'event_type':event.event_type,'aggregate_type':event.aggregate_type,'aggregate_id':event.aggregate_id,'payload':event.payload},headers={'Idempotency-Key':event.idempotency_key})
            response.raise_for_status()
        finally:
            if owns_client: client.close()
        event.status='completed'; event.processed_at=utcnow(); event.last_error=None; event.locked_at=None; event.locked_by=None
        add_audit(db,actor_user_id=None,action='integration.delivered',entity_type='integration_event',entity_id=event.id,details={'destination':event.destination_system,'attempts':event.attempts})
    except Exception as exc:
        event.last_error=str(exc)[:2000]; event.locked_at=None; event.locked_by=None
        if event.attempts>=event.max_attempts:
            event.status='dead_letter'
            add_notification(db,title='Integration event requires attention',message=f'{event.event_type} for {event.aggregate_id} exhausted all retries.',severity='error')
            add_audit(db,actor_user_id=None,action='integration.dead_lettered',entity_type='integration_event',entity_id=event.id,details={'error':event.last_error,'attempts':event.attempts})
        else:
            event.status='failed'; delay=min(3600,30*(2**(event.attempts-1))); event.available_at=utcnow()+timedelta(seconds=delay)
            add_audit(db,actor_user_id=None,action='integration.retry_scheduled',entity_type='integration_event',entity_id=event.id,details={'error':event.last_error,'attempts':event.attempts,'delay_seconds':delay})
    db.commit(); db.refresh(event); return event

def run_once(db:Session,limit:int=25)->dict:
    worker_id=f'{socket.gethostname()}:{os.getpid()}'; rows=claim_events(db,worker_id,limit); completed=failed=dead=0
    for row in rows:
        result=process_event(db,row.id,worker_id)
        completed+=result.status=='completed'; failed+=result.status=='failed'; dead+=result.status=='dead_letter'
    return {'claimed':len(rows),'completed':completed,'failed':failed,'dead_letter':dead}
