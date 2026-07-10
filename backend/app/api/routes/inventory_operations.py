from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from app.api.deps import require_permission
from app.db.session import get_db
from app.models.user import User
from app.models.inventory import Item, Location, StockBalance, StockMovement, StockDocument, UnitOfMeasure
from app.models.procurement import Supplier
from app.models.inventory_operations import ItemBarcode, UnitConversion, ItemLocationSetting, InventoryLot, LotBalance, StockReservation, TransferOrder, TransferOrderLine, CycleCountSchedule
from app.schemas.inventory_operations import *
from app.services.controls import add_audit, add_notification, next_document_number
from app.services.inventory import InventoryError, post_document

router=APIRouter(tags=['inventory-operations'])
def fail(code:int,message:str): raise HTTPException(code,message)
def now(): return datetime.now(timezone.utc)
def save(db,row):
    db.add(row)
    try: db.commit(); db.refresh(row); return row
    except IntegrityError: db.rollback(); fail(409,'Duplicate or invalid record')

def get_balance(db:Session,item_id:str,location_id:str)->Decimal:
    row=db.scalar(select(StockBalance).where(StockBalance.item_id==item_id,StockBalance.location_id==location_id))
    return Decimal(row.quantity) if row else Decimal('0')
def active_reserved(db:Session,item_id:str,location_id:str)->Decimal:
    current=now()
    rows=db.scalars(select(StockReservation).where(StockReservation.item_id==item_id,StockReservation.location_id==location_id,StockReservation.status=='active')).all()
    return sum((Decimal(x.quantity) for x in rows if x.expires_at is None or x.expires_at>current),Decimal('0'))
def lot_balance(db:Session,lot_id:str,location_id:str,lock:bool=False):
    stmt=select(LotBalance).where(LotBalance.lot_id==lot_id,LotBalance.location_id==location_id)
    if lock: stmt=stmt.with_for_update()
    row=db.scalar(stmt)
    if not row:
        row=LotBalance(lot_id=lot_id,location_id=location_id,quantity=0); db.add(row); db.flush()
    return row

@router.get('/items/barcode/{barcode}',response_model=dict)
def barcode_lookup(barcode:str,db:Session=Depends(get_db),_:User=Depends(require_permission('items.read'))):
    row=db.scalar(select(ItemBarcode).where(ItemBarcode.barcode==barcode))
    if not row: fail(404,'Barcode not found')
    item=db.get(Item,row.item_id)
    return {'item_id':item.id,'sku':item.sku,'name':item.name,'barcode':row.barcode,'barcode_type':row.barcode_type}
@router.get('/items/{item_id}/barcodes',response_model=list[BarcodeOut])
def list_barcodes(item_id:str,db:Session=Depends(get_db),_:User=Depends(require_permission('items.read'))): return db.scalars(select(ItemBarcode).where(ItemBarcode.item_id==item_id).order_by(ItemBarcode.is_primary.desc(),ItemBarcode.barcode)).all()
@router.post('/items/{item_id}/barcodes',response_model=BarcodeOut,status_code=201)
def add_barcode(item_id:str,p:BarcodeCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('items.*'))):
    if not db.get(Item,item_id): fail(404,'Item not found')
    if p.is_primary:
        for x in db.scalars(select(ItemBarcode).where(ItemBarcode.item_id==item_id,ItemBarcode.is_primary==True)).all(): x.is_primary=False
    row=ItemBarcode(item_id=item_id,**p.model_dump()); db.add(row); db.flush(); add_audit(db,actor_user_id=user.id,action='item.barcode_added',entity_type='item',entity_id=item_id,details={'barcode':p.barcode}); db.commit(); db.refresh(row); return row

