from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.assets import AssetEvent, DepreciationLine, DepreciationRun, FixedAsset
from app.models.classification import OperationalDimension
from app.models.inventory import Item, Location
from app.models.user import User
from app.services.controls import add_audit, enqueue_event

router = APIRouter(tags=["assets"])
ZERO = Decimal("0")

def fail(code:int,message:str): raise HTTPException(code,message)
def now(): return datetime.now(timezone.utc)
def money(value): return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def dimension(db:Session, dimension_id:str, kind:str):
    row=db.get(OperationalDimension,dimension_id)
    if not row or row.dimension_type!=kind or not row.is_active: fail(422,f"Active {kind.replace('_',' ')} not found")
    return row

def fixed_asset_item(db:Session,item_id:str):
    item=db.get(Item,item_id)
    if not item or not item.is_active or not item.item_type_id: fail(422,"Active fixed-asset item not found")
    item_type=db.get(OperationalDimension,item.item_type_id)
    if not item_type or item_type.behavior_key!="fixed_asset": fail(422,"Item type must belong to the fixed-asset behavioral family")
    return item

def carrying_value(asset:FixedAsset): return money(asset.acquisition_cost)+money(asset.capitalized_cost)-money(asset.accumulated_depreciation)-money(asset.impairment_loss)

class AssetIn(BaseModel):
    asset_tag:str=Field(min_length=1,max_length=80); item_id:str; asset_class_id:str; depreciation_method_id:str
    location_id:str|None=None; department_id:str|None=None; cost_center_id:str|None=None; custodian_user_id:str|None=None
    supplier_id:str|None=None; purchase_order_id:str|None=None; goods_receipt_id:str|None=None
    serial_number:str|None=None; model_number:str|None=None; acquisition_date:date; placed_in_service_date:date|None=None
    acquisition_cost:Decimal=Field(ge=0); capitalized_cost:Decimal=Field(default=ZERO,ge=0); residual_value:Decimal=Field(default=ZERO,ge=0)
    useful_life_months:int=Field(default=60,ge=1,le=1200); warranty_expiry:date|None=None; notes:str|None=None

class AssetEventIn(BaseModel):
    event_type:str; event_date:date; to_location_id:str|None=None; amount:Decimal|None=Field(default=None,ge=0); notes:str|None=None

class RunIn(BaseModel): period:str=Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")

def asset_payload(asset:FixedAsset):
    return {"id":asset.id,"asset_tag":asset.asset_tag,"item_id":asset.item_id,"asset_class_id":asset.asset_class_id,"depreciation_method_id":asset.depreciation_method_id,"location_id":asset.location_id,"department_id":asset.department_id,"cost_center_id":asset.cost_center_id,"custodian_user_id":asset.custodian_user_id,"serial_number":asset.serial_number,"model_number":asset.model_number,"acquisition_date":asset.acquisition_date,"placed_in_service_date":asset.placed_in_service_date,"acquisition_cost":asset.acquisition_cost,"capitalized_cost":asset.capitalized_cost,"residual_value":asset.residual_value,"useful_life_months":asset.useful_life_months,"accumulated_depreciation":asset.accumulated_depreciation,"impairment_loss":asset.impairment_loss,"net_book_value":carrying_value(asset),"status":asset.status,"condition":asset.condition,"warranty_expiry":asset.warranty_expiry,"disposal_date":asset.disposal_date,"disposal_proceeds":asset.disposal_proceeds,"notes":asset.notes}

@router.get("/assets")
def list_assets(status:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission("inventory.read"))):
    stmt=select(FixedAsset).order_by(FixedAsset.asset_tag)
    if status: stmt=stmt.where(FixedAsset.status==status)
    return [asset_payload(x) for x in db.scalars(stmt).all()]

@router.post("/assets",status_code=201)
def create_asset(p:AssetIn,db:Session=Depends(get_db),user:User=Depends(require_permission("inventory.*"))):
    fixed_asset_item(db,p.item_id); dimension(db,p.asset_class_id,"asset_class"); method=dimension(db,p.depreciation_method_id,"depreciation_method")
    if p.location_id and not db.get(Location,p.location_id): fail(422,"Location not found")
    if money(p.residual_value)>money(p.acquisition_cost)+money(p.capitalized_cost): fail(422,"Residual value cannot exceed total capitalized cost")
    values=p.model_dump(exclude={"asset_tag"})
    row=FixedAsset(**values,asset_tag=p.asset_tag.upper().strip(),status="active" if p.placed_in_service_date else "candidate",created_by_user_id=user.id)
    if method.behavior_key=="no_depreciation": row.useful_life_months=1
    db.add(row)
    try:
        db.flush(); add_audit(db,actor_user_id=user.id,action="asset.created",entity_type="fixed_asset",entity_id=row.id,details={"asset_tag":row.asset_tag}); db.commit(); db.refresh(row); return asset_payload(row)
    except IntegrityError: db.rollback(); fail(409,"Asset tag already exists or asset references are invalid")

