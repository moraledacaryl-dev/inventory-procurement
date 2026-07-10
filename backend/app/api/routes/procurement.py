from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from app.api.deps import require_permission
from app.db.session import get_db
from app.models.user import User
from app.models.inventory import Item, Location, StockBalance, StockDocument
from app.models.procurement import Supplier, SupplierItem, PurchaseRequisition, PurchaseRequisitionLine, SupplierQuotation, SupplierQuotationLine, PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine, PurchaseReturn
from app.schemas.procurement import *
from app.services.controls import add_audit, add_notification, enqueue_event, next_document_number
from app.services.inventory import InventoryError, post_document

router=APIRouter(tags=['procurement'])
def now(): return datetime.now(timezone.utc)
def fail(code:int,message:str): raise HTTPException(code,message)
def save(db,row):
    db.add(row)
    try: db.commit(); db.refresh(row); return row
    except IntegrityError: db.rollback(); fail(409,'Duplicate or invalid record')
def load_pr(db,id): return db.scalar(select(PurchaseRequisition).where(PurchaseRequisition.id==id).options(selectinload(PurchaseRequisition.lines)))
def load_quote(db,id): return db.scalar(select(SupplierQuotation).where(SupplierQuotation.id==id).options(selectinload(SupplierQuotation.lines)))
def load_po(db,id,lock:bool=False):
    stmt=select(PurchaseOrder).where(PurchaseOrder.id==id).options(selectinload(PurchaseOrder.lines))
    if lock: stmt=stmt.with_for_update()
    return db.scalar(stmt)
def unique_items(lines):
    ids=[x.item_id for x in lines]
    if len(ids)!=len(set(ids)): fail(422,'Duplicate item lines are not allowed')

def reorder_rows(db:Session,location_id:str|None=None)->list[ReorderSuggestion]:
    if location_id and not db.get(Location,location_id): fail(404,'Location not found')
    items=db.scalars(select(Item).where(Item.is_active==True,Item.track_stock==True,Item.minimum_stock>0).order_by(Item.sku)).all()
    balances=db.scalars(select(StockBalance)).all()
    current:dict[str,Decimal]={}
    for balance in balances:
        if location_id and balance.location_id!=location_id: continue
        current[balance.item_id]=current.get(balance.item_id,Decimal('0'))+Decimal(balance.quantity)
    po_stmt=select(PurchaseOrder).where(PurchaseOrder.status.in_(['approved','partially_received'])).options(selectinload(PurchaseOrder.lines))
    if location_id: po_stmt=po_stmt.where(PurchaseOrder.delivery_location_id==location_id)
    on_order:dict[str,Decimal]={}
    for po in db.scalars(po_stmt).unique().all():
        for line in po.lines:
            outstanding=max(Decimal('0'),Decimal(line.ordered_quantity)-Decimal(line.received_quantity))
            on_order[line.item_id]=on_order.get(line.item_id,Decimal('0'))+outstanding
    preferred={}
    for link in db.scalars(select(SupplierItem).where(SupplierItem.is_preferred==True)).all(): preferred.setdefault(link.item_id,link)
    suppliers={x.id:x for x in db.scalars(select(Supplier)).all()}
    location=db.get(Location,location_id) if location_id else None
    result=[]
    for item in items:
        qty=current.get(item.id,Decimal('0')); incoming=on_order.get(item.id,Decimal('0'))
        suggested=max(Decimal('0'),Decimal(item.minimum_stock)-qty-incoming)
        if suggested<=0: continue
        link=preferred.get(item.id); supplier=suppliers.get(link.supplier_id) if link else None
        if link and suggested<Decimal(link.minimum_order_quantity): suggested=Decimal(link.minimum_order_quantity)
        result.append(ReorderSuggestion(item_id=item.id,sku=item.sku,item_name=item.name,location_id=location_id,location_name=location.name if location else None,current_quantity=qty,minimum_stock=Decimal(item.minimum_stock),on_order_quantity=incoming,suggested_quantity=suggested,standard_cost=Decimal(item.standard_cost),preferred_supplier_id=link.supplier_id if link else None,preferred_supplier_name=supplier.name if supplier else None,lead_time_days=link.lead_time_days if link else None))
    return result