@router.get('/items/{item_id}/conversions',response_model=list[ConversionOut])
def list_conversions(item_id:str,db:Session=Depends(get_db),_:User=Depends(require_permission('items.read'))): return db.scalars(select(UnitConversion).where(UnitConversion.item_id==item_id,UnitConversion.is_active==True)).all()
@router.post('/items/{item_id}/conversions',response_model=ConversionOut,status_code=201)
def add_conversion(item_id:str,p:ConversionCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('items.*'))):
    if not db.get(Item,item_id) or not db.get(UnitOfMeasure,p.from_unit_id) or not db.get(UnitOfMeasure,p.to_unit_id): fail(422,'Item or unit not found')
    if p.from_unit_id==p.to_unit_id: fail(422,'Conversion units must differ')
    row=UnitConversion(item_id=item_id,**p.model_dump()); db.add(row); db.flush(); add_audit(db,actor_user_id=user.id,action='item.conversion_added',entity_type='item',entity_id=item_id,details={'multiplier':str(p.multiplier)}); db.commit(); db.refresh(row); return row
@router.get('/items/{item_id}/convert')
def convert_quantity(item_id:str,from_unit_id:str,to_unit_id:str,quantity:Decimal=Query(gt=0),db:Session=Depends(get_db),_:User=Depends(require_permission('items.read'))):
    if from_unit_id==to_unit_id: return {'quantity':str(quantity),'converted_quantity':str(quantity)}
    row=db.scalar(select(UnitConversion).where(UnitConversion.item_id==item_id,UnitConversion.from_unit_id==from_unit_id,UnitConversion.to_unit_id==to_unit_id,UnitConversion.is_active==True))
    if row: result=quantity*Decimal(row.multiplier)
    else:
        reverse=db.scalar(select(UnitConversion).where(UnitConversion.item_id==item_id,UnitConversion.from_unit_id==to_unit_id,UnitConversion.to_unit_id==from_unit_id,UnitConversion.is_active==True))
        if not reverse: fail(404,'Conversion not configured')
        result=quantity/Decimal(reverse.multiplier)
    return {'quantity':str(quantity),'converted_quantity':str(result),'from_unit_id':from_unit_id,'to_unit_id':to_unit_id}

@router.get('/item-location-settings',response_model=list[LocationSettingOut])
def list_settings(item_id:str|None=None,location_id:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('inventory.read'))):
    stmt=select(ItemLocationSetting).where(ItemLocationSetting.is_active==True)
    if item_id: stmt=stmt.where(ItemLocationSetting.item_id==item_id)
    if location_id: stmt=stmt.where(ItemLocationSetting.location_id==location_id)
    return db.scalars(stmt).all()
@router.post('/item-location-settings',response_model=LocationSettingOut,status_code=201)
def create_setting(p:LocationSettingCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('inventory.*'))):
    if not db.get(Item,p.item_id) or not db.get(Location,p.location_id): fail(422,'Item or location not found')
    if p.preferred_supplier_id and not db.get(Supplier,p.preferred_supplier_id): fail(422,'Supplier not found')
    row=ItemLocationSetting(**p.model_dump()); db.add(row); db.flush(); add_audit(db,actor_user_id=user.id,action='inventory.location_setting_created',entity_type='item_location_setting',entity_id=row.id); db.commit(); db.refresh(row); return row

@router.get('/lots',response_model=list[LotOut])
def list_lots(item_id:str|None=None,status:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('inventory.read'))):
    stmt=select(InventoryLot).order_by(InventoryLot.expiry_date,InventoryLot.lot_number)
    if item_id: stmt=stmt.where(InventoryLot.item_id==item_id)
    if status: stmt=stmt.where(InventoryLot.status==status)
    return db.scalars(stmt).all()
@router.post('/lots',response_model=LotOut,status_code=201)
def create_lot(p:LotCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('inventory.*'))):
    if not db.get(Item,p.item_id): fail(422,'Item not found')
    if p.supplier_id and not db.get(Supplier,p.supplier_id): fail(422,'Supplier not found')
    if p.manufactured_date and p.expiry_date and p.expiry_date<p.manufactured_date: fail(422,'Expiry date cannot precede manufacture date')
    row=InventoryLot(**p.model_dump()); db.add(row); db.flush(); add_audit(db,actor_user_id=user.id,action='inventory.lot_created',entity_type='inventory_lot',entity_id=row.id,details={'lot_number':row.lot_number}); db.commit(); db.refresh(row); return row
