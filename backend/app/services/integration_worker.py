import json, os, socket
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.models.inventory import Item, Location, StockBalance
from app.models.operations import IntegrationEvent
from app.services.controls import add_audit, add_notification, enqueue_event

ACCOUNTING_ENDPOINT='/api/integration-review/service-intake'
ACCOUNTING_DELIVERED_STATUSES={'ready_for_review','accepted','rejected'}
OPERATIONS_SOURCE_APP='inventory_procurement'
OPERATIONS_ENDPOINT=f'/api/integrations/v2/events/{OPERATIONS_SOURCE_APP}'
OPERATIONS_EVENT_TYPES={
    'inventory.exception.created','stock.low.alert','stockout.alert','count.variance.pending_review',
    'transfer.pending_review','requisition.pending_review','purchase.need.created',
    'receiving.exception.created','expiry.alert','wastage.alert',
}

def utcnow(): return datetime.now(timezone.utc)
def endpoint_map()->dict[str,str]:
    raw=os.getenv('INTEGRATION_ENDPOINTS_JSON','{}')
    try:return json.loads(raw)
    except json.JSONDecodeError:return {}

def _money(value)->Decimal:
    try:return Decimal(str(value or 0))
    except (InvalidOperation,ValueError,TypeError):return Decimal('0')

def _join_url(base:str,path:str)->str:return f"{base.rstrip('/')}/{path.lstrip('/')}"

def _operations_url(base:str)->str:
    clean=base.rstrip('/')
    if clean.endswith(OPERATIONS_ENDPOINT):return clean
    if clean.endswith('/api'):return _join_url(clean,OPERATIONS_ENDPOINT.removeprefix('/api'))
    return _join_url(clean,OPERATIONS_ENDPOINT)

def _validate_accounting_response(response:httpx.Response)->dict:
    try:payload=response.json()
    except (ValueError,TypeError) as exc:raise RuntimeError('Accounting intake returned invalid JSON') from exc
    if not isinstance(payload,dict):raise RuntimeError('Accounting intake returned an invalid response envelope')
    status=str(payload.get('status') or '').strip().lower()
    if status=='validation_failed':
        validation=payload.get('validation') if isinstance(payload.get('validation'),dict) else {}
        errors=validation.get('errors') if isinstance(validation.get('errors'),list) else []
        detail='; '.join(str(error) for error in errors if error) or 'Accounting rejected the integration payload'
        raise RuntimeError(f'Accounting intake validation_failed: {detail}')
    if status not in ACCOUNTING_DELIVERED_STATUSES:
        raise RuntimeError(f'Accounting intake returned unexpected status: {status or "missing"}')
    return payload

def accounting_envelope(event:IntegrationEvent)->dict:
    payload=event.payload if isinstance(event.payload,dict) else {}
    effect='reference_only';amount=Decimal('0');links={'target_type':event.aggregate_type,'target_id':str(event.aggregate_id)}
    if event.event_type=='procurement.goods_received':
        amount=sum((_money(line.get('accepted_quantity'))*_money(line.get('unit_cost')) for line in payload.get('lines',[])),Decimal('0'));effect='payable';links={'supplier_id':payload.get('supplier_id'),'supplier_name':str(payload.get('supplier_id') or 'Supplier'),'purchase_order_id':payload.get('purchase_order_id'),'invoice_number':payload.get('goods_receipt_number'),'category':'Inventory purchases'}
    elif event.event_type=='procurement.purchase_order.approved':links={'target_type':'purchase_order','target_id':str(payload.get('purchase_order_id') or event.aggregate_id),'purchase_order_id':payload.get('purchase_order_id'),'supplier_id':payload.get('supplier_id'),'commitment_total':payload.get('total')}
    elif event.event_type=='procurement.purchase_return.posted':links={'target_type':'purchase_return','target_id':str(payload.get('purchase_return_id') or event.aggregate_id),'purchase_return_id':payload.get('purchase_return_id'),'purchase_order_id':payload.get('purchase_order_id'),'return_number':payload.get('return_number')}
    elif event.event_type=='inventory.production.completed':links={'target_type':'production_batch','target_id':str(payload.get('batch_id') or event.aggregate_id),'batch_id':payload.get('batch_id'),'batch_number':payload.get('batch_number'),'stock_value':payload.get('total_cost'),'category':'Inventory production'}
    elif event.event_type in {'inventory.pos_sale_consumed','inventory.pos_sale_reversed'}:links={'target_type':'pos_sale','target_id':str(payload.get('sale_id') or event.aggregate_id),'sale_id':payload.get('sale_id'),'stock_document_id':payload.get('stock_document_id'),'category':'Cost of goods sold','reversal':event.event_type.endswith('reversed')}
    return {'source_app':'inventory','source_event_id':event.id,'source_entity_type':event.aggregate_type,'source_entity_id':event.aggregate_id,'source_revision':max(1,int(event.attempts or 0)+1),'financial_effect':effect,'amount':float(amount.quantize(Decimal('0.01'))),'currency':str(payload.get('currency') or 'PHP').upper(),'proposed_account_id':payload.get('accounting_account_id'),'proposed_journal':payload.get('proposed_journal'),'proposed_links':links,'payload':{'event_type':event.event_type,'aggregate_type':event.aggregate_type,'aggregate_id':event.aggregate_id,'data':payload},'idempotency_key':event.idempotency_key,'correlation_id':str(payload.get('correlation_id') or event.aggregate_id)}