@router.get('/suppliers',response_model=list[SupplierOut])
def suppliers(db:Session=Depends(get_db),_:User=Depends(require_permission('suppliers.read'))): return db.scalars(select(Supplier).order_by(Supplier.code)).all()
@router.post('/suppliers',response_model=SupplierOut,status_code=201)
def create_supplier(p:SupplierCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('suppliers.*'))):
    row=Supplier(**{**p.model_dump(),'code':p.code.upper().strip(),'name':p.name.strip()}); db.add(row); db.flush(); add_audit(db,actor_user_id=user.id,action='supplier.created',entity_type='supplier',entity_id=row.id,details={'code':row.code}); db.commit(); db.refresh(row); return row
@router.get('/suppliers/{supplier_id}/items',response_model=list[SupplierItemOut])
def supplier_items(supplier_id:str,db:Session=Depends(get_db),_:User=Depends(require_permission('suppliers.read'))): return db.scalars(select(SupplierItem).where(SupplierItem.supplier_id==supplier_id)).all()
@router.post('/suppliers/{supplier_id}/items',response_model=SupplierItemOut,status_code=201)
def add_supplier_item(supplier_id:str,p:SupplierItemCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('suppliers.*'))):
    if not db.get(Supplier,supplier_id) or not db.get(Item,p.item_id): fail(422,'Supplier or item not found')
    if p.is_preferred:
        for old in db.scalars(select(SupplierItem).where(SupplierItem.item_id==p.item_id,SupplierItem.is_preferred==True)).all(): old.is_preferred=False
    row=SupplierItem(supplier_id=supplier_id,**p.model_dump()); db.add(row); db.flush(); add_audit(db,actor_user_id=user.id,action='supplier.item_linked',entity_type='supplier_item',entity_id=row.id,details={'supplier_id':supplier_id,'item_id':p.item_id,'preferred':p.is_preferred}); db.commit(); db.refresh(row); return row

@router.get('/supplier-performance',response_model=list[SupplierPerformance])
def supplier_performance(db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))):
    suppliers=db.scalars(select(Supplier).order_by(Supplier.code)).all(); result=[]
    pos=db.scalars(select(PurchaseOrder).options(selectinload(PurchaseOrder.lines))).unique().all()
    receipts=db.scalars(select(GoodsReceipt).options(selectinload(GoodsReceipt.lines))).unique().all()
    receipts_by_po={}
    for receipt in receipts: receipts_by_po.setdefault(receipt.purchase_order_id,[]).append(receipt)
    for supplier in suppliers:
        supplier_pos=[po for po in pos if po.supplier_id==supplier.id]; ordered=received=accepted=rejected=Decimal('0'); on_time=0; completed=0; variances=[]
        for po in supplier_pos:
            ordered+=sum((Decimal(line.ordered_quantity)*Decimal(line.unit_price) for line in po.lines),Decimal('0'))
            po_receipts=receipts_by_po.get(po.id,[])
            if po.status=='received': completed+=1
            if po_receipts and po.expected_delivery_date:
                first=min(x.received_at.date() for x in po_receipts); variance=(first-po.expected_delivery_date).days; variances.append(Decimal(variance)); on_time+=variance<=0
            for receipt in po_receipts:
                for line in receipt.lines:
                    received+=Decimal(line.received_quantity)*Decimal(line.unit_cost); accepted+=Decimal(line.accepted_quantity)*Decimal(line.unit_cost); rejected+=Decimal(line.rejected_quantity)*Decimal(line.unit_cost)
        acceptance=(accepted/received*100).quantize(Decimal('0.01')) if received else Decimal('0')
        on_time_rate=(Decimal(on_time)/Decimal(len(variances))*100).quantize(Decimal('0.01')) if variances else Decimal('0')
        average=(sum(variances,Decimal('0'))/Decimal(len(variances))).quantize(Decimal('0.01')) if variances else Decimal('0')
        result.append(SupplierPerformance(supplier_id=supplier.id,supplier_code=supplier.code,supplier_name=supplier.name,purchase_orders=len(supplier_pos),completed_orders=completed,ordered_value=ordered,received_value=received,accepted_value=accepted,rejected_value=rejected,acceptance_rate=acceptance,on_time_rate=on_time_rate,average_delivery_variance_days=average))
    return result

