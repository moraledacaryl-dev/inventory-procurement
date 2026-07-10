from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from app.api.deps import require_permission
from app.db.session import get_db
from app.models.user import User
from app.models.inventory import Item, Location
from app.models.procurement import Supplier, SupplierItem, PurchaseRequisition, PurchaseRequisitionLine, SupplierQuotation, SupplierQuotationLine, PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine, PurchaseReturn
from app.schemas.procurement import *
from app.services.inventory import InventoryError, post_document

router=APIRouter(tags=['procurement'])
def now(): return datetime.now(timezone.utc)
def fail(code:int,message:str): raise HTTPException(code,message)
def save(db,row):
    db.add(row)
    try: db.commit(); db.refresh(row); return row
    except IntegrityError: db.rollback(); fail(409,'Duplicate or invalid record')
def numbered(prefix:str,count:int): return f'{prefix}-{count+1:06d}'

def load_pr(db,id): return db.scalar(select(PurchaseRequisition).where(PurchaseRequisition.id==id).options(selectinload(PurchaseRequisition.lines)))
def load_quote(db,id): return db.scalar(select(SupplierQuotation).where(SupplierQuotation.id==id).options(selectinload(SupplierQuotation.lines)))
def load_po(db,id): return db.scalar(select(PurchaseOrder).where(PurchaseOrder.id==id).options(selectinload(PurchaseOrder.lines)))

@router.get('/suppliers',response_model=list[SupplierOut])
def suppliers(db:Session=Depends(get_db),_:User=Depends(require_permission('suppliers.read'))): return db.scalars(select(Supplier).order_by(Supplier.code)).all()
@router.post('/suppliers',response_model=SupplierOut,status_code=201)
def create_supplier(p:SupplierCreate,db:Session=Depends(get_db),_:User=Depends(require_permission('suppliers.*'))): return save(db,Supplier(**{**p.model_dump(),'code':p.code.upper().strip(),'name':p.name.strip()}))
@router.get('/suppliers/{supplier_id}/items',response_model=list[SupplierItemOut])
def supplier_items(supplier_id:str,db:Session=Depends(get_db),_:User=Depends(require_permission('suppliers.read'))): return db.scalars(select(SupplierItem).where(SupplierItem.supplier_id==supplier_id)).all()
@router.post('/suppliers/{supplier_id}/items',response_model=SupplierItemOut,status_code=201)
def add_supplier_item(supplier_id:str,p:SupplierItemCreate,db:Session=Depends(get_db),_:User=Depends(require_permission('suppliers.*'))):
    if not db.get(Supplier,supplier_id) or not db.get(Item,p.item_id): fail(422,'Supplier or item not found')
    return save(db,SupplierItem(supplier_id=supplier_id,**p.model_dump()))

@router.get('/requisitions',response_model=list[PROut])
def requisitions(status:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('procurement.read'))):
    stmt=select(PurchaseRequisition).options(selectinload(PurchaseRequisition.lines)).order_by(PurchaseRequisition.created_at.desc())
    if status: stmt=stmt.where(PurchaseRequisition.status==status)
    return db.scalars(stmt).unique().all()
@router.post('/requisitions',response_model=PROut,status_code=201)
def create_requisition(p:PRCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('procurement.*'))):
    for line in p.lines:
        if not db.get(Item,line.item_id): fail(422,'Item not found')
    row=PurchaseRequisition(requisition_number=numbered('PR',db.query(PurchaseRequisition).count()),department=p.department,needed_by=p.needed_by,justification=p.justification,status='submitted',requested_by_user_id=user.id)
    row.lines=[PurchaseRequisitionLine(**x.model_dump()) for x in p.lines]
    return save(db,row)
@router.post('/requisitions/{requisition_id}/approve',response_model=PROut)
def approve_requisition(requisition_id:str,db:Session=Depends(get_db),user:User=Depends(require_permission('procurement.*'))):
    row=load_pr(db,requisition_id)
    if not row: fail(404,'Requisition not found')
    if row.status!='submitted': fail(409,'Only submitted requisitions can be approved')
    row.status='approved'; row.approved_by_user_id=user.id; row.approved_at=now(); db.commit(); db.refresh(row); return row