def operations_envelope(event:IntegrationEvent)->dict:
    if event.event_type not in OPERATIONS_EVENT_TYPES:raise ValueError(f'Operations v2 does not accept {event.event_type}')
    payload=event.payload if isinstance(event.payload,dict) else {};priority=str(payload.get('priority') or 'Normal').title()
    if priority not in {'Low','Normal','High','Critical'}:priority='Normal'
    title=str(payload.get('title') or payload.get('name') or event.event_type.replace('.', ' ').replace('_',' ').title());summary=str(payload.get('summary') or payload.get('description') or payload.get('reason') or '')
    occurred_at=event.created_at or utcnow();body={'event_id':event.idempotency_key or event.id,'event_type':event.event_type,'schema_version':1,'occurred_at':occurred_at.isoformat(),'priority':priority,'title':title,'summary':summary,'subject':{'type':event.aggregate_type,'id':str(event.aggregate_id)},'payload':payload,'metadata':{'source_event_id':event.id,'source_system':event.source_system}}
    department_id=payload.get('department_id')
    if isinstance(department_id,int):body['department_id']=department_id
    correlation_id=payload.get('correlation_id')
    if correlation_id:body['correlation_id']=str(correlation_id)
    return body

def enqueue_operations_stock_alerts(db:Session,endpoints:dict[str,str]|None=None)->int:
    """Queue one Operations alert per stock-balance revision while it is low/out.

    No events are created until the Operations endpoint and dedicated key are configured,
    so rollout can be staged without filling the outbox with undeliverable alerts.
    """
    endpoints=endpoints or endpoint_map()
    if not endpoints.get('operations') or not os.getenv('OPERATIONS_INTEGRATION_KEY','').strip():return 0
    rows=db.execute(select(StockBalance,Item,Location).join(Item,Item.id==StockBalance.item_id).join(Location,Location.id==StockBalance.location_id).where(Item.is_active==True,Item.track_stock==True,Item.minimum_stock>0,StockBalance.quantity<Item.minimum_stock)).all()
    queued=0
    for balance,item,location in rows:
        event_type='stockout.alert' if Decimal(str(balance.quantity or 0))<=0 else 'stock.low.alert'
        stamp=(balance.updated_at or utcnow()).astimezone(timezone.utc).isoformat()
        key=f'ops-stock:{balance.id}:{event_type}:{stamp}'
        existing=db.scalar(select(IntegrationEvent.id).where(IntegrationEvent.idempotency_key==key))
        if existing:continue
        quantity=str(balance.quantity or 0);minimum=str(item.minimum_stock or 0)
        enqueue_event(db,destination_system='operations',event_type=event_type,aggregate_type='stock_balance',aggregate_id=balance.id,idempotency_key=key,payload={'title':f'{"Stockout" if event_type=="stockout.alert" else "Low stock"}: {item.name}','summary':f'{quantity} {item.sku} at {location.name}; minimum stock is {minimum}.','priority':'Critical' if event_type=='stockout.alert' else 'High','item_id':item.id,'sku':item.sku,'item_name':item.name,'location_id':location.id,'location_name':location.name,'quantity':quantity,'minimum_stock':minimum,'balance_updated_at':stamp})
        queued+=1
    if queued:db.commit()
    return queued