@router.get('/lot-balances',response_model=list[LotBalanceOut])
def lot_balances(item_id:str|None=None,location_id:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('inventory.read'))):
    stmt=select(LotBalance,InventoryLot).join(InventoryLot,InventoryLot.id==LotBalance.lot_id).where(LotBalance.quantity!=0)
    if item_id: stmt=stmt.where(InventoryLot.item_id==item_id)
    if location_id: stmt=stmt.where(LotBalance.location_id==location_id)
    return [LotBalanceOut(lot_id=lot.id,item_id=lot.item_id,lot_number=lot.lot_number,location_id=balance.location_id,quantity=Decimal(balance.quantity),expiry_date=lot.expiry_date,status=lot.status) for balance,lot in db.execute(stmt).all()]
@router.post('/lot-transactions',response_model=dict,status_code=201)
def lot_transaction(p:LotTransactionCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('inventory.*'))):
    lot=db.get(InventoryLot,p.lot_id)
    if not lot or lot.status not in {'active','quarantine'}: fail(409,'Lot is not available for transactions')
    if not db.get(Location,p.location_id): fail(422,'Location not found')
    sign=Decimal('1') if p.transaction_type=='receipt' else Decimal('-1')
    balance=lot_balance(db,p.lot_id,p.location_id,lock=True)
    new_qty=Decimal(balance.quantity)+sign*p.quantity
    if new_qty<0: fail(409,'Insufficient lot quantity')
    reason=p.reason or p.transaction_type
    try:
        doc=post_document(db,kind=p.transaction_type,actor_id=user.id,entries=[{'item_id':lot.item_id,'location_id':p.location_id,'quantity':sign*p.quantity,'unit_cost':p.unit_cost,'reason':reason}],reference=lot.lot_number,idempotency_key=p.idempotency_key,commit=False)
        balance.quantity=new_qty
        if p.transaction_type in {'waste','damage'}: add_notification(db,title=f'{p.transaction_type.title()} recorded',message=f'{p.quantity} units from lot {lot.lot_number} were written off.',severity='warning')
        add_audit(db,actor_user_id=user.id,action=f'inventory.{p.transaction_type}',entity_type='inventory_lot',entity_id=lot.id,details={'quantity':str(p.quantity),'location_id':p.location_id,'document_id':doc.id})
        db.commit(); return {'document_id':doc.id,'document_number':doc.document_number,'lot_id':lot.id,'lot_quantity':str(balance.quantity)}
    except (InventoryError,IntegrityError) as exc:
        db.rollback(); fail(409,str(exc))

@router.get('/availability',response_model=list[AvailabilityOut])
def availability(item_id:str|None=None,location_id:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('inventory.read'))):
    stmt=select(StockBalance)
    if item_id: stmt=stmt.where(StockBalance.item_id==item_id)
    if location_id: stmt=stmt.where(StockBalance.location_id==location_id)
    rows=[]
    for balance in db.scalars(stmt).all():
        reserved=active_reserved(db,balance.item_id,balance.location_id); physical=Decimal(balance.quantity)
        rows.append(AvailabilityOut(item_id=balance.item_id,location_id=balance.location_id,physical_quantity=physical,reserved_quantity=reserved,available_quantity=physical-reserved))
    return rows
@router.post('/reservations',response_model=ReservationOut,status_code=201)
def create_reservation(p:ReservationCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('inventory.*'))):
    if not db.get(Item,p.item_id) or not db.get(Location,p.location_id): fail(422,'Item or location not found')
    available=get_balance(db,p.item_id,p.location_id)-active_reserved(db,p.item_id,p.location_id)
    if p.quantity>available: fail(409,'Insufficient available stock')
    row=StockReservation(reservation_number=next_document_number(db,'RSV'),created_by_user_id=user.id,**p.model_dump()); db.add(row); db.flush(); add_audit(db,actor_user_id=user.id,action='inventory.reserved',entity_type='stock_reservation',entity_id=row.id,details={'quantity':str(row.quantity)}); db.commit(); db.refresh(row); return row
