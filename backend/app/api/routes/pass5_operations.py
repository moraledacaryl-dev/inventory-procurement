from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from app.api.deps import require_permission
from app.db.session import get_db
from app.models.assets import FixedAsset
from app.models.inventory import Item, Location
from app.models.pass5 import MaintenancePlan, WorkOrder, WorkOrderPart, PurchaseLineTreatment, AccountingMapping
from app.models.user import User
from app.services.controls import add_audit, enqueue_event, next_document_number

router=APIRouter(tags=['maintenance-accounting'])
def fail(c,m): raise HTTPException(c,m)
def now(): return datetime.now(timezone.utc)

def work_order_payload(row:WorkOrder):
    return {
        'id':row.id,'work_order_number':row.work_order_number,'asset_id':row.asset_id,'plan_id':row.plan_id,
        'title':row.title,'description':row.description,'priority':row.priority,'status':row.status,
        'assigned_user_id':row.assigned_user_id,'contractor':row.contractor,'scheduled_date':row.scheduled_date,
        'started_at':row.started_at,'completed_at':row.completed_at,'labor_cost':row.labor_cost,
        'external_cost':row.external_cost,'downtime_hours':row.downtime_hours,'completion_notes':row.completion_notes,
        'created_by_user_id':row.created_by_user_id,'created_at':row.created_at,
        'parts':[{'id':x.id,'item_id':x.item_id,'quantity':x.quantity,'unit_cost':x.unit_cost} for x in row.parts],
    }

class PlanIn(BaseModel):
    code:str; name:str; asset_id:str; interval_days:int=Field(gt=0,le=3650); checklist:str|None=None; assigned_user_id:str|None=None; next_due_date:date
class PartIn(BaseModel): item_id:str; quantity:Decimal=Field(gt=0); unit_cost:Decimal=Field(default=0,ge=0)
class WorkOrderIn(BaseModel):
    asset_id:str; plan_id:str|None=None; title:str; description:str|None=None; priority:str='normal'; assigned_user_id:str|None=None; contractor:str|None=None; scheduled_date:date|None=None; parts:list[PartIn]=[]
class CompleteIn(BaseModel): labor_cost:Decimal=Field(default=0,ge=0); external_cost:Decimal=Field(default=0,ge=0); downtime_hours:Decimal=Field(default=0,ge=0); completion_notes:str|None=None
class TreatmentIn(BaseModel):
    source_type:str; source_line_id:str; treatment:str; workspace_id:str|None=None; department_id:str|None=None; cost_center_id:str|None=None; intended_location_id:str|None=None; asset_class_id:str|None=None; accounting_mapping_id:str|None=None; project_reference:str|None=None; notes:str|None=None
class MappingIn(BaseModel): event_key:str; dimension_id:str|None=None; debit_account:str; credit_account:str; description:str|None=None

@router.get('/maintenance/plans')
def plans(db:Session=Depends(get_db),_:User=Depends(require_permission('inventory.read'))): return db.scalars(select(MaintenancePlan).order_by(MaintenancePlan.next_due_date)).all()
@router.post('/maintenance/plans',status_code=201)
def create_plan(p:PlanIn,db:Session=Depends(get_db),u:User=Depends(require_permission('inventory.*'))):
    if not db.get(FixedAsset,p.asset_id): fail(422,'Asset not found')
    data=p.model_dump(); data['code']=p.code.upper().strip(); row=MaintenancePlan(**data); db.add(row)
    try: db.flush(); add_audit(db,actor_user_id=u.id,action='maintenance.plan_created',entity_type='maintenance_plan',entity_id=row.id,details={'asset_id':row.asset_id}); db.commit(); db.refresh(row); return row
    except IntegrityError: db.rollback(); fail(409,'Maintenance plan code already exists')

@router.get('/maintenance/work-orders')
def work_orders(status:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('inventory.read'))):
    q=select(WorkOrder).options(selectinload(WorkOrder.parts)).order_by(WorkOrder.created_at.desc())
    if status:q=q.where(WorkOrder.status==status)
    return [work_order_payload(x) for x in db.scalars(q).unique().all()]
