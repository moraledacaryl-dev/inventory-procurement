import csv, io, json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.api.deps import require_permission
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.inventory import Item, Category, UnitOfMeasure, StockBalance
from app.models.operations import Notification, IntegrationEvent, BackupRecord
from app.models.user import User
from app.schemas.operations import *

router=APIRouter(tags=['operations'])

def page(stmt,count_stmt,db,limit,offset):
    total=db.scalar(count_stmt) or 0
    rows=db.scalars(stmt.limit(limit).offset(offset)).all()
    return rows,{'total':total,'limit':limit,'offset':offset}

@router.get('/audit-logs',response_model=list[AuditOut])
def audit_logs(action:str|None=None,entity_type:str|None=None,limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0),db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))):
    stmt=select(AuditLog).order_by(AuditLog.created_at.desc())
    if action: stmt=stmt.where(AuditLog.action==action)
    if entity_type: stmt=stmt.where(AuditLog.entity_type==entity_type)
    return db.scalars(stmt.limit(limit).offset(offset)).all()

@router.get('/notifications',response_model=list[NotificationOut])
def notifications(unread_only:bool=False,db:Session=Depends(get_db),user:User=Depends(require_permission('reports.read'))):
    stmt=select(Notification).where((Notification.user_id==user.id)|(Notification.user_id==None)).order_by(Notification.created_at.desc())
    if unread_only: stmt=stmt.where(Notification.is_read==False)
    return db.scalars(stmt.limit(100)).all()
@router.post('/notifications/{notification_id}/read',response_model=NotificationOut)
def mark_read(notification_id:str,db:Session=Depends(get_db),user:User=Depends(require_permission('reports.read'))):
    row=db.get(Notification,notification_id)
    if not row or row.user_id not in {None,user.id}: raise HTTPException(404,'Notification not found')
    row.is_read=True; db.commit(); db.refresh(row); return row

@router.get('/integration-events',response_model=list[IntegrationEventOut])
def integration_events(status:str|None=None,limit:int=Query(100,ge=1,le=500),db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))):
    stmt=select(IntegrationEvent).order_by(IntegrationEvent.created_at.desc())
    if status: stmt=stmt.where(IntegrationEvent.status==status)
    return db.scalars(stmt.limit(limit)).all()
@router.post('/integration-events',response_model=IntegrationEventOut,status_code=201)
def create_event(p:IntegrationEventCreate,db:Session=Depends(get_db),_:User=Depends(require_permission('procurement.*'))):
    existing=db.scalar(select(IntegrationEvent).where(IntegrationEvent.idempotency_key==p.idempotency_key))
    if existing: return existing
    row=IntegrationEvent(**p.model_dump()); db.add(row); db.commit(); db.refresh(row); return row
@router.post('/integration-events/{event_id}/retry',response_model=IntegrationEventOut)
def retry_event(event_id:str,db:Session=Depends(get_db),_:User=Depends(require_permission('procurement.*'))):
    row=db.get(IntegrationEvent,event_id)
    if not row: raise HTTPException(404,'Event not found')
    row.status='pending'; row.last_error=None; db.commit(); db.refresh(row); return row

@router.get('/exports/items.csv')
def export_items(db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))):
    output=io.StringIO(); writer=csv.writer(output); writer.writerow(['sku','name','category_id','base_unit_id','minimum_stock','standard_cost','is_active'])
    for x in db.scalars(select(Item).order_by(Item.sku)).all(): writer.writerow([x.sku,x.name,x.category_id,x.base_unit_id,x.minimum_stock,x.standard_cost,x.is_active])
    return StreamingResponse(iter([output.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=items.csv'})
@router.get('/exports/balances.csv')
def export_balances(db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))):
    output=io.StringIO(); writer=csv.writer(output); writer.writerow(['item_id','location_id','quantity','average_cost'])
    for x in db.scalars(select(StockBalance)).all(): writer.writerow([x.item_id,x.location_id,x.quantity,x.average_cost])
    return StreamingResponse(iter([output.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=stock-balances.csv'})
@router.post('/imports/items.csv')
async def import_items(file:UploadFile=File(...),db:Session=Depends(get_db),_:User=Depends(require_permission('items.*'))):
    content=(await file.read()).decode('utf-8-sig'); reader=csv.DictReader(io.StringIO(content)); created=0; skipped=0; errors=[]
    for index,row in enumerate(reader,2):
        try:
            if db.scalar(select(Item).where(Item.sku==row['sku'].upper().strip())): skipped+=1; continue
            if not db.get(Category,row['category_id']) or not db.get(UnitOfMeasure,row['base_unit_id']): raise ValueError('Unknown category or unit')
            db.add(Item(sku=row['sku'].upper().strip(),name=row['name'].strip(),category_id=row['category_id'],base_unit_id=row['base_unit_id'],minimum_stock=row.get('minimum_stock') or 0,standard_cost=row.get('standard_cost') or 0)); created+=1
        except Exception as exc: errors.append({'line':index,'error':str(exc)})
    if errors: db.rollback(); raise HTTPException(422,{'errors':errors})
    db.commit(); return {'created':created,'skipped':skipped}

@router.get('/backups',response_model=list[BackupOut])
def backups(db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))): return db.scalars(select(BackupRecord).order_by(BackupRecord.created_at.desc())).all()
