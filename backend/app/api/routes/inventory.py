from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from app.api.deps import require_permission
from app.db.session import get_db
from app.models.user import User
from app.models.inventory import Category, UnitOfMeasure, Location, Item, StockBalance, StockMovement, CountSession, CountLine
from app.schemas.inventory import *
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
def create_item(p:ItemCreate,db:Session=Depends(get_db),_:User=Depends(require_permission("items.*"))):
    if not db.get(Category,p.category_id) or not db.get(UnitOfMeasure,p.base_unit_id): raise HTTPException(422,"Category or unit not found")
    data=p.model_dump(); data["sku"]=p.sku.upper().strip(); data["name"]=p.name.strip(); return save(db,Item(**data))
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
@router.post("/counts",response_model=CountOut,status_code=201)
def create_count(p:CountCreate,db:Session=Depends(get_db),user:User=Depends(require_permission("counts.create"))):
    if not db.get(Location,p.location_id): raise HTTPException(422,"Location not found")
    session=CountSession(count_number=f"COUNT-{db.query(CountSession).count()+1:06d}",location_id=p.location_id,notes=p.notes,created_by_user_id=user.id); db.add(session); db.flush()
    items=db.scalars(select(Item).where(Item.is_active==True,Item.track_stock==True)).all(); balances={b.item_id:b for b in db.scalars(select(StockBalance).where(StockBalance.location_id==p.location_id)).all()}
    for item in items: session.lines.append(CountLine(item_id=item.id,system_quantity=balances.get(item.id).quantity if balances.get(item.id) else 0))
    db.commit(); db.refresh(session); return session
@router.get("/counts",response_model=list[CountOut])
def list_counts(db:Session=Depends(get_db),_:User=Depends(require_permission("counts.create"))): return db.scalars(select(CountSession).options(selectinload(CountSession.lines)).order_by(CountSession.created_at.desc())).all()
@router.post("/counts/{count_id}/post",response_model=CountOut)
def post_count(count_id:str,p:CountSubmit,db:Session=Depends(get_db),user:User=Depends(require_permission("counts.submit"))):
    session=db.scalar(select(CountSession).where(CountSession.id==count_id).options(selectinload(CountSession.lines)).with_for_update())
    if not session: raise HTTPException(404,"Count not found")
    if session.status!="open": conflict("Count is already posted")
    submitted={x.item_id:x for x in p.lines}; entries=[]
    current_balances={b.item_id:Decimal(b.quantity) for b in db.scalars(select(StockBalance).where(StockBalance.location_id==session.location_id).with_for_update()).all()}
    for line in session.lines:
        if line.item_id not in submitted: continue
        entry=submitted[line.item_id]; line.counted_quantity=entry.counted_quantity; line.note=entry.note
        delta=Decimal(entry.counted_quantity)-current_balances.get(line.item_id,Decimal("0"))
        if delta: entries.append({"item_id":line.item_id,"location_id":session.location_id,"quantity":delta,"unit_cost":0,"reason":"physical count variance"})
    try:
        if entries:
            doc=post_document(db,kind="count_adjustment",actor_id=user.id,entries=entries,reference=session.count_number,commit=False)
            session.posted_document_id=doc.id
        session.status="posted"; db.commit(); db.refresh(session); return session
    except (InventoryError,IntegrityError) as exc:
        db.rollback(); conflict(exc if isinstance(exc,InventoryError) else "Count could not be posted")