@router.get('/reorder-suggestions',response_model=list[ReorderSuggestion])
def reorder_suggestions(location_id:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('procurement.read'))): return reorder_rows(db,location_id)
@router.post('/reorder-suggestions/requisition',response_model=PROut,status_code=201)
def create_reorder_requisition(p:ReorderRequisitionCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('procurement.*'))):
    suggestions=reorder_rows(db,p.location_id)
    if p.item_ids is not None: suggestions=[x for x in suggestions if x.item_id in set(p.item_ids)]
    if not suggestions: fail(409,'No reorder quantities are currently required')
    row=PurchaseRequisition(requisition_number=next_document_number(db,'PR'),department=p.department,needed_by=p.needed_by,justification=p.justification,status='submitted',requested_by_user_id=user.id)
    row.lines=[PurchaseRequisitionLine(item_id=x.item_id,quantity=x.suggested_quantity,estimated_unit_cost=x.standard_cost,notes=f'Auto-reorder; stock {x.current_quantity}, minimum {x.minimum_stock}, on order {x.on_order_quantity}') for x in suggestions]
    db.add(row); db.flush(); add_audit(db,actor_user_id=user.id,action='requisition.auto_created',entity_type='purchase_requisition',entity_id=row.id,details={'line_count':len(row.lines),'location_id':p.location_id}); add_notification(db,title='Reorder requisition submitted',message=f'{row.requisition_number} was generated with {len(row.lines)} low-stock items.',severity='info'); db.commit(); return load_pr(db,row.id)

@router.get('/requisitions',response_model=list[PROut])
def requisitions(status:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('procurement.read'))):
    stmt=select(PurchaseRequisition).options(selectinload(PurchaseRequisition.lines)).order_by(PurchaseRequisition.created_at.desc())
    if status: stmt=stmt.where(PurchaseRequisition.status==status)
    return db.scalars(stmt).unique().all()
@router.post('/requisitions',response_model=PROut,status_code=201)
def create_requisition(p:PRCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('procurement.*'))):
    unique_items(p.lines)
    for line in p.lines:
        if not db.get(Item,line.item_id): fail(422,'Item not found')
    row=PurchaseRequisition(requisition_number=next_document_number(db,'PR'),department=p.department,needed_by=p.needed_by,justification=p.justification,status='submitted',requested_by_user_id=user.id)
    row.lines=[PurchaseRequisitionLine(**x.model_dump()) for x in p.lines]; db.add(row); db.flush(); add_audit(db,actor_user_id=user.id,action='requisition.submitted',entity_type='purchase_requisition',entity_id=row.id,details={'line_count':len(row.lines)}); db.commit(); return load_pr(db,row.id)
@router.post('/requisitions/{requisition_id}/approve',response_model=PROut)
def approve_requisition(requisition_id:str,db:Session=Depends(get_db),user:User=Depends(require_permission('procurement.*'))):
    row=load_pr(db,requisition_id)
    if not row: fail(404,'Requisition not found')
    if row.status!='submitted': fail(409,'Only submitted requisitions can be approved')
    if row.requested_by_user_id==user.id: fail(409,'Requester cannot approve their own requisition')
    row.status='approved'; row.approved_by_user_id=user.id; row.approved_at=now(); add_audit(db,actor_user_id=user.id,action='requisition.approved',entity_type='purchase_requisition',entity_id=row.id); enqueue_event(db,destination_system='command-center',event_type='procurement.requisition.approved',aggregate_type='purchase_requisition',aggregate_id=row.id,idempotency_key=f'requisition-approved:{row.id}',payload={'requisition_id':row.id,'requisition_number':row.requisition_number}); db.commit(); return load_pr(db,row.id)
@router.post('/requisitions/{requisition_id}/reject',response_model=PROut)
def reject_requisition(requisition_id:str,db:Session=Depends(get_db),user:User=Depends(require_permission('procurement.*'))):
    row=load_pr(db,requisition_id)
    if not row: fail(404,'Requisition not found')
    if row.status not in {'submitted','approved'}: fail(409,'Requisition cannot be rejected')
    row.status='rejected'; add_audit(db,actor_user_id=user.id,action='requisition.rejected',entity_type='purchase_requisition',entity_id=row.id); db.commit(); return load_pr(db,row.id)