@router.post("/assets/{asset_id}/events",status_code=201)
def create_event(asset_id:str,p:AssetEventIn,db:Session=Depends(get_db),user:User=Depends(require_permission("inventory.*"))):
    asset=db.get(FixedAsset,asset_id)
    if not asset: fail(404,"Asset not found")
    if asset.status=="disposed": fail(409,"Disposed assets cannot be changed")
    from_location=asset.location_id
    if p.event_type=="place_in_service":
        if asset.placed_in_service_date: fail(409,"Asset is already in service")
        asset.placed_in_service_date=p.event_date; asset.status="active"
    elif p.event_type=="transfer":
        if not p.to_location_id or not db.get(Location,p.to_location_id): fail(422,"Destination location not found")
        asset.location_id=p.to_location_id
    elif p.event_type=="impairment":
        amount=money(p.amount)
        if amount<=0 or amount>carrying_value(asset)-money(asset.residual_value): fail(422,"Invalid impairment amount")
        asset.impairment_loss=money(asset.impairment_loss)+amount
    elif p.event_type=="dispose":
        asset.status="disposed"; asset.disposal_date=p.event_date; asset.disposal_proceeds=money(p.amount)
    else: fail(422,"Unsupported asset event")
    event=AssetEvent(asset_id=asset.id,event_type=p.event_type,event_date=p.event_date,from_location_id=from_location,to_location_id=p.to_location_id,amount=p.amount,notes=p.notes,created_by_user_id=user.id); db.add(event); db.flush()
    add_audit(db,actor_user_id=user.id,action=f"asset.{p.event_type}",entity_type="fixed_asset",entity_id=asset.id,details={"event_id":event.id,"amount":str(p.amount) if p.amount is not None else None})
    if p.event_type in {"impairment","dispose"}: enqueue_event(db,destination_system="accounting",event_type=f"inventory.asset.{p.event_type}",aggregate_type="fixed_asset",aggregate_id=asset.id,idempotency_key=f"asset-{p.event_type}:{event.id}",payload={"asset_id":asset.id,"asset_tag":asset.asset_tag,"amount":str(p.amount or 0),"net_book_value":str(carrying_value(asset))})
    db.commit(); db.refresh(event); return event

def monthly_amount(db:Session,asset:FixedAsset):
    method=db.get(OperationalDimension,asset.depreciation_method_id)
    if not method or method.behavior_key=="no_depreciation": return Decimal("0")
    depreciable=max(Decimal("0"),money(asset.acquisition_cost)+money(asset.capitalized_cost)-money(asset.residual_value)-money(asset.impairment_loss))
    remaining=max(Decimal("0"),depreciable-money(asset.accumulated_depreciation))
    return min(remaining,(depreciable/Decimal(asset.useful_life_months)).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))

@router.get("/depreciation-runs")
def list_runs(db:Session=Depends(get_db),_:User=Depends(require_permission("reports.read"))): return db.scalars(select(DepreciationRun).order_by(DepreciationRun.period.desc())).all()

@router.post("/depreciation-runs",status_code=201)
def create_run(p:RunIn,db:Session=Depends(get_db),user:User=Depends(require_permission("inventory.*"))):
    if db.scalar(select(DepreciationRun.id).where(DepreciationRun.period==p.period)): fail(409,"Depreciation run already exists for this period")
    run=DepreciationRun(period=p.period,created_by_user_id=user.id); db.add(run); db.flush(); total=Decimal("0")
    for asset in db.scalars(select(FixedAsset).where(FixedAsset.status=="active",FixedAsset.placed_in_service_date.is_not(None))).all():
        amount=monthly_amount(db,asset)
        if amount<=0: continue
        closing=money(asset.accumulated_depreciation)+amount; nbv=money(asset.acquisition_cost)+money(asset.capitalized_cost)-closing-money(asset.impairment_loss)
        db.add(DepreciationLine(run_id=run.id,asset_id=asset.id,amount=amount,opening_accumulated=asset.accumulated_depreciation,closing_accumulated=closing,closing_net_book_value=nbv)); total+=amount
    run.total_amount=money(total); add_audit(db,actor_user_id=user.id,action="depreciation.run_created",entity_type="depreciation_run",entity_id=run.id,details={"period":run.period,"total":str(run.total_amount)}); db.commit(); db.refresh(run); return run

@router.post("/depreciation-runs/{run_id}/post")
def post_run(run_id:str,db:Session=Depends(get_db),user:User=Depends(require_permission("inventory.*"))):
    run=db.scalar(select(DepreciationRun).where(DepreciationRun.id==run_id).with_for_update())
    if not run: fail(404,"Depreciation run not found")
    if run.status!="draft": fail(409,"Only draft depreciation runs can be posted")
    lines=db.scalars(select(DepreciationLine).where(DepreciationLine.run_id==run.id)).all()
    for line in lines:
        asset=db.get(FixedAsset,line.asset_id); asset.accumulated_depreciation=money(asset.accumulated_depreciation)+money(line.amount)
    run.status="posted"; run.posted_by_user_id=user.id; run.posted_at=now()
    enqueue_event(db,destination_system="accounting",event_type="inventory.asset.depreciation_posted",aggregate_type="depreciation_run",aggregate_id=run.id,idempotency_key=f"asset-depreciation:{run.period}",payload={"run_id":run.id,"period":run.period,"total_amount":str(run.total_amount),"lines":[{"asset_id":x.asset_id,"amount":str(x.amount)} for x in lines]})
    add_audit(db,actor_user_id=user.id,action="depreciation.run_posted",entity_type="depreciation_run",entity_id=run.id,details={"period":run.period,"total":str(run.total_amount)}); db.commit(); db.refresh(run); return run
