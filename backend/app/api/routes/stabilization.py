from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from app.api.deps import require_permission
from app.db.session import get_db
from app.models.user import User
from app.models.inventory import Item, Location, StockBalance, StockMovement
from app.models.operations import IntegrationEvent, BackupRecord
from app.models.readiness import AcceptanceRun
from app.models.stabilization import StaffFeedback, OperationalIncident
from app.schemas.stabilization import *
from app.services.controls import add_audit, next_document_number

router=APIRouter(tags=['stabilization'])
def now(): return datetime.now(timezone.utc)
def fail(code:int,message:str): raise HTTPException(code,message)

@router.post('/feedback',response_model=FeedbackOut,status_code=201)
def submit_feedback(p:FeedbackCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('inventory.read'))):
    row=StaffFeedback(**p.model_dump(),submitted_by_user_id=user.id); db.add(row); db.flush(); add_audit(db,actor_user_id=user.id,action='feedback.submitted',entity_type='staff_feedback',entity_id=row.id,details={'category':row.category,'severity':row.severity}); db.commit(); db.refresh(row); return row

@router.get('/feedback',response_model=list[FeedbackOut])
def list_feedback(status:str|None=None,severity:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))):
    stmt=select(StaffFeedback).order_by(StaffFeedback.created_at.desc())
    if status: stmt=stmt.where(StaffFeedback.status==status)
    if severity: stmt=stmt.where(StaffFeedback.severity==severity)
    return db.scalars(stmt.limit(200)).all()

@router.patch('/feedback/{feedback_id}',response_model=FeedbackOut)
def update_feedback(feedback_id:str,p:FeedbackUpdate,db:Session=Depends(get_db),user:User=Depends(require_permission('reports.read'))):
    row=db.get(StaffFeedback,feedback_id)
    if not row: fail(404,'Feedback not found')
    row.status=p.status; row.assigned_to_user_id=p.assigned_to_user_id; row.resolved_at=now() if p.status in {'resolved','dismissed'} else None
    add_audit(db,actor_user_id=user.id,action='feedback.updated',entity_type='staff_feedback',entity_id=row.id,details={'status':row.status}); db.commit(); db.refresh(row); return row

@router.post('/incidents',response_model=IncidentOut,status_code=201)
def create_incident(p:IncidentCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('reports.read'))):
    row=OperationalIncident(incident_number=next_document_number(db,'INC'),created_by_user_id=user.id,**p.model_dump()); db.add(row); db.flush(); add_audit(db,actor_user_id=user.id,action='incident.created',entity_type='operational_incident',entity_id=row.id,details={'severity':row.severity}); db.commit(); db.refresh(row); return row

@router.get('/incidents',response_model=list[IncidentOut])
def list_incidents(status:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))):
    stmt=select(OperationalIncident).order_by(OperationalIncident.created_at.desc())
    if status: stmt=stmt.where(OperationalIncident.status==status)
    return db.scalars(stmt.limit(200)).all()

@router.patch('/incidents/{incident_id}',response_model=IncidentOut)
def update_incident(incident_id:str,p:IncidentUpdate,db:Session=Depends(get_db),user:User=Depends(require_permission('reports.read'))):
    row=db.get(OperationalIncident,incident_id)
    if not row: fail(404,'Incident not found')
    row.status=p.status
    if p.status=='acknowledged': row.acknowledged_at=now()
    if p.status=='resolved': row.resolved_at=now()
    add_audit(db,actor_user_id=user.id,action='incident.updated',entity_type='operational_incident',entity_id=row.id,details={'status':row.status}); db.commit(); db.refresh(row); return row

@router.get('/rollout/summary',response_model=RolloutSummary)
def rollout_summary(db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))):
    open_feedback=db.scalar(select(func.count()).select_from(StaffFeedback).where(StaffFeedback.status.in_(['open','reviewing']))) or 0
    high=db.scalar(select(func.count()).select_from(StaffFeedback).where(StaffFeedback.status.in_(['open','reviewing']),StaffFeedback.severity.in_(['high','critical']))) or 0
    incidents=db.scalar(select(func.count()).select_from(OperationalIncident).where(OperationalIncident.status!='resolved')) or 0
    critical=db.scalar(select(func.count()).select_from(OperationalIncident).where(OperationalIncident.status!='resolved',OperationalIncident.severity=='critical')) or 0
    failed=db.scalar(select(func.count()).select_from(AcceptanceRun).where(AcceptanceRun.status=='failed')) or 0
    dead=db.scalar(select(func.count()).select_from(IntegrationEvent).where(IntegrationEvent.status=='dead_letter')) or 0
    status='go' if high==0 and critical==0 and dead==0 else 'hold'
    return RolloutSummary(open_feedback=open_feedback,high_priority_feedback=high,open_incidents=incidents,critical_incidents=critical,failed_acceptance_runs=failed,dead_letter_events=dead,status=status)

@router.post('/rollout/smoke-test',response_model=SmokeTestResult)
def smoke_test(db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))):
    checks={}; db.execute(text('SELECT 1')); checks['database']=True
    checks['items']=db.scalar(select(func.count()).select_from(Item))>=0
    checks['locations']=db.scalar(select(func.count()).select_from(Location))>=0
    movement=db.execute(select(StockMovement.item_id,StockMovement.location_id,func.sum(StockMovement.quantity)).group_by(StockMovement.item_id,StockMovement.location_id)).all(); ledger={(a,b):c or 0 for a,b,c in movement}; mismatches=[]
    for b in db.scalars(select(StockBalance)).all():
        if ledger.get((b.item_id,b.location_id),0)!=b.quantity: mismatches.append(b.id)
    checks['stock_reconciliation']=not mismatches
    checks['dead_letters']=(db.scalar(select(func.count()).select_from(IntegrationEvent).where(IntegrationEvent.status=='dead_letter')) or 0)==0
    checks['backup_present']=db.scalar(select(func.count()).select_from(BackupRecord))>0
    return SmokeTestResult(status='passed' if all(checks.values()) else 'failed',checks=checks)