@router.get('/quotations',response_model=list[QuoteOut])
def quotations(requisition_id:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('procurement.read'))):
    stmt=select(SupplierQuotation).options(selectinload(SupplierQuotation.lines)).order_by(SupplierQuotation.created_at.desc())
    if requisition_id: stmt=stmt.where(SupplierQuotation.requisition_id==requisition_id)
    return db.scalars(stmt).unique().all()
@router.post('/quotations',response_model=QuoteOut,status_code=201)
def create_quotation(p:QuoteCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('procurement.*'))):
    unique_items(p.lines); req=load_pr(db,p.requisition_id)
    if not req or req.status!='approved': fail(409,'Quotation requires an approved requisition')
    if not db.get(Supplier,p.supplier_id): fail(422,'Supplier not found')
    allowed={x.item_id:Decimal(x.quantity) for x in req.lines}
    if any(x.item_id not in allowed or Decimal(x.quantity)>allowed[x.item_id] for x in p.lines): fail(422,'Quotation item or quantity exceeds requisition')
    row=SupplierQuotation(quotation_number=next_document_number(db,'RFQ'),requisition_id=p.requisition_id,supplier_id=p.supplier_id,valid_until=p.valid_until,delivery_days=p.delivery_days,payment_terms_days=p.payment_terms_days,notes=p.notes)
    row.lines=[SupplierQuotationLine(**x.model_dump()) for x in p.lines]; db.add(row); db.flush(); add_audit(db,actor_user_id=user.id,action='quotation.recorded',entity_type='supplier_quotation',entity_id=row.id,details={'supplier_id':p.supplier_id}); db.commit(); return load_quote(db,row.id)
@router.get('/requisitions/{requisition_id}/quotation-comparison',response_model=list[QuoteComparison])
def compare_quotes(requisition_id:str,db:Session=Depends(get_db),_:User=Depends(require_permission('procurement.read'))):
    quotes=db.scalars(select(SupplierQuotation).where(SupplierQuotation.requisition_id==requisition_id).options(selectinload(SupplierQuotation.lines))).unique().all()
    result=[QuoteComparison(quotation_id=q.id,quotation_number=q.quotation_number,supplier_id=q.supplier_id,total=sum((Decimal(x.quantity)*Decimal(x.unit_price) for x in q.lines),Decimal('0')),delivery_days=q.delivery_days,payment_terms_days=q.payment_terms_days,status=q.status) for q in quotes]
    return sorted(result,key=lambda x:(x.total,x.delivery_days))

@router.get('/purchase-orders',response_model=list[POOut])
def purchase_orders(status:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('procurement.read'))):
    stmt=select(PurchaseOrder).options(selectinload(PurchaseOrder.lines)).order_by(PurchaseOrder.created_at.desc())
    if status: stmt=stmt.where(PurchaseOrder.status==status)
    return db.scalars(stmt).unique().all()
@router.post('/purchase-orders',response_model=POOut,status_code=201)
def create_po(p:POCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('procurement.*'))):
    unique_items(p.lines)
    if not db.get(Supplier,p.supplier_id) or not db.get(Location,p.delivery_location_id): fail(422,'Supplier or delivery location not found')
    req=None
    if p.requisition_id:
        req=load_pr(db,p.requisition_id)
        if not req or req.status!='approved': fail(409,'Purchase order requires an approved requisition')
        req_qty={x.item_id:Decimal(x.quantity) for x in req.lines}
        if any(x.item_id not in req_qty or Decimal(x.ordered_quantity)>req_qty[x.item_id] for x in p.lines): fail(422,'Purchase order item or quantity exceeds requisition')
    if p.quotation_id:
        quote=load_quote(db,p.quotation_id)
        if not quote or quote.supplier_id!=p.supplier_id or (p.requisition_id and quote.requisition_id!=p.requisition_id): fail(409,'Quotation does not match supplier or requisition')
        quote_lines={x.item_id:(Decimal(x.quantity),Decimal(x.unit_price)) for x in quote.lines}
        if any(x.item_id not in quote_lines or Decimal(x.ordered_quantity)>quote_lines[x.item_id][0] or Decimal(x.unit_price)>quote_lines[x.item_id][1] for x in p.lines): fail(422,'Purchase order exceeds selected quotation')
    row=PurchaseOrder(purchase_order_number=next_document_number(db,'PO'),supplier_id=p.supplier_id,requisition_id=p.requisition_id,quotation_id=p.quotation_id,delivery_location_id=p.delivery_location_id,expected_delivery_date=p.expected_delivery_date,notes=p.notes,created_by_user_id=user.id,status='draft')
    row.lines=[PurchaseOrderLine(**x.model_dump()) for x in p.lines]; db.add(row); db.flush(); add_audit(db,actor_user_id=user.id,action='purchase_order.created',entity_type='purchase_order',entity_id=row.id,details={'supplier_id':p.supplier_id,'line_count':len(row.lines)}); db.commit(); return load_po(db,row.id)
