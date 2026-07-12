from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from app.api.deps import require_permission
from app.db.session import get_db
from app.models.user import User
from app.models.inventory import Item, Location, StockBalance, StockDocument, StockMovement
from app.models.classification import OperationalDimension, ItemWorkspaceAssignment
from app.models.operations import IntegrationEvent
from app.models.production import Recipe, RecipeLine, ProductionBatch, PosProductMapping, PosSaleEvent
from app.schemas.production import *
from app.services.controls import add_audit, add_notification, enqueue_event, next_document_number
from app.services.inventory import InventoryError, post_document

router=APIRouter(tags=['production'])
INGREDIENT_BEHAVIORS={'ingredient','recipe_output','recipe_packaging'}
OUTPUT_BEHAVIORS={'recipe_output'}
def fail(code:int,message:str): raise HTTPException(code,message)
def now(): return datetime.now(timezone.utc)
def load_recipe(db,id): return db.scalar(select(Recipe).where(Recipe.id==id).options(selectinload(Recipe.lines)))
def balance(db,item_id,location_id):
    row=db.scalar(select(StockBalance).where(StockBalance.item_id==item_id,StockBalance.location_id==location_id))
    return Decimal(row.quantity) if row else Decimal('0')
def avg_cost(db,item_id,location_id):
    row=db.scalar(select(StockBalance).where(StockBalance.item_id==item_id,StockBalance.location_id==location_id))
    if row: return Decimal(row.average_cost)
    item=db.get(Item,item_id); return Decimal(item.standard_cost if item else 0)

def fnb_workspace_ids(db:Session)->set[str]:
    return set(db.scalars(select(OperationalDimension.id).where(OperationalDimension.dimension_type=='workspace',OperationalDimension.behavior_key=='fnb',OperationalDimension.is_active.is_(True))).all())

def recipe_item_behavior(db:Session,item:Item|None)->str|None:
    if not item or not item.is_active or not item.item_type_id:return None
    fnb_ids=fnb_workspace_ids(db)
    assigned=item.primary_workspace_id in fnb_ids or bool(db.scalar(select(ItemWorkspaceAssignment.id).where(ItemWorkspaceAssignment.item_id==item.id,ItemWorkspaceAssignment.workspace_id.in_(fnb_ids)).limit(1)))
    if not assigned:return None
    item_type=db.get(OperationalDimension,item.item_type_id)
    return item_type.behavior_key if item_type and item_type.dimension_type=='item_type' and item_type.is_active else None

def require_recipe_item(db:Session,item_id:str,allowed:set[str],label:str)->Item:
    item=db.get(Item,item_id)
    behavior=recipe_item_behavior(db,item)
    if behavior not in allowed:fail(422,f'{label} must be an active F&B item with a compatible item type')
    return item

def recipe_entries(db,recipe:Recipe,location_id:str,output_quantity:Decimal,consume_only:bool=False):
    factor=output_quantity/Decimal(recipe.yield_quantity); entries=[]; total_cost=Decimal('0')
    for line in recipe.lines:
        qty=Decimal(line.quantity)*factor*(Decimal('1')+Decimal(line.waste_factor)); cost=avg_cost(db,line.ingredient_item_id,location_id); total_cost+=qty*cost
        entries.append({'item_id':line.ingredient_item_id,'location_id':location_id,'quantity':-qty,'unit_cost':cost,'reason':'recipe consumption'})
    if not consume_only: entries.append({'item_id':recipe.output_item_id,'location_id':location_id,'quantity':output_quantity,'unit_cost':total_cost/output_quantity,'reason':'production output'})
    return entries,total_cost

@router.get('/recipes/item-options')
def recipe_item_options(db:Session=Depends(get_db),_:User=Depends(require_permission('inventory.read'))):
    items=db.scalars(select(Item).where(Item.is_active.is_(True)).order_by(Item.sku)).all();ingredients=[];outputs=[]
    for item in items:
        behavior=recipe_item_behavior(db,item)
        row={'id':item.id,'sku':item.sku,'name':item.name,'item_type_behavior':behavior}
        if behavior in INGREDIENT_BEHAVIORS:ingredients.append(row)
        if behavior in OUTPUT_BEHAVIORS:outputs.append(row)
    return {'ingredients':ingredients,'outputs':outputs}

