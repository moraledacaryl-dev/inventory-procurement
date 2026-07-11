from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from app.api.deps import require_permission
from app.db.session import get_db
from app.models.user import User
from app.models.inventory import Category, UnitOfMeasure, Location, Item, StockBalance, StockMovement, StockDocument, CountSession, CountLine
from app.schemas.inventory import *
from app.services.controls import add_audit, next_document_number
from app.services.inventory import InventoryError, post_document, receipt_entries, issue_entries, transfer_entries
router = APIRouter(tags=["inventory"])
def conflict(exc): raise HTTPException(status_code=409, detail=str(exc))
def save(db,row):
    db.add(row)
    try: db.commit(); db.refresh(row); return row
    except IntegrityError: db.rollback(); conflict("Duplicate or invalid record")
@router.get("/categories",response_model=list[CategoryOut])
def list_categories(db:Session=Depends(get_db),_:User=Depends(require_permission("items.read"))): return db.scalars(select(Category).order_by(Category.name)).all()
@router.post("/categories",response_model=CategoryOut,status_code=201)
def create_category(p:CategoryCreate,db:Session=Depends(get_db),_:User=Depends(require_permission("items.*"))): return save(db,Category(name=p.name.strip(),description=p.description))
@router.get("/units",response_model=list[UnitOut])
def list_units(db:Session=Depends(get_db),_:User=Depends(require_permission("items.read"))): return db.scalars(select(UnitOfMeasure).order_by(UnitOfMeasure.code)).all()
@router.post("/units",response_model=UnitOut,status_code=201)
def create_unit(p:UnitCreate,db:Session=Depends(get_db),_:User=Depends(require_permission("items.*"))): return save(db,UnitOfMeasure(code=p.code.upper().strip(),name=p.name.strip(),precision=p.precision))
@router.get("/locations",response_model=list[LocationOut])
def list_locations(db:Session=Depends(get_db),_:User=Depends(require_permission("locations.read"))): return db.scalars(select(Location).order_by(Location.code)).all()
@router.post("/locations",response_model=LocationOut,status_code=201)
def create_location(p:LocationCreate,db:Session=Depends(get_db),_:User=Depends(require_permission("locations.*"))):
    if p.parent_id and not db.get(Location,p.parent_id): raise HTTPException(422,"Parent location not found")
    return save(db,Location(code=p.code.upper().strip(),name=p.name.strip(),location_type=p.location_type,parent_id=p.parent_id))
@router.get("/items",response_model=list[ItemOut])
def list_items(q:str|None=None,active:bool|None=True,db:Session=Depends(get_db),_:User=Depends(require_permission("items.read"))):
    stmt=select(Item).order_by(Item.sku)
    if q: stmt=stmt.where((Item.sku.ilike(f"%{q}%"))|(Item.name.ilike(f"%{q}%")))
    if active is not None: stmt=stmt.where(Item.is_active==active)
    return db.scalars(stmt).all()
@router.post("/items",response_model=ItemOut,status_code=201)
def create_item(p:ItemCreate,db:Session=Depends(get_db),user:User=Depends(require_permission("items.*"))):
    if not db.get(Category,p.category_id) or not db.get(UnitOfMeasure,p.base_unit_id): raise HTTPException(422,"Category or unit not found")
    data=p.model_dump(); data["sku"]=p.sku.upper().strip(); data["name"]=p.name.strip(); item=save(db,Item(**data)); add_audit(db,actor_user_id=user.id,action="item.created",entity_type="item",entity_id=item.id,details={"sku":item.sku}); db.commit(); return item
