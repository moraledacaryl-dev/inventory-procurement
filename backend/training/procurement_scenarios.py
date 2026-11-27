"""Purchasing fixtures and exact, read-only commercial outcome validation."""
from decimal import Decimal
from sqlalchemy import select
from app.models.procurement import PurchaseRequisition, PurchaseRequisitionLine, SupplierQuotation, SupplierQuotationLine, PurchaseOrder, Supplier
from app.models.inventory import StockBalance, StockDocument
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.operations import IntegrationEvent


def applicable(lesson):
    return lesson.workflow.startswith("procurement_") or lesson.workflow=="read_procurement"


def prepare_procurement(db,lesson,v):
    if not applicable(lesson):return
    from app.models.pass6 import OperationalAccessScope
    submitted=lesson.module=="J"
    req=PurchaseRequisition(id="training-requisition",requisition_number="TRAIN-REQUEST",department="Kitchen",location_id=v["store"],
        justification="Verified weekend demand" if lesson.id!="reject-duplicate-request" else "Duplicate of existing approved TRAIN-PO",status="submitted" if submitted else "approved",
        requested_by_user_id=v["actor"] if lesson.id=="request-self-approval" else v["colleague"],approved_by_user_id=None if submitted else v["reviewer"])
    req.lines=[PurchaseRequisitionLine(item_id=v["chicken"],quantity=v["quantity"],estimated_unit_cost=200)]
    db.add(req)
    po=db.get(PurchaseOrder,v["po"])
    if lesson.id in {"purchase-approval-limit","amend-draft-order"}:
        po.status="draft";po.approved_by_user_id=None;po.approved_at=None
    if lesson.id in {"purchase-approval-limit","inspect-received-order-lock"}:po.lines[0].ordered_quantity=v["quantity"]
    if lesson.id=="purchase-approval-limit":
        for scope in db.scalars(select(OperationalAccessScope).where(OperationalAccessScope.user_id==v["actor"])):scope.approval_limit=100
    if lesson.id in {"award-timely-quotation","inspect-awarded-order"}:
        db.add(Supplier(id="training-budget-supplier",code="TRAIN-BUDGET",name="Training Budget Foods",payment_terms_days=7))
        db.flush()
        for name,supplier,price,days in [("fast",v["supplier"],220,1),("cheap","training-budget-supplier",200,8)]:
            quote=SupplierQuotation(id="training-quote-"+name,quotation_number="TRAIN-"+("FAST" if name=="fast" else "BUDGET"),requisition_id=req.id,supplier_id=supplier,delivery_days=days,payment_terms_days=7,status="submitted")
            quote.lines=[SupplierQuotationLine(item_id=v["chicken"],quantity=v["quantity"],unit_price=price)]
            db.add(quote)


def after_prepare_procurement(db,lesson,v):
    if lesson.id=="inspect-awarded-order":
        from app.api.routes.quotation_po_workspace import award_quotation, QuoteAwardCreate
        # Replace the unrelated base PO with the actual awarded PO while keeping
        # its real, generated identifier. The read task resolves that identifier.
        base=db.get(PurchaseOrder,v["po"])
        db.delete(base);db.commit()
        result=award_quotation("training-requisition",QuoteAwardCreate(quotation_id="training-quote-fast",delivery_location_id=v["store"]),db,db.get(User,v["colleague"]))
        po=db.get(PurchaseOrder,result["purchase_order_id"])
        po.purchase_order_number="TRAIN-PO";db.commit()
    if lesson.id=="inspect-received-order-lock":
        from app.api.routes.receiving_workspace import post_controlled_receipt, ControlledReceiptCreate
        post_controlled_receipt(v["po"],ControlledReceiptCreate(delivery_reference="TRAIN-PRIOR-DELIVERY",lines=[{"purchase_order_line_id":v["po-line"],"received_quantity":v["quantity"],"accepted_quantity":v["quantity"],"rejected_quantity":0}]),db,db.get(User,v["colleague"]))


def procurement_inspection(lesson,mode,v):
    if lesson.id=="inspect-awarded-order":return "Open the linked TRAIN-PO. What is its actual status?","draft","/purchasing?view=source"
    if lesson.id=="inspect-approved-order-lock":return "What status is shown for TRAIN-PO?","approved",lesson.route.format(**v)
    if lesson.id=="inspect-received-order-lock":return "How many kg does TRAIN-PO record as received?",str(v["quantity"]),lesson.route.format(**v)