@router.get('/recipes',response_model=list[RecipeOut])
def recipes(status:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('inventory.read'))):
    stmt=select(Recipe).options(selectinload(Recipe.lines)).order_by(Recipe.code)
    if status: stmt=stmt.where(Recipe.status==status)
    return db.scalars(stmt).unique().all()
@router.post('/recipes',response_model=RecipeOut,status_code=201)
def create_recipe(p:RecipeCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('inventory.*'))):
    require_recipe_item(db,p.output_item_id,OUTPUT_BEHAVIORS,'Output item')
    ids=[x.ingredient_item_id for x in p.lines]
    if len(ids)!=len(set(ids)) or p.output_item_id in ids: fail(422,'Recipe ingredients must be unique and cannot equal output item')
    for item_id in ids:require_recipe_item(db,item_id,INGREDIENT_BEHAVIORS,'Ingredient')
    row=Recipe(code=p.code.upper().strip(),name=p.name.strip(),output_item_id=p.output_item_id,yield_quantity=p.yield_quantity,notes=p.notes,created_by_user_id=user.id)
    row.lines=[RecipeLine(**x.model_dump()) for x in p.lines]; db.add(row)
    try:
        db.flush(); add_audit(db,actor_user_id=user.id,action='recipe.created',entity_type='recipe',entity_id=row.id,details={'line_count':len(row.lines)}); db.commit(); return load_recipe(db,row.id)
    except IntegrityError: db.rollback(); fail(409,'Duplicate recipe code or ingredient')
@router.post('/recipes/{recipe_id}/approve',response_model=RecipeOut)
def approve_recipe(recipe_id:str,db:Session=Depends(get_db),user:User=Depends(require_permission('inventory.*'))):
    row=load_recipe(db,recipe_id)
    if not row: fail(404,'Recipe not found')
    if row.status!='draft': fail(409,'Only draft recipes can be approved')
    if row.created_by_user_id==user.id: fail(409,'Recipe creator cannot approve their own recipe')
    require_recipe_item(db,row.output_item_id,OUTPUT_BEHAVIORS,'Output item')
    for line in row.lines:require_recipe_item(db,line.ingredient_item_id,INGREDIENT_BEHAVIORS,'Ingredient')
    row.status='approved'; row.approved_by_user_id=user.id; row.approved_at=now(); add_audit(db,actor_user_id=user.id,action='recipe.approved',entity_type='recipe',entity_id=row.id); db.commit(); return load_recipe(db,row.id)
@router.get('/recipes/{recipe_id}/cost',response_model=RecipeCostOut)
def recipe_cost(recipe_id:str,location_id:str,db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))):
    recipe=load_recipe(db,recipe_id)
    if not recipe or not db.get(Location,location_id): fail(404,'Recipe or location not found')
    total=Decimal('0'); possible=[]
    for line in recipe.lines:
        required=Decimal(line.quantity)*(Decimal('1')+Decimal(line.waste_factor)); total+=required*avg_cost(db,line.ingredient_item_id,location_id)
        if not line.optional and required>0: possible.append(balance(db,line.ingredient_item_id,location_id)/required*Decimal(recipe.yield_quantity))
    return RecipeCostOut(recipe_id=recipe.id,yield_quantity=recipe.yield_quantity,total_cost=total,cost_per_output_unit=total/Decimal(recipe.yield_quantity),available_output_quantity=min(possible) if possible else Decimal('0'))