@router.post('/purchase-orders/{po_id}/approve',response_model=POOut)
def approve_po(po_id:str,db:Session=Depends(get_db),user:User=Depends(require_permission('procurement.*'))):
    po=load_po(db,po_id)
    if not po: fail(404,'Purchase order not found')
    if po.status!='draft': fail(409,'Only draft purchase orders can be approved')
    if po.created_by_user_id==user.id: fail(409,'Creator cannot approve their own purchase order')
    po.status='approved'; po.approved_by_user_id=user.id; po.approved_at=now(); total=sum((Decimal(x.ordered_quantity)*Decimal(x.unit_price) for x in po.lines),Decimal('0')); add_audit(db,actor_user_id=user.id,action='purchase_order.approved',entity_type='purchase_order',entity_id=po.id,details={'total':str(total)}); enqueue_event(db,destination_system='accounting',event_type='procurement.purchase_order.approved',aggregate_type='purchase_order',aggregate_id=po.id,idempotency_key=f'po-approved:{po.id}',payload={'purchase_order_id':po.id,'purchase_order_number':po.purchase_order_number,'supplier_id':po.supplier_id,'total':str(total)}); db.commit(); return load_po(db,po.id)

@router.post('/purchase-orders/{po_id}/receipts',response_model=GoodsReceiptOut,status_code=201)
def receive_po(po_id:str,p:GoodsReceiptCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('receiving.*'))):
    if p.idempotency_key:
        existing_doc=db.scalar(select(StockDocument).where(StockDocument.idempotency_key==p.idempotency_key))
        if existing_doc:
            existing=db.scalar(select(GoodsReceipt).where(GoodsReceipt.stock_document_id==existing_doc.id).options(selectinload(GoodsReceipt.lines)))
            if existing: return existing
            fail(409,'Idempotency key is already used by another stock operation')
    po=load_po(db,po_id,lock=True)
    if not po: fail(404,'Purchase order not found')
    if po.status not in {'approved','partially_received'}: fail(409,'Purchase order is not receivable')
    ids=[x.purchase_order_line_id for x in p.lines]
    if len(ids)!=len(set(ids)): fail(422,'Duplicate purchase order receipt lines are not allowed')
    po_lines={x.id:x for x in po.lines}; entries=[]
    for x in p.lines:
        line=po_lines.get(x.purchase_order_line_id)
        if not line: fail(422,'Purchase order line not found')
        outstanding=Decimal(line.ordered_quantity)-Decimal(line.received_quantity)
        if x.received_quantity>outstanding: fail(409,'Received quantity exceeds outstanding quantity')
        if x.accepted_quantity: entries.append({'item_id':line.item_id,'location_id':po.delivery_location_id,'quantity':x.accepted_quantity,'unit_cost':line.unit_price,'reason':'purchase order receipt'})
    try:
        doc=post_document(db,kind='po_receipt',actor_id=user.id,entries=entries,reference=po.purchase_order_number,notes=p.notes,idempotency_key=p.idempotency_key,commit=False,allow_empty=True)
        receipt=GoodsReceipt(goods_receipt_number=next_document_number(db,'GRN'),purchase_order_id=po.id,stock_document_id=doc.id,delivery_reference=p.delivery_reference,received_by_user_id=user.id,notes=p.notes)
        for x in p.lines:
            line=po_lines[x.purchase_order_line_id]; line.received_quantity=Decimal(line.received_quantity)+x.received_quantity
            receipt.lines.append(GoodsReceiptLine(purchase_order_line_id=line.id,item_id=line.item_id,received_quantity=x.received_quantity,accepted_quantity=x.accepted_quantity,rejected_quantity=x.rejected_quantity,unit_cost=line.unit_price))
        po.status='received' if all(Decimal(x.received_quantity)>=Decimal(x.ordered_quantity) for x in po.lines) else 'partially_received'
        db.add(receipt); db.flush(); add_audit(db,actor_user_id=user.id,action='goods_receipt.posted',entity_type='goods_receipt',entity_id=receipt.id,details={'purchase_order_id':po.id,'line_count':len(receipt.lines)}); enqueue_event(db,destination_system='accounting',event_type='procurement.goods_received',aggregate_type='goods_receipt',aggregate_id=receipt.id,idempotency_key=f'goods-received:{receipt.id}',payload={'goods_receipt_id':receipt.id,'goods_receipt_number':receipt.goods_receipt_number,'purchase_order_id':po.id,'supplier_id':po.supplier_id,'lines':[{'item_id':x.item_id,'accepted_quantity':str(x.accepted_quantity),'rejected_quantity':str(x.rejected_quantity),'unit_cost':str(x.unit_cost)} for x in receipt.lines]}); db.commit(); db.refresh(receipt); return receipt
    except (InventoryError,IntegrityError) as exc:
        db.rollback(); fail(409,str(exc) if isinstance(exc,InventoryError) else 'Goods receipt could not be posted')
