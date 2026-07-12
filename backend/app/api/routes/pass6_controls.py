from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import require_permission
from app.db.session import get_db
from app.models.assets import FixedAsset
from app.models.classification import OperationalDimension
from app.models.inventory import Item, Location, StockBalance
from app.models.pass5 import MaintenancePlan, WorkOrder
from app.models.pass6 import OperationalAccessScope, SavedView
from app.models.property import PropertyBalance
from app.models.user import User
from app.services.controls import add_audit

router=APIRouter(tags=['final-controls'])
def fail(code:int,message:str): raise HTTPException(code,message)
def dec(value): return Decimal(str(value or 0))

class ScopeIn(BaseModel):
    user_id:str; workspace_id:str|None=None; department_id:str|None=None; location_id:str|None=None; record_class_id:str|None=None; approval_limit:Decimal=Field(default=0,ge=0); is_active:bool=True
class SavedViewIn(BaseModel):
    module_key:str=Field(min_length=1,max_length=80); name:str=Field(min_length=1,max_length=120); filters:dict={}; columns:list=[]; is_default:bool=False


def validate_dimension(db:Session,value:str|None,kind:str):
    if not value:return
    row=db.get(OperationalDimension,value)
    if not row or row.dimension_type!=kind: fail(422,f'{kind.replace("_"," ").title()} not found')

@router.get('/access-scopes')
def access_scopes(user_id:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('users.read'))):
    q=select(OperationalAccessScope).order_by(OperationalAccessScope.user_id,OperationalAccessScope.created_at)
    if user_id:q=q.where(OperationalAccessScope.user_id==user_id)
    return db.scalars(q).all()

@router.post('/access-scopes',status_code=201)
def set_access_scope(p:ScopeIn,db:Session=Depends(get_db),u:User=Depends(require_permission('users.*'))):
    if not db.get(User,p.user_id): fail(422,'User not found')
    validate_dimension(db,p.workspace_id,'workspace'); validate_dimension(db,p.department_id,'department'); validate_dimension(db,p.record_class_id,'record_class')
    if p.location_id and not db.get(Location,p.location_id): fail(422,'Location not found')
    row=OperationalAccessScope(**p.model_dump()); db.add(row)
    try:
        db.flush(); add_audit(db,actor_user_id=u.id,action='access.scope_created',entity_type='operational_access_scope',entity_id=row.id,details={'user_id':row.user_id,'approval_limit':str(row.approval_limit)}); db.commit(); db.refresh(row); return row
    except IntegrityError:
        db.rollback(); fail(409,'This operational scope already exists')

@router.get('/saved-views')
def saved_views(module_key:str|None=None,db:Session=Depends(get_db),u:User=Depends(require_permission('inventory.read'))):
    q=select(SavedView).where(SavedView.user_id==u.id).order_by(SavedView.module_key,SavedView.name)
    if module_key:q=q.where(SavedView.module_key==module_key)
    return db.scalars(q).all()

@router.post('/saved-views',status_code=201)
def create_saved_view(p:SavedViewIn,db:Session=Depends(get_db),u:User=Depends(require_permission('inventory.read'))):
    if p.is_default:
        for row in db.scalars(select(SavedView).where(SavedView.user_id==u.id,SavedView.module_key==p.module_key)).all(): row.is_default=False
    row=SavedView(user_id=u.id,**p.model_dump()); db.add(row)
    try: db.commit(); db.refresh(row); return row
    except IntegrityError: db.rollback(); fail(409,'A saved view with this name already exists')

@router.get('/reports/operating-summary')
def operating_summary(workspace_id:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))):
    items={x.id:x for x in db.scalars(select(Item)).all()}
    stock_rows=db.scalars(select(StockBalance)).all(); stock_value=Decimal('0'); stock_units=Decimal('0')
    for row in stock_rows:
        item=items.get(row.item_id)
        if not item or (workspace_id and item.primary_workspace_id!=workspace_id): continue
        stock_units+=dec(row.quantity); stock_value+=dec(row.quantity)*dec(item.standard_cost)
    reusable_units=Decimal('0')
    for row in db.scalars(select(PropertyBalance)).all():
        item=items.get(row.item_id)
        if item and (not workspace_id or item.primary_workspace_id==workspace_id): reusable_units+=dec(row.quantity)
    assets=db.scalars(select(FixedAsset)).all(); gross=Decimal('0'); accumulated=Decimal('0'); impairment=Decimal('0')
    for asset in assets:
        item=items.get(asset.item_id)
        if item and workspace_id and item.primary_workspace_id!=workspace_id: continue
        gross+=dec(asset.acquisition_cost)+dec(asset.capitalized_cost); accumulated+=dec(asset.accumulated_depreciation); impairment+=dec(asset.impairment_loss)
    overdue=db.scalar(select(func.count()).select_from(MaintenancePlan).where(MaintenancePlan.is_active.is_(True),MaintenancePlan.next_due_date<date.today())) or 0
    open_work_orders=db.scalar(select(func.count()).select_from(WorkOrder).where(WorkOrder.status.in_(['open','in_progress']))) or 0
    unclassified=sum(1 for x in items.values() if x.is_active and (not x.primary_workspace_id or not x.item_type_id or not x.record_class_id))
    return {'workspace_id':workspace_id,'stock_units':str(stock_units),'stock_value':str(stock_value.quantize(Decimal('0.01'))),'reusable_units':str(reusable_units),'gross_asset_cost':str(gross.quantize(Decimal('0.01'))),'accumulated_depreciation':str(accumulated.quantize(Decimal('0.01'))),'impairment_loss':str(impairment.quantize(Decimal('0.01'))),'net_fixed_assets':str((gross-accumulated-impairment).quantize(Decimal('0.01'))),'overdue_maintenance':overdue,'open_work_orders':open_work_orders,'unclassified_items':unclassified}

@router.get('/classification/migration-review')
def migration_review(limit:int=Query(default=500,ge=1,le=2000),db:Session=Depends(get_db),_:User=Depends(require_permission('inventory.read'))):
    rows=db.scalars(select(Item).where(Item.is_active.is_(True)).order_by(Item.sku).limit(limit)).all()
    return [{'id':x.id,'sku':x.sku,'name':x.name,'primary_workspace_id':x.primary_workspace_id,'item_type_id':x.item_type_id,'record_class_id':x.record_class_id,'complete':bool(x.primary_workspace_id and x.item_type_id and x.record_class_id)} for x in rows]