@router.post('/requisitions/{requisition_id}/reject',response_model=PROut)
def reject_requisition(requisition_id:str,db:Session=Depends(get_db),_:User=Depends(require_permission('procurement.*'))):
    row=load_pr(db,requisition_id)
    if not row: fail(404,'Requisition not found')
    if row.status not in {'submitted','approved'}: fail(409,'Requisition cannot be rejected')
    row.status='rejected'; db.commit(); db.refresh(row); return row

@router.get('/quotations',response_model=list[QuoteOut])
def quotations(requisition_id:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission('procurement.read'))):
    stmt=select(SupplierQuotation).options(selectinload(SupplierQuotation.lines)).order_by(SupplierQuotation.created_at.desc())
    if requisition_id: stmt=stmt.where(SupplierQuotation.requisition_id==requisition_id)
    return db.scalars(stmt).unique().all()
@router.post('/quotations',response_model=QuoteOut,status_code=201)
def create_quotation(p:QuoteCreate,db:Session=Depends(get_db),_:User=Depends(require_permission('procurement.*'))):
    req=load_pr(db,p.requisition_id)
    if not req or req.status!='approved': fail(409,'Quotation requires an approved requisition')
    if not db.get(Supplier,p.supplier_id): fail(422,'Supplier not found')
    allowed={x.item_id for x in req.lines}
    if any(x.item_id not in allowed for x in p.lines): fail(422,'Quotation contains item not present on requisition')
    row=SupplierQuotation(quotation_number=numbered('RFQ',db.query(SupplierQuotation).count()),requisition_id=p.requisition_id,supplier_id=p.supplier_id,valid_until=p.valid_until,delivery_days=p.delivery_days,payment_terms_days=p.payment_terms_days,notes=p.notes)
    row.lines=[SupplierQuotationLine(**x.model_dump()) for x in p.lines]
    return save(db,row)
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
    if not db.get(Supplier,p.supplier_id) or not db.get(Location,p.delivery_location_id): fail(422,'Supplier or delivery location not found')
    if p.requisition_id:
        req=load_pr(db,p.requisition_id)
        if not req or req.status!='approved': fail(409,'Purchase order requires an approved requisition')
    if p.quotation_id:
        quote=load_quote(db,p.quotation_id)
        if not quote or quote.supplier_id!=p.supplier_id: fail(409,'Quotation does not match supplier')
    row=PurchaseOrder(purchase_order_number=numbered('PO',db.query(PurchaseOrder).count()),supplier_id=p.supplier_id,requisition_id=p.requisition_id,quotation_id=p.quotation_id,delivery_location_id=p.delivery_location_id,expected_delivery_date=p.expected_delivery_date,notes=p.notes,created_by_user_id=user.id,status='draft')
    row.lines=[PurchaseOrderLine(**x.model_dump()) for x in p.lines]
    return save(db,row)
@router.post('/purchase-orders/{po_id}/approve',response_model=POOut)
def approve_po(po_id:str,db:Session=Depends(get_db),user:User=Depends(require_permission('procurement.*'))):
    po=load_po(db,po_id)
    if not po: fail(404,'Purchase order not found')
    if po.status!='draft': fail(409,'Only draft purchase orders can be approved')
    po.status='approved'; po.approved_by_user_id=user.id; po.approved_at=now(); db.commit(); db.refresh(po); return po