@router.get("/items/{item_id}",response_model=ItemDetail)
def item_detail(item_id:str,db:Session=Depends(get_db),_:User=Depends(require_permission("items.read"))):
    item=db.get(Item,item_id)
    if not item: raise HTTPException(404,"Item not found")
    category=db.get(Category,item.category_id); unit=db.get(UnitOfMeasure,item.base_unit_id)
    balance_rows=db.execute(select(StockBalance,Location).join(Location,Location.id==StockBalance.location_id).where(StockBalance.item_id==item.id).order_by(Location.code)).all()
    movement_rows=db.execute(select(StockMovement,StockDocument,Location).join(StockDocument,StockDocument.id==StockMovement.document_id).join(Location,Location.id==StockMovement.location_id).where(StockMovement.item_id==item.id).order_by(StockMovement.created_at.desc()).limit(25)).all()
    total_quantity=sum((Decimal(balance.quantity) for balance,_location in balance_rows),Decimal("0"))
    total_value=sum((Decimal(balance.quantity)*Decimal(balance.average_cost) for balance,_location in balance_rows),Decimal("0"))
    average_cost=total_value/total_quantity if total_quantity else Decimal(item.standard_cost or 0)
    return ItemDetail(item=item,category=category,base_unit=unit,totals={"quantity":total_quantity,"inventory_value":total_value,"average_cost":average_cost,"location_count":len(balance_rows),"movement_count":db.scalar(select(func.count()).select_from(StockMovement).where(StockMovement.item_id==item.id)) or 0},balances=[ItemBalanceDetail(location_id=balance.location_id,location_code=location.code,location_name=location.name,quantity=balance.quantity,average_cost=balance.average_cost,inventory_value=Decimal(balance.quantity)*Decimal(balance.average_cost),updated_at=balance.updated_at) for balance,location in balance_rows],recent_movements=[ItemMovementDetail(id=movement.id,location_id=movement.location_id,location_name=location.name,document_number=document.document_number,document_type=document.document_type,quantity=movement.quantity,unit_cost=movement.unit_cost,reason=movement.reason,created_at=movement.created_at) for movement,document,location in movement_rows])
@router.patch("/items/{item_id}",response_model=ItemOut)
def update_item(item_id:str,p:ItemUpdate,db:Session=Depends(get_db),user:User=Depends(require_permission("items.*"))):
    item=db.get(Item,item_id)
    if not item: raise HTTPException(404,"Item not found")
    data=p.model_dump(exclude_unset=True)
    if data.get("category_id") and not db.get(Category,data["category_id"]): raise HTTPException(422,"Category not found")
    if data.get("base_unit_id") and not db.get(UnitOfMeasure,data["base_unit_id"]): raise HTTPException(422,"Unit not found")
    if "name" in data: data["name"]=data["name"].strip()
    if data.get("is_active") is False:
        balance_total=db.scalar(select(func.coalesce(func.sum(StockBalance.quantity),0)).where(StockBalance.item_id==item.id)) or 0
        if Decimal(balance_total)!=0: conflict("Item with non-zero stock cannot be deactivated")
    changes={key:{"from":str(getattr(item,key)),"to":str(value)} for key,value in data.items() if getattr(item,key)!=value}
    for key,value in data.items(): setattr(item,key,value)
    try:
        add_audit(db,actor_user_id=user.id,action="item.updated",entity_type="item",entity_id=item.id,details={"changes":changes}); db.commit(); db.refresh(item); return item
    except IntegrityError: db.rollback(); conflict("Item update could not be saved")
@router.get("/stock/balances",response_model=list[BalanceOut])
def balances(item_id:str|None=None,location_id:str|None=None,low_stock:bool=False,db:Session=Depends(get_db),_:User=Depends(require_permission("inventory.read"))):
    stmt=select(StockBalance)
    if item_id: stmt=stmt.where(StockBalance.item_id==item_id)
    if location_id: stmt=stmt.where(StockBalance.location_id==location_id)
    rows=db.scalars(stmt.order_by(StockBalance.location_id,StockBalance.item_id)).all()
    if low_stock:
        items={i.id:i for i in db.scalars(select(Item)).all()}; rows=[r for r in rows if Decimal(r.quantity)<=Decimal(items[r.item_id].minimum_stock)]
    return rows
