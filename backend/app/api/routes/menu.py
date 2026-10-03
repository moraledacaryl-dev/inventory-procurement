from decimal import Decimal
import secrets
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session,selectinload
from app.api.deps import require_permission
from app.db.session import get_db
from app.models.menu import MenuItem,MenuVariant
from app.models.production import Recipe
from app.models.inventory import Item
from app.models.user import User
from app.services.controls import add_audit
router=APIRouter(tags=["fnb-menu"])
class VariantIn(BaseModel):
    id:str|None=None
    name:str=Field(default="Regular",min_length=1,max_length=120)
    sku:str|None=Field(default=None,max_length=80)
    barcode:str|None=Field(default=None,max_length=100)
    price:Decimal=Field(ge=0)
    with_drink_price:Decimal|None=Field(default=None,ge=0)
    recipe_id:str|None=None
    inventory_item_id:str|None=None
    is_active:bool=True
class MenuIn(BaseModel):
    name:str=Field(min_length=1,max_length=180)
    display_name:str|None=Field(default=None,max_length=180)
    category:str=Field(min_length=1,max_length=100)
    description:str|None=None
    prep_station:str=Field(default="bar",max_length=40)
    is_active:bool=True
    pos_visible:bool=True
    variants:list[VariantIn]=Field(min_length=1)
def code(prefix): return prefix+f"{secrets.randbelow(10**10):010d}"
def validate(db,row):
    if row.recipe_id and not db.get(Recipe,row.recipe_id): raise HTTPException(422,"Recipe not found")
    if row.inventory_item_id and not db.get(Item,row.inventory_item_id): raise HTTPException(422,"Inventory item not found")
    if row.with_drink_price is not None and row.with_drink_price>row.price: raise HTTPException(422,"With-drink price cannot exceed regular price")
def serial(row):
    return {"id":row.id,"name":row.name,"display_name":row.display_name,"category":row.category,"description":row.description,"prep_station":row.prep_station,"sort_order":row.sort_order,"is_active":row.is_active,"pos_visible":row.pos_visible,"variants":[{"id":v.id,"name":v.name,"sku":v.sku,"barcode":v.barcode,"price":str(v.price),"with_drink_price":str(v.with_drink_price) if v.with_drink_price is not None else None,"recipe_id":v.recipe_id,"inventory_item_id":v.inventory_item_id,"sort_order":v.sort_order,"is_active":v.is_active} for v in row.variants]}
@router.get("/fnb/menu")
def list_menu(include_inactive:bool=False,db:Session=Depends(get_db),_:User=Depends(require_permission("items.read"))):
    stmt=select(MenuItem).options(selectinload(MenuItem.variants)).order_by(MenuItem.category,MenuItem.sort_order,MenuItem.display_name)
    if not include_inactive: stmt=stmt.where(MenuItem.is_active.is_(True))
    return [serial(x) for x in db.scalars(stmt).unique().all()]
def variants(db,item,rows):
    old={v.id:v for v in item.variants};keep=set()
    for order,data in enumerate(rows):
        validate(db,data);v=old.get(data.id) if data.id else None
        if not v: v=MenuVariant(menu_item_id=item.id);db.add(v)
        v.name=data.name.strip();v.sku=(data.sku or code("HO-")).upper().strip();v.barcode=(data.barcode or code("20")).strip();v.price=data.price;v.with_drink_price=data.with_drink_price;v.recipe_id=data.recipe_id;v.inventory_item_id=data.inventory_item_id;v.sort_order=order;v.is_active=data.is_active
        db.flush();keep.add(v.id)
    for v in item.variants:
        if v.id not in keep:v.is_active=False
@router.post("/fnb/menu",status_code=201)
def create(payload:MenuIn,db:Session=Depends(get_db),user:User=Depends(require_permission("items.*"))):
    item=MenuItem(name=payload.name.strip(),display_name=(payload.display_name or payload.name).strip(),category=payload.category.strip(),description=payload.description,prep_station=payload.prep_station.strip(),is_active=payload.is_active,pos_visible=payload.pos_visible);db.add(item)
    try:
        db.flush();variants(db,item,payload.variants);add_audit(db,actor_user_id=user.id,action="menu.item_created",entity_type="menu_item",entity_id=item.id,details={"name":item.name,"category":item.category});db.commit()
        return serial(db.scalar(select(MenuItem).where(MenuItem.id==item.id).options(selectinload(MenuItem.variants))))
    except IntegrityError: db.rollback();raise HTTPException(409,"Duplicate SKU/barcode or invalid menu configuration")
@router.put("/fnb/menu/{item_id}")
def update(item_id:str,payload:MenuIn,db:Session=Depends(get_db),user:User=Depends(require_permission("items.*"))):
    item=db.scalar(select(MenuItem).where(MenuItem.id==item_id).options(selectinload(MenuItem.variants)))
    if not item:raise HTTPException(404,"Menu item not found")
    item.name=payload.name.strip();item.display_name=(payload.display_name or payload.name).strip();item.category=payload.category.strip();item.description=payload.description;item.prep_station=payload.prep_station.strip();item.is_active=payload.is_active;item.pos_visible=payload.pos_visible
    try:
        variants(db,item,payload.variants);add_audit(db,actor_user_id=user.id,action="menu.item_updated",entity_type="menu_item",entity_id=item.id,details={"name":item.name});db.commit()
        return serial(db.scalar(select(MenuItem).where(MenuItem.id==item.id).options(selectinload(MenuItem.variants))))
    except IntegrityError:db.rollback();raise HTTPException(409,"Duplicate SKU/barcode or invalid menu configuration")