@router.post('/reservations/{reservation_id}/release',response_model=ReservationOut)
def release_reservation(reservation_id:str,db:Session=Depends(get_db),user:User=Depends(require_permission('inventory.*'))):
    row=db.get(StockReservation,reservation_id)
    if not row: fail(404,'Reservation not found')
    if row.status!='active': fail(409,'Reservation is not active')
    row.status='released'; add_audit(db,actor_user_id=user.id,action='inventory.reservation_released',entity_type='stock_reservation',entity_id=row.id); db.commit(); db.refresh(row); return row

@router.get('/transfer-orders',response_model=list[TransferOrderOut])
def list_transfer_orders(status:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('inventory.read'))):
    stmt=select(TransferOrder).options(selectinload(TransferOrder.lines)).order_by(TransferOrder.created_at.desc())
    if status: stmt=stmt.where(TransferOrder.status==status)
    return db.scalars(stmt).unique().all()
@router.post('/transfer-orders',response_model=TransferOrderOut,status_code=201)
def create_transfer_order(p:TransferOrderCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('inventory.*'))):
    if p.source_location_id==p.destination_location_id: fail(422,'Locations must differ')
    if not db.get(Location,p.source_location_id) or not db.get(Location,p.destination_location_id): fail(422,'Location not found')
    ids=[x.item_id for x in p.lines]
    if len(ids)!=len(set(ids)): fail(422,'Duplicate item lines are not allowed')
    for line in p.lines:
        if not db.get(Item,line.item_id): fail(422,'Item not found')
        if line.quantity>get_balance(db,line.item_id,p.source_location_id)-active_reserved(db,line.item_id,p.source_location_id): fail(409,'Insufficient available stock')
    row=TransferOrder(transfer_number=next_document_number(db,'TO'),source_location_id=p.source_location_id,destination_location_id=p.destination_location_id,notes=p.notes,created_by_user_id=user.id)
    row.lines=[TransferOrderLine(item_id=x.item_id,quantity=x.quantity) for x in p.lines]; db.add(row); db.flush(); add_audit(db,actor_user_id=user.id,action='transfer_order.created',entity_type='transfer_order',entity_id=row.id); db.commit(); return db.scalar(select(TransferOrder).where(TransferOrder.id==row.id).options(selectinload(TransferOrder.lines)))
@router.post('/transfer-orders/{transfer_id}/dispatch',response_model=TransferOrderOut)
def dispatch_transfer(transfer_id:str,db:Session=Depends(get_db),user:User=Depends(require_permission('inventory.*'))):
    row=db.scalar(select(TransferOrder).where(TransferOrder.id==transfer_id).options(selectinload(TransferOrder.lines)).with_for_update())
    if not row: fail(404,'Transfer order not found')
    if row.status!='draft': fail(409,'Only draft transfers can be dispatched')
    for line in row.lines:
        if line.quantity>get_balance(db,line.item_id,row.source_location_id)-active_reserved(db,line.item_id,row.source_location_id): fail(409,'Insufficient available stock at dispatch')
    row.status='dispatched'; row.dispatched_by_user_id=user.id; row.dispatched_at=now(); add_audit(db,actor_user_id=user.id,action='transfer_order.dispatched',entity_type='transfer_order',entity_id=row.id); db.commit(); return row
@router.post('/transfer-orders/{transfer_id}/receive',response_model=TransferOrderOut)
def receive_transfer(transfer_id:str,db:Session=Depends(get_db),user:User=Depends(require_permission('inventory.*'))):
    row=db.scalar(select(TransferOrder).where(TransferOrder.id==transfer_id).options(selectinload(TransferOrder.lines)).with_for_update())
    if not row: fail(404,'Transfer order not found')
    if row.status!='dispatched': fail(409,'Only dispatched transfers can be received')
    entries=[]
    for line in row.lines:
        entries.extend([{'item_id':line.item_id,'location_id':row.source_location_id,'quantity':-Decimal(line.quantity),'unit_cost':0,'reason':'transfer out'},{'item_id':line.item_id,'location_id':row.destination_location_id,'quantity':Decimal(line.quantity),'unit_cost':0,'cost_from_location_id':row.source_location_id,'reason':'transfer in'}])
    try:
        doc=post_document(db,kind='transfer',actor_id=user.id,entries=entries,reference=row.transfer_number,commit=False)
        row.status='received'; row.received_by_user_id=user.id; row.received_at=now(); row.stock_document_id=doc.id; add_audit(db,actor_user_id=user.id,action='transfer_order.received',entity_type='transfer_order',entity_id=row.id,details={'stock_document_id':doc.id}); db.commit(); return row
    except (InventoryError,IntegrityError) as exc:
        db.rollback(); fail(409,str(exc))