@router.get("/stock/movements",response_model=list[MovementOut])
def movements(item_id:str|None=None,location_id:str|None=None,limit:int=Query(100,ge=1,le=500),db:Session=Depends(get_db),_:User=Depends(require_permission("inventory.read"))):
    stmt=select(StockMovement)
    if item_id: stmt=stmt.where(StockMovement.item_id==item_id)
    if location_id: stmt=stmt.where(StockMovement.location_id==location_id)
    return db.scalars(stmt.order_by(StockMovement.created_at.desc()).limit(limit)).all()
def post(kind,p,entries,user,db):
    try: return post_document(db,kind=kind,actor_id=user.id,entries=entries,reference=p.reference,notes=p.notes,idempotency_key=p.idempotency_key)
    except InventoryError as exc: conflict(exc)
@router.post("/stock/receipts",response_model=DocumentOut,status_code=201)
def receipt(p:ReceiptCreate,db:Session=Depends(get_db),user:User=Depends(require_permission("inventory.*"))): return post("receipt",p,receipt_entries(p.location_id,p.lines),user,db)
@router.post("/stock/issues",response_model=DocumentOut,status_code=201)
def issue(p:IssueCreate,db:Session=Depends(get_db),user:User=Depends(require_permission("inventory.*"))): return post("issue",p,issue_entries(p.location_id,p.lines),user,db)
@router.post("/stock/transfers",response_model=DocumentOut,status_code=201)
def transfer(p:TransferCreate,db:Session=Depends(get_db),user:User=Depends(require_permission("inventory.*"))):
    try: entries=transfer_entries(p.source_location_id,p.destination_location_id,p.lines)
    except InventoryError as exc: conflict(exc)
    return post("transfer",p,entries,user,db)
@router.post("/stock/adjustments",response_model=DocumentOut,status_code=201)
def adjustment(p:AdjustmentCreate,db:Session=Depends(get_db),user:User=Depends(require_permission("inventory.*"))):
    entries=[{"item_id":x.item_id,"location_id":p.location_id,"quantity":x.quantity_delta,"unit_cost":x.unit_cost,"reason":x.reason} for x in p.lines]
    return post("adjustment",p,entries,user,db)

def current_count_entries(db:Session,session:CountSession):
    balances={b.item_id:Decimal(b.quantity) for b in db.scalars(select(StockBalance).where(StockBalance.location_id==session.location_id).with_for_update()).all()}
    entries=[]
    for line in session.lines:
        if line.counted_quantity is None: continue
        delta=Decimal(line.counted_quantity)-balances.get(line.item_id,Decimal("0"))
        if delta: entries.append({"item_id":line.item_id,"location_id":session.location_id,"quantity":delta,"unit_cost":0,"reason":"physical count variance"})
    return entries

def finalize_count(db:Session,session:CountSession,user:User):
    entries=current_count_entries(db,session)
    if entries:
        doc=post_document(db,kind="count_adjustment",actor_id=user.id,entries=entries,reference=session.count_number,commit=False)
        session.posted_document_id=doc.id
    session.status="posted"
    add_audit(db,actor_user_id=user.id,action='count.posted',entity_type='count_session',entity_id=session.id,details={'line_count':len(entries)})