@router.post('/maintenance/work-orders',status_code=201)
def create_work_order(p:WorkOrderIn,db:Session=Depends(get_db),u:User=Depends(require_permission('inventory.*'))):
    asset=db.get(FixedAsset,p.asset_id)
    if not asset or asset.status=='disposed': fail(422,'Active asset not found')
    if p.plan_id and not db.get(MaintenancePlan,p.plan_id): fail(422,'Maintenance plan not found')
    for part in p.parts:
        if not db.get(Item,part.item_id): fail(422,'Part item not found')
    data=p.model_dump(exclude={'parts'}); row=WorkOrder(work_order_number=next_document_number(db,'MWO'),**data,created_by_user_id=u.id)
    row.parts=[WorkOrderPart(**x.model_dump()) for x in p.parts]; db.add(row); db.flush(); add_audit(db,actor_user_id=u.id,action='maintenance.work_order_created',entity_type='maintenance_work_order',entity_id=row.id,details={'asset_id':row.asset_id}); db.commit()
    row=db.scalar(select(WorkOrder).where(WorkOrder.id==row.id).options(selectinload(WorkOrder.parts))); return work_order_payload(row)
@router.post('/maintenance/work-orders/{work_order_id}/start')
def start_work_order(work_order_id:str,db:Session=Depends(get_db),u:User=Depends(require_permission('inventory.*'))):
    row=db.scalar(select(WorkOrder).where(WorkOrder.id==work_order_id).options(selectinload(WorkOrder.parts)))
    if not row: fail(404,'Work order not found')
    if row.status!='open': fail(409,'Only open work orders can start')
    row.status='in_progress'; row.started_at=now(); db.commit(); db.refresh(row); return work_order_payload(row)
@router.post('/maintenance/work-orders/{work_order_id}/complete')
def complete_work_order(work_order_id:str,p:CompleteIn,db:Session=Depends(get_db),u:User=Depends(require_permission('inventory.*'))):
    row=db.scalar(select(WorkOrder).where(WorkOrder.id==work_order_id).options(selectinload(WorkOrder.parts)))
    if not row: fail(404,'Work order not found')
    if row.status not in {'open','in_progress'}: fail(409,'Work order cannot be completed')
    for k,v in p.model_dump().items(): setattr(row,k,v)
    row.status='completed'; row.completed_at=now()
    if row.plan_id:
        plan=db.get(MaintenancePlan,row.plan_id); plan.next_due_date=date.today()+timedelta(days=plan.interval_days)
    total=sum((Decimal(x.quantity)*Decimal(x.unit_cost) for x in row.parts),Decimal('0'))+Decimal(row.labor_cost)+Decimal(row.external_cost)
    enqueue_event(db,destination_system='accounting',event_type='inventory.maintenance.completed',aggregate_type='maintenance_work_order',aggregate_id=row.id,idempotency_key=f'maintenance:{row.id}',payload={'work_order_id':row.id,'asset_id':row.asset_id,'total_cost':str(total)})
    add_audit(db,actor_user_id=u.id,action='maintenance.work_order_completed',entity_type='maintenance_work_order',entity_id=row.id,details={'total_cost':str(total)}); db.commit(); db.refresh(row); return work_order_payload(row)

@router.get('/purchase-line-treatments')
def treatments(source_type:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('inventory.read'))):
    q=select(PurchaseLineTreatment)
    if source_type:q=q.where(PurchaseLineTreatment.source_type==source_type)
    return db.scalars(q.order_by(PurchaseLineTreatment.created_at.desc())).all()
@router.post('/purchase-line-treatments',status_code=201)
def set_treatment(p:TreatmentIn,db:Session=Depends(get_db),u:User=Depends(require_permission('inventory.*'))):
    allowed={'stock','reusable_property','fixed_asset','service_expense'}
    if p.treatment not in allowed: fail(422,'Unsupported purchasing treatment')
    if p.intended_location_id and not db.get(Location,p.intended_location_id): fail(422,'Location not found')
    row=db.scalar(select(PurchaseLineTreatment).where(PurchaseLineTreatment.source_type==p.source_type,PurchaseLineTreatment.source_line_id==p.source_line_id))
    if row:
        for k,v in p.model_dump().items(): setattr(row,k,v)
    else: row=PurchaseLineTreatment(**p.model_dump()); db.add(row)
    db.commit(); db.refresh(row); return row

@router.get('/accounting-mappings')
def mappings(db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))): return db.scalars(select(AccountingMapping).order_by(AccountingMapping.event_key)).all()
@router.post('/accounting-mappings',status_code=201)
def create_mapping(p:MappingIn,db:Session=Depends(get_db),u:User=Depends(require_permission('inventory.*'))):
    row=AccountingMapping(**p.model_dump()); db.add(row)
    try: db.commit(); db.refresh(row); return row
    except IntegrityError: db.rollback(); fail(409,'Accounting mapping already exists')