@router.get('/cycle-count-schedules',response_model=list[CycleScheduleOut])
def schedules(due_only:bool=False,db:Session=Depends(get_db),_:User=Depends(require_permission('counts.create'))):
    stmt=select(CycleCountSchedule).where(CycleCountSchedule.is_active==True).order_by(CycleCountSchedule.next_count_date)
    if due_only: stmt=stmt.where(CycleCountSchedule.next_count_date<=date.today())
    return db.scalars(stmt).all()
@router.post('/cycle-count-schedules',response_model=CycleScheduleOut,status_code=201)
def create_schedule(p:CycleScheduleCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('counts.create'))):
    if not db.get(Item,p.item_id) or not db.get(Location,p.location_id): fail(422,'Item or location not found')
    row=CycleCountSchedule(**p.model_dump()); db.add(row); db.flush(); add_audit(db,actor_user_id=user.id,action='count.schedule_created',entity_type='cycle_count_schedule',entity_id=row.id); db.commit(); db.refresh(row); return row

@router.get('/reports/valuation',response_model=list[ValuationRow])
def valuation(location_id:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))):
    stmt=select(StockBalance)
    if location_id: stmt=stmt.where(StockBalance.location_id==location_id)
    return [ValuationRow(item_id=x.item_id,location_id=x.location_id,quantity=Decimal(x.quantity),average_cost=Decimal(x.average_cost),inventory_value=Decimal(x.quantity)*Decimal(x.average_cost)) for x in db.scalars(stmt).all()]
@router.get('/reports/aging',response_model=list[AgingRow])
def aging(location_id:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))):
    balances=db.scalars(select(StockBalance).where(StockBalance.quantity!=0)).all(); result=[]; current=now()
    for balance in balances:
        if location_id and balance.location_id!=location_id: continue
        last=db.scalar(select(func.max(StockMovement.created_at)).where(StockMovement.item_id==balance.item_id,StockMovement.location_id==balance.location_id))
        days=(current-last).days if last else None
        classification='active' if days is not None and days<=30 else 'slow' if days is not None and days<=90 else 'non_moving'
        result.append(AgingRow(item_id=balance.item_id,location_id=balance.location_id,last_movement_at=last,days_since_movement=days,quantity=Decimal(balance.quantity),classification=classification))
    return result
@router.get('/reports/expiry',response_model=list[ExpiryRow])
def expiry_report(days:int=Query(30,ge=0,le=3650),location_id:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))):
    today=date.today(); cutoff=today+timedelta(days=days)
    stmt=select(LotBalance,InventoryLot).join(InventoryLot,InventoryLot.id==LotBalance.lot_id).where(LotBalance.quantity>0,InventoryLot.expiry_date!=None,InventoryLot.expiry_date<=cutoff)
    if location_id: stmt=stmt.where(LotBalance.location_id==location_id)
    rows=[]
    for balance,lot in db.execute(stmt).all():
        remaining=(lot.expiry_date-today).days; status='expired' if remaining<0 else 'near_expiry'
        rows.append(ExpiryRow(lot_id=lot.id,item_id=lot.item_id,lot_number=lot.lot_number,location_id=balance.location_id,quantity=Decimal(balance.quantity),expiry_date=lot.expiry_date,days_to_expiry=remaining,status=status))
    return rows
@router.get('/reports/waste',response_model=list[WasteSummaryRow])
def waste_report(db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))):
    rows=db.execute(select(StockMovement.item_id,func.sum(-StockMovement.quantity),func.sum(-StockMovement.quantity*StockMovement.unit_cost)).where(StockMovement.reason.in_(['waste','damage'])).group_by(StockMovement.item_id)).all()
    return [WasteSummaryRow(item_id=item_id,quantity=Decimal(qty or 0),value=Decimal(value or 0)) for item_id,qty,value in rows]