def verify_procurement(db,lesson,v,actions):
    req=db.get(PurchaseRequisition,"training-requisition")
    po=db.get(PurchaseOrder,v["po"])
    actor_docs=list(db.scalars(select(StockDocument).where(StockDocument.posted_by_user_id==v["actor"])))
    balance=db.scalar(select(StockBalance.quantity).where(StockBalance.item_id==v["chicken"],StockBalance.location_id==v["store"]))
    untouched=balance==v["base"] and not actor_docs
    id=lesson.id
    def refused(path,status):return any(a.get("path")=="/api/v1"+path and a.get("status")==status for a in actions)
    def audited(action,entity):return bool(db.scalar(select(AuditLog.id).where(AuditLog.actor_user_id==v["actor"],AuditLog.action==action,AuditLog.entity_id==entity)))
    def local_event(type,entity):
        row=db.scalar(select(IntegrationEvent).where(IntegrationEvent.event_type==type,IntegrationEvent.aggregate_id==entity))
        return bool(row and row.status=="pending")
    ok=False;evidence={"workflow":lesson.workflow,"stock_unchanged":bool(untouched)}
    if id=="approve-purchase-request":
        ok=req.status=="approved" and req.approved_by_user_id==v["actor"] and req.requested_by_user_id!=v["actor"] and local_event("procurement.requisition.approved",req.id)
    elif id=="reject-duplicate-request":ok=req.status=="rejected" and not req.approved_by_user_id and po.status=="approved" and audited("requisition.rejected",req.id)
    elif id=="request-self-approval":ok=req.status=="submitted" and not req.approved_by_user_id and refused("/requisitions/training-requisition/approve",409)
    elif id=="record-supplier-quotation":
        rows=list(db.scalars(select(SupplierQuotation)))
        ok=len(rows)==1 and rows[0].supplier_id==v["supplier"] and rows[0].requisition_id==req.id and rows[0].delivery_days==1 and rows[0].payment_terms_days==v["terms"] and rows[0].valid_until is None and rows[0].notes==v["reference"] and len(rows[0].lines)==1 and rows[0].lines[0].item_id==v["chicken"] and rows[0].lines[0].quantity==v["quantity"] and rows[0].lines[0].unit_price==220 and rows[0].status=="submitted" and len(list(db.scalars(select(PurchaseOrder))))==1
    elif id=="award-timely-quotation":
        rows=list(db.scalars(select(PurchaseOrder).where(PurchaseOrder.created_by_user_id==v["actor"])))
        fast=db.get(SupplierQuotation,"training-quote-fast");cheap=db.get(SupplierQuotation,"training-quote-cheap")
        ok=len(rows)==1 and rows[0].requisition_id==req.id and rows[0].quotation_id==fast.id and rows[0].supplier_id==v["supplier"] and rows[0].delivery_location_id==v["store"] and rows[0].status=="draft" and rows[0].approved_by_user_id is None and len(rows[0].lines)==1 and rows[0].lines[0].item_id==v["chicken"] and rows[0].lines[0].ordered_quantity==v["quantity"] and rows[0].lines[0].unit_price==220 and fast.status=="awarded" and cheap.status=="not_awarded" and len(list(db.scalars(select(PurchaseOrder))))==2
        if rows:evidence["purchase_order_id"]=rows[0].id
    elif id=="purchase-approval-limit":ok=po.status=="draft" and not po.approved_by_user_id and refused("/purchase-orders/training-po/approve",403)
    elif id=="amend-draft-order":ok=po.status=="draft" and not po.approved_by_user_id and po.notes==v["reference"] and len(po.lines)==1 and po.lines[0].item_id==v["chicken"] and po.lines[0].ordered_quantity==v["quantity"] and po.lines[0].unit_price==220 and po.lines[0].received_quantity==0 and audited("purchase_order.amended",po.id)
    elif id=="cancel-unreceived-order":ok=po.status=="cancelled" and all(line.received_quantity==0 for line in po.lines) and audited("purchase_order.cancelled",po.id) and local_event("procurement.purchase_order.cancelled",po.id)
    passed=bool(ok and untouched)
    evidence.update(passed=passed,correction=lesson.situation.format(**v)+" Check the actual saved status and relationships. If an unintended commercial change was posted, reset this practice before retrying.")
    return passed,evidence


def verify_procurement_inspection(db,lesson,mode):
    from training.scenarios import values
    v=values(lesson,mode)
    rows=list(db.scalars(select(PurchaseOrder)))
    po=rows[0] if len(rows)==1 else None
    actor_change=db.scalar(select(AuditLog.id).where(AuditLog.actor_user_id==v["actor"]))
    expected=v["base"]+(v["quantity"] if lesson.id=="inspect-received-order-lock" else 0)
    balance=db.scalar(select(StockBalance.quantity).where(StockBalance.item_id==v["chicken"],StockBalance.location_id==v["store"]))
    status="draft" if lesson.id=="inspect-awarded-order" else "received" if lesson.id=="inspect-received-order-lock" else "approved"
    ok=bool(po and not actor_change and balance==expected and po.status==status)
    if lesson.id=="inspect-awarded-order":ok=ok and po.quotation_id=="training-quote-fast" and po.requisition_id=="training-requisition"
    if lesson.id=="inspect-received-order-lock":ok=ok and po.lines[0].received_quantity==v["quantity"]
    return bool(ok),{"record_unchanged":bool(ok),"correction":"Open the actual order record and report what it shows. Keep the order and stock unchanged; reset this practice if an unintended change was posted."}