@router.get('/production-batches',response_model=list[ProductionOut])
def batches(db:Session=Depends(get_db),_:User=Depends(require_permission('inventory.read'))): return db.scalars(select(ProductionBatch).order_by(ProductionBatch.created_at.desc())).all()
@router.post('/production-batches',response_model=ProductionOut,status_code=201)
def create_batch(p:ProductionCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('inventory.*'))):
    recipe=load_recipe(db,p.recipe_id)
    if not recipe or recipe.status!='approved': fail(409,'Production requires an approved recipe')
    if not db.get(Location,p.location_id): fail(422,'Location not found')
    row=ProductionBatch(batch_number=next_document_number(db,'BATCH'),recipe_id=p.recipe_id,location_id=p.location_id,planned_quantity=p.planned_quantity,notes=p.notes,created_by_user_id=user.id); db.add(row); db.flush(); add_audit(db,actor_user_id=user.id,action='production.planned',entity_type='production_batch',entity_id=row.id); db.commit(); db.refresh(row); return row
@router.post('/production-batches/{batch_id}/complete',response_model=ProductionOut)
def complete_batch(batch_id:str,p:ProductionComplete,db:Session=Depends(get_db),user:User=Depends(require_permission('inventory.*'))):
    batch=db.scalar(select(ProductionBatch).where(ProductionBatch.id==batch_id).with_for_update())
    if not batch: fail(404,'Production batch not found')
    if batch.status!='planned': fail(409,'Only planned batches can be completed')
    recipe=load_recipe(db,batch.recipe_id); entries,total=recipe_entries(db,recipe,batch.location_id,p.actual_quantity)
    try:
        doc=post_document(db,kind='production',actor_id=user.id,entries=entries,reference=batch.batch_number,notes=batch.notes,commit=False)
        batch.actual_quantity=p.actual_quantity; batch.status='completed'; batch.completed_by_user_id=user.id; batch.completed_at=now(); batch.stock_document_id=doc.id
        add_audit(db,actor_user_id=user.id,action='production.completed',entity_type='production_batch',entity_id=batch.id,details={'actual_quantity':str(p.actual_quantity),'total_cost':str(total)})
        enqueue_event(db,destination_system='accounting',event_type='inventory.production.completed',aggregate_type='production_batch',aggregate_id=batch.id,idempotency_key=f'production-completed:{batch.id}',payload={'batch_id':batch.id,'batch_number':batch.batch_number,'output_item_id':recipe.output_item_id,'actual_quantity':str(p.actual_quantity),'total_cost':str(total)})
        db.commit(); db.refresh(batch); return batch
    except (InventoryError,IntegrityError) as exc: db.rollback(); fail(409,str(exc))

@router.get('/pos-mappings',response_model=list[PosMappingOut])
def mappings(db:Session=Depends(get_db),_:User=Depends(require_permission('integrations.read'))): return db.scalars(select(PosProductMapping).order_by(PosProductMapping.pos_system,PosProductMapping.external_product_id)).all()
@router.post('/pos-mappings',response_model=PosMappingOut,status_code=201)
def create_mapping(p:PosMappingCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('integrations.*'))):
    recipe=load_recipe(db,p.recipe_id)
    if not recipe or recipe.status!='approved' or not db.get(Location,p.location_id): fail(422,'Approved recipe or location not found')
    row=PosProductMapping(**p.model_dump()); db.add(row)
    try: db.flush(); add_audit(db,actor_user_id=user.id,action='pos.mapping_created',entity_type='pos_product_mapping',entity_id=row.id); db.commit(); db.refresh(row); return row
    except IntegrityError: db.rollback(); fail(409,'POS product is already mapped')