@router.post('/purchase-orders/{po_id}/receipts',response_model=GoodsReceiptOut,status_code=201)
def receive_po(po_id:str,p:GoodsReceiptCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('receiving.*'))):
    po=load_po(db,po_id)
    if not po: fail(404,'Purchase order not found')
    if po.status not in {'approved','partially_received'}: fail(409,'Purchase order is not receivable')
    po_lines={x.id:x for x in po.lines}; entries=[]
    for x in p.lines:
        line=po_lines.get(x.purchase_order_line_id)
        if not line: fail(422,'Purchase order line not found')
        outstanding=Decimal(line.ordered_quantity)-Decimal(line.received_quantity)
        if x.received_quantity>outstanding: fail(409,'Received quantity exceeds outstanding quantity')
        if x.accepted_quantity: entries.append({'item_id':line.item_id,'location_id':po.delivery_location_id,'quantity':x.accepted_quantity,'unit_cost':line.unit_price,'reason':'purchase order receipt'})
    try: doc=post_document(db,kind='po_receipt',actor_id=user.id,entries=entries,reference=po.purchase_order_number,notes=p.notes,idempotency_key=p.idempotency_key)
    except InventoryError as exc: fail(409,str(exc))
    existing=db.scalar(select(GoodsReceipt).where(GoodsReceipt.stock_document_id==doc.id).options(selectinload(GoodsReceipt.lines)))
    if existing: return existing
    receipt=GoodsReceipt(goods_receipt_number=numbered('GRN',db.query(GoodsReceipt).count()),purchase_order_id=po.id,stock_document_id=doc.id,delivery_reference=p.delivery_reference,received_by_user_id=user.id,notes=p.notes)
    for x in p.lines:
        line=po_lines[x.purchase_order_line_id]; line.received_quantity=Decimal(line.received_quantity)+x.received_quantity
        receipt.lines.append(GoodsReceiptLine(purchase_order_line_id=line.id,item_id=line.item_id,received_quantity=x.received_quantity,accepted_quantity=x.accepted_quantity,rejected_quantity=x.rejected_quantity,unit_cost=line.unit_price))
    po.status='received' if all(Decimal(x.received_quantity)>=Decimal(x.ordered_quantity) for x in po.lines) else 'partially_received'
    db.add(receipt); db.commit(); db.refresh(receipt); return receipt
@router.get('/goods-receipts',response_model=list[GoodsReceiptOut])
def goods_receipts(db:Session=Depends(get_db),_:User=Depends(require_permission('receiving.read'))): return db.scalars(select(GoodsReceipt).options(selectinload(GoodsReceipt.lines)).order_by(GoodsReceipt.received_at.desc())).unique().all()

@router.post('/purchase-orders/{po_id}/returns',response_model=ReturnOut,status_code=201)
def create_return(po_id:str,p:ReturnCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('receiving.*'))):
    po=load_po(db,po_id)
    if not po: fail(404,'Purchase order not found')
    lines={x.id:x for x in po.lines}; entries=[]
    for x in p.lines:
        line=lines.get(x.purchase_order_line_id)
        if not line: fail(422,'Purchase order line not found')
        returnable=Decimal(line.received_quantity)-Decimal(line.returned_quantity)
        if x.quantity>returnable: fail(409,'Return quantity exceeds received quantity')
        entries.append({'item_id':line.item_id,'location_id':po.delivery_location_id,'quantity':-x.quantity,'unit_cost':line.unit_price,'reason':'purchase return'})
    try: doc=post_document(db,kind='purchase_return',actor_id=user.id,entries=entries,reference=po.purchase_order_number,notes=p.reason,idempotency_key=p.idempotency_key)
    except InventoryError as exc: fail(409,str(exc))
    existing=db.scalar(select(PurchaseReturn).where(PurchaseReturn.stock_document_id==doc.id))
    if existing: return existing
    for x in p.lines: lines[x.purchase_order_line_id].returned_quantity=Decimal(lines[x.purchase_order_line_id].returned_quantity)+x.quantity
    row=PurchaseReturn(return_number=numbered('PRTN',db.query(PurchaseReturn).count()),purchase_order_id=po.id,stock_document_id=doc.id,reason=p.reason,created_by_user_id=user.id)
    db.add(row); db.commit(); db.refresh(row); return row