@router.post("/counts",response_model=CountOut,status_code=201)
def create_count(p:CountCreate,db:Session=Depends(get_db),user:User=Depends(require_permission("counts.create"))):
    if not db.get(Location,p.location_id): raise HTTPException(422,"Location not found")
    session=CountSession(count_number=next_document_number(db,'COUNT'),location_id=p.location_id,notes=p.notes,blind_count=p.blind_count,approval_threshold=p.approval_threshold,created_by_user_id=user.id); db.add(session); db.flush()
    items=db.scalars(select(Item).where(Item.is_active==True,Item.track_stock==True)).all(); balances={b.item_id:b for b in db.scalars(select(StockBalance).where(StockBalance.location_id==p.location_id)).all()
    for item in items: session.lines.append(CountLine(item_id=item.id,system_quantity=balances.get(item.id).quantity if balances.get(item.id) else 0))
    add_audit(db,actor_user_id=user.id,action='count.created',entity_type='count_session',entity_id=session.id,details={'blind_count':p.blind_count,'approval_threshold':str(p.approval_threshold)}); db.commit(); db.refresh(session); return session
@router.get("/counts",response_model=list[CountOut])
def list_counts(db:Session=Depends(get_db),_:User=Depends(require_permission("counts.create"))): return db.scalars(select(CountSession).options(selectinload(CountSession.lines)).order_by(CountSession.created_at.desc())).unique().all()
@router.get('/counts/{count_id}/worksheet',response_model=CountWorksheet)
def count_worksheet(count_id:str,db:Session=Depends(get_db),_:User=Depends(require_permission('counts.create'))):
    session=db.scalar(select(CountSession).where(CountSession.id==count_id).options(selectinload(CountSession.lines)))
    if not session: raise HTTPException(404,'Count not found')
    return CountWorksheet(id=session.id,count_number=session.count_number,location_id=session.location_id,blind_count=session.blind_count,lines=[CountWorksheetLine(item_id=x.item_id,counted_quantity=x.counted_quantity,note=x.note) for x in session.lines])
@router.post("/counts/{count_id}/post",response_model=CountOut)
def post_count(count_id:str,p:CountSubmit,db:Session=Depends(get_db),user:User=Depends(require_permission("counts.submit"))):
    session=db.scalar(select(CountSession).where(CountSession.id==count_id).options(selectinload(CountSession.lines)).with_for_update())
    if not session: raise HTTPException(404,"Count not found")
    if session.status!="open": conflict("Count is not open")
    submitted={x.item_id:x for x in p.lines}; current={b.item_id:Decimal(b.quantity) for b in db.scalars(select(StockBalance).where(StockBalance.location_id==session.location_id).with_for_update()).all()}; max_variance=Decimal('0')
    for line in session.lines:
        if line.item_id not in submitted: continue
        entry=submitted[line.item_id]; line.counted_quantity=entry.counted_quantity; line.note=entry.note; max_variance=max(max_variance,abs(Decimal(entry.counted_quantity)-current.get(line.item_id,Decimal('0'))))
    try:
        if Decimal(session.approval_threshold)>0 and max_variance>Decimal(session.approval_threshold):
            session.status='pending_approval'; add_audit(db,actor_user_id=user.id,action='count.approval_requested',entity_type='count_session',entity_id=session.id,details={'max_variance':str(max_variance)})
        else: finalize_count(db,session,user)
        db.commit(); db.refresh(session); return session
    except (InventoryError,IntegrityError) as exc:
        db.rollback(); conflict(exc if isinstance(exc,InventoryError) else "Count could not be posted")
@router.post('/counts/{count_id}/approve',response_model=CountOut)
def approve_count(count_id:str,db:Session=Depends(get_db),user:User=Depends(require_permission('counts.submit'))):
    session=db.scalar(select(CountSession).where(CountSession.id==count_id).options(selectinload(CountSession.lines)).with_for_update())
    if not session: raise HTTPException(404,'Count not found')
    if session.status!='pending_approval': conflict('Count is not pending approval')
    if session.created_by_user_id==user.id: conflict('Count creator cannot approve their own variance')
    try:
        session.approved_by_user_id=user.id; session.approved_at=datetime.now(timezone.utc); finalize_count(db,session,user); add_audit(db,actor_user_id=user.id,action='count.approved',entity_type='count_session',entity_id=session.id); db.commit(); db.refresh(session); return session
    except (InventoryError,IntegrityError) as exc:
        db.rollback(); conflict(exc if isinstance(exc,InventoryError) else 'Count approval failed')