@router.post('/integrations/pos/events',response_model=PosSaleEventOut,status_code=201)
def process_pos_event(p:PosSaleEventIn,db:Session=Depends(get_db),user:User=Depends(require_permission('integrations.*'))):
    existing=db.scalar(select(PosSaleEvent).where(PosSaleEvent.external_event_id==p.external_event_id))
    if existing: return existing
    original=None
    if p.event_type!='sale_completed':
        original=db.scalar(select(PosSaleEvent).where(PosSaleEvent.external_sale_id==p.external_sale_id,PosSaleEvent.event_type=='sale_completed',PosSaleEvent.status=='processed'))
        if not original or not original.stock_document_id: fail(409,'Original completed sale was not found')
        prior=db.scalar(select(PosSaleEvent).where(PosSaleEvent.external_sale_id==p.external_sale_id,PosSaleEvent.event_type.in_(['sale_voided','sale_refunded']),PosSaleEvent.status=='processed'))
        if prior: fail(409,'Sale has already been reversed')
    try:
        if p.event_type=='sale_completed':
            entries=[]; accounting_lines=[]
            for sale_line in p.lines:
                mapping=db.scalar(select(PosProductMapping).where(PosProductMapping.pos_system==p.pos_system,PosProductMapping.external_product_id==sale_line.external_product_id,PosProductMapping.is_active==True))
                if not mapping: fail(422,f'POS product {sale_line.external_product_id} is not mapped')
                recipe=load_recipe(db,mapping.recipe_id); line_entries,cost=recipe_entries(db,recipe,mapping.location_id,sale_line.quantity,consume_only=True); entries.extend(line_entries); accounting_lines.append({'external_product_id':sale_line.external_product_id,'quantity':str(sale_line.quantity),'cost':str(cost)})
            doc=post_document(db,kind='pos_sale_consumption',actor_id=user.id,entries=entries,reference=p.external_sale_id,idempotency_key=f'pos:{p.external_event_id}',commit=False)
            row=PosSaleEvent(external_event_id=p.external_event_id,event_type=p.event_type,external_sale_id=p.external_sale_id,pos_system=p.pos_system,payload=p.model_dump(mode='json'),stock_document_id=doc.id)
            db.add(row); db.flush(); enqueue_event(db,destination_system='accounting',event_type='inventory.pos_sale_consumed',aggregate_type='pos_sale_event',aggregate_id=row.id,idempotency_key=f'accounting-pos:{p.external_event_id}',payload={'sale_id':p.external_sale_id,'stock_document_id':doc.id,'lines':accounting_lines})
        else:
            original_doc=db.scalar(select(StockDocument).where(StockDocument.id==original.stock_document_id).options(selectinload(StockDocument.movements)))
            entries=[{'item_id':m.item_id,'location_id':m.location_id,'quantity':-Decimal(m.quantity),'unit_cost':Decimal(m.unit_cost),'reason':p.event_type} for m in original_doc.movements]
            doc=post_document(db,kind='pos_sale_reversal',actor_id=user.id,entries=entries,reference=p.external_sale_id,idempotency_key=f'pos:{p.external_event_id}',commit=False)
            row=PosSaleEvent(external_event_id=p.external_event_id,event_type=p.event_type,external_sale_id=p.external_sale_id,pos_system=p.pos_system,payload=p.model_dump(mode='json'),stock_document_id=doc.id,reversal_of_event_id=original.id)
            db.add(row); db.flush(); enqueue_event(db,destination_system='accounting',event_type='inventory.pos_sale_reversed',aggregate_type='pos_sale_event',aggregate_id=row.id,idempotency_key=f'accounting-pos:{p.external_event_id}',payload={'sale_id':p.external_sale_id,'event_type':p.event_type,'stock_document_id':doc.id})
        add_audit(db,actor_user_id=user.id,action=f'pos.{p.event_type}',entity_type='pos_sale_event',entity_id=row.id,details={'external_sale_id':p.external_sale_id}); db.commit(); db.refresh(row); return row
    except (InventoryError,IntegrityError): db.rollback(); raise

@router.get('/integrations/reconciliation',response_model=ReconciliationOut)
def reconciliation(db:Session=Depends(get_db),_:User=Depends(require_permission('integrations.read'))):
    counts=dict(db.execute(select(IntegrationEvent.status,func.count()).group_by(IntegrationEvent.status)).all()); latest=db.scalar(select(func.max(PosSaleEvent.processed_at))); unprocessed=db.scalar(select(func.count()).select_from(PosSaleEvent).where(PosSaleEvent.status!='processed')) or 0
    return ReconciliationOut(pending_events=counts.get('pending',0)+counts.get('processing',0),failed_events=counts.get('failed',0),dead_letter_events=counts.get('dead_letter',0),unprocessed_pos_events=unprocessed,latest_pos_event_at=latest)