@router.get('/goods-receipts',response_model=list[GoodsReceiptOut])
def goods_receipts(db:Session=Depends(get_db),_:User=Depends(require_permission('receiving.read'))): return db.scalars(select(GoodsReceipt).options(selectinload(GoodsReceipt.lines)).order_by(GoodsReceipt.received_at.desc())).unique().all()

@router.post('/purchase-orders/{po_id}/returns',response_model=ReturnOut,status_code=201)
def create_return(po_id:str,p:ReturnCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('receiving.*'))):
    if p.idempotency_key:
        existing_doc=db.scalar(select(StockDocument).where(StockDocument.idempotency_key==p.idempotency_key))
        if existing_doc:
            existing=db.scalar(select(PurchaseReturn).where(PurchaseReturn.stock_document_id==existing_doc.id))
            if existing: return existing
            fail(409,'Idempotency key is already used by another stock operation')
    po=load_po(db,po_id,lock=True)
    if not po: fail(404,'Purchase order not found')
    ids=[x.purchase_order_line_id for x in p.lines]
    if len(ids)!=len(set(ids)): fail(422,'Duplicate purchase return lines are not allowed')
    lines={x.id:x for x in po.lines}; entries=[]
    for x in p.lines:
        line=lines.get(x.purchase_order_line_id)
        if not line: fail(422,'Purchase order line not found')
        returnable=Decimal(line.received_quantity)-Decimal(line.returned_quantity)
        if x.quantity>returnable: fail(409,'Return quantity exceeds received quantity')
        entries.append({'item_id':line.item_id,'location_id':po.delivery_location_id,'quantity':-x.quantity,'unit_cost':line.unit_price,'reason':'purchase return'})
    try:
        doc=post_document(db,kind='purchase_return',actor_id=user.id,entries=entries,reference=po.purchase_order_number,notes=p.reason,idempotency_key=p.idempotency_key,commit=False)
        for x in p.lines: lines[x.purchase_order_line_id].returned_quantity=Decimal(lines[x.purchase_order_line_id].returned_quantity)+x.quantity
        row=PurchaseReturn(return_number=next_document_number(db,'PRTN'),purchase_order_id=po.id,stock_document_id=doc.id,reason=p.reason,created_by_user_id=user.id); db.add(row); db.flush(); add_audit(db,actor_user_id=user.id,action='purchase_return.posted',entity_type='purchase_return',entity_id=row.id,details={'purchase_order_id':po.id}); enqueue_event(db,destination_system='accounting',event_type='procurement.purchase_return.posted',aggregate_type='purchase_return',aggregate_id=row.id,idempotency_key=f'purchase-return:{row.id}',payload={'purchase_return_id':row.id,'return_number':row.return_number,'purchase_order_id':po.id,'reason':row.reason}); db.commit(); db.refresh(row); return row
    except (InventoryError,IntegrityError) as exc:
        db.rollback(); fail(409,str(exc) if isinstance(exc,InventoryError) else 'Purchase return could not be posted')