def claim_events(db:Session,worker_id:str,limit:int=25)->list[IntegrationEvent]:
    now=utcnow();stale=now-timedelta(minutes=10);stmt=(select(IntegrationEvent).where(IntegrationEvent.direction=='outbound',IntegrationEvent.available_at<=now,IntegrationEvent.status.in_(['pending','failed']),or_(IntegrationEvent.locked_at==None,IntegrationEvent.locked_at<stale),IntegrationEvent.attempts<IntegrationEvent.max_attempts).order_by(IntegrationEvent.created_at).limit(limit).with_for_update(skip_locked=True));rows=db.scalars(stmt).all()
    for row in rows:row.status='processing';row.locked_at=now;row.locked_by=worker_id
    db.commit();return rows

def process_event(db:Session,event_id:str,worker_id:str,endpoints:dict[str,str]|None=None,client:httpx.Client|None=None)->IntegrationEvent:
    endpoints=endpoints or endpoint_map();event=db.get(IntegrationEvent,event_id)
    if not event or event.locked_by!=worker_id or event.status!='processing':raise ValueError('Event is not claimed by this worker')
    event.attempts+=1;base=endpoints.get(event.destination_system)
    try:
        if not base:raise RuntimeError(f'No endpoint configured for {event.destination_system}')
        body={'id':event.id,'event_type':event.event_type,'aggregate_type':event.aggregate_type,'aggregate_id':event.aggregate_id,'payload':event.payload};headers={'Idempotency-Key':event.idempotency_key};url=base
        if event.destination_system=='accounting':
            url=_join_url(base,ACCOUNTING_ENDPOINT) if not base.rstrip('/').endswith(ACCOUNTING_ENDPOINT) else base;body=accounting_envelope(event);token=os.getenv('INTEGRATION_API_KEY','').strip()
            if token:headers['X-Integration-Api-Key']=token
        elif event.destination_system=='operations':
            url=_operations_url(base);body=operations_envelope(event);token=os.getenv('OPERATIONS_INTEGRATION_KEY','').strip()
            if not token:raise RuntimeError('OPERATIONS_INTEGRATION_KEY is not configured')
            headers['X-Integration-Api-Key']=token
        owns_client=client is None;client=client or httpx.Client(timeout=15)
        try:
            response=client.post(url,json=body,headers=headers);response.raise_for_status()
            if event.destination_system=='accounting':_validate_accounting_response(response)
        finally:
            if owns_client:client.close()
        event.status='completed';event.processed_at=utcnow();event.last_error=None;event.locked_at=None;event.locked_by=None;add_audit(db,actor_user_id=None,action='integration.delivered',entity_type='integration_event',entity_id=event.id,details={'destination':event.destination_system,'attempts':event.attempts})
    except Exception as exc:
        event.last_error=str(exc)[:2000];event.locked_at=None;event.locked_by=None
        if event.attempts>=event.max_attempts:event.status='dead_letter';add_notification(db,title='Integration event requires attention',message=f'{event.event_type} for {event.aggregate_id} exhausted all retries.',severity='error');add_audit(db,actor_user_id=None,action='integration.dead_lettered',entity_type='integration_event',entity_id=event.id,details={'error':event.last_error,'attempts':event.attempts})
        else:event.status='failed';delay=min(3600,30*(2**(event.attempts-1)));event.available_at=utcnow()+timedelta(seconds=delay);add_audit(db,actor_user_id=None,action='integration.retry_scheduled',entity_type='integration_event',entity_id=event.id,details={'error':event.last_error,'attempts':event.attempts,'delay_seconds':delay})
    db.commit();db.refresh(event);return event

def run_once(db:Session,limit:int=25)->dict:
    endpoints=endpoint_map();queued=enqueue_operations_stock_alerts(db,endpoints);worker_id=f'{socket.gethostname()}:{os.getpid()}';rows=claim_events(db,worker_id,limit);completed=failed=dead=0
    for row in rows:
        result=process_event(db,row.id,worker_id,endpoints=endpoints);completed+=result.status=='completed';failed+=result.status=='failed';dead+=result.status=='dead_letter'
    return {'queued_operations_alerts':queued,'claimed':len(rows),'completed':completed,'failed':failed,'dead_letter':dead}
