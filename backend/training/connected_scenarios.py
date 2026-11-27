"""Faithful local request and delivery fixtures; no transport is executed."""
from decimal import Decimal
import re
from sqlalchemy import select
from app.models.operations import IntegrationEvent
from app.models.procurement import PurchaseOrder
from app.models.inventory import StockBalance, StockDocument
from app.models.audit_log import AuditLog


def local_control_allowed(method,path,lesson):
    if method=="POST" and lesson.id=="refuse-accepted-accounting-dedicated":
        return path=="/api/v1/integrations/accounting/events/training-safety-event/requeue"
    if method!="POST" or not lesson.workflow.startswith(("connected_","capstone_")):return False
    return bool(re.fullmatch(r"/api/v1/integrations/(accounting/events/[A-Za-z0-9-]+/requeue|operations/requests/[A-Za-z0-9-]+/decision)",path))


def prepare_connected(db,lesson,v):
    if not lesson.workflow.startswith("connected_"):return
    if lesson.module=="W":
        db.get(PurchaseOrder,v["po"]).lines[0].ordered_quantity=5
        db.add(IntegrationEvent(id="training-retry",direction="outbound",source_system="inventory",destination_system="accounting",event_type="procurement.purchase_order.approved",aggregate_type="purchase_order",aggregate_id="TRAIN-RETRY",idempotency_key="training-accounting-retry",status="failed",attempts=5,last_error="Synthetic temporary receiver outage",payload={"purchase_order_id":v["po"],"total":"1000"}))
        return
    completed=lesson.id=="complete-evidenced-operations-work"
    db.add(IntegrationEvent(id="training-connected-request",direction="inbound",source_system="staff",destination_system="inventory",event_type="operations.request.submitted",aggregate_type="operational_request",aggregate_id="TRAIN-WEEKEND-DUTY",idempotency_key="training-staff-request",status="completed",payload={"source_system":"staff","external_request_id":"TRAIN-WEEKEND-DUTY","requester_user_id":v["colleague"],"department":"Kitchen","request_type":"stock_request","title":"Training weekend supplies","description":f"Confirmed handover of {v['quantity']} kg chicken; follow the linked movement." if completed else "Verified fictional weekend supply request","priority":"high","workflow_status":"accepted" if completed else "submitted","assigned_to_user_id":v["colleague"] if completed else None}))


def after_prepare_connected(db,lesson,v):
    if lesson.id=="complete-evidenced-operations-work":
        from app.services.inventory import post_document
        document=post_document(db,kind="issue",actor_id=v["colleague"],entries=[{"item_id":v["chicken"],"location_id":v["store"],"quantity":-Decimal(v["quantity"]),"unit_cost":200}],reference="TRAIN-WEEKEND-DUTY")
        event=db.get(IntegrationEvent,"training-connected-request")
        event.payload={**event.payload,"related_entity_type":"stock_document","related_entity_id":document.id}
        db.commit()


def verify_connected(db,lesson,v,actions):
    docs=list(db.scalars(select(StockDocument).where(StockDocument.posted_by_user_id==v["actor"])))
    balance=db.scalar(select(StockBalance.quantity).where(StockBalance.item_id==v["chicken"],StockBalance.location_id==v["store"]))
    expected=v["base"]-(v["quantity"] if lesson.id=="complete-evidenced-operations-work" else 0)
    unchanged=not docs and balance==expected and not db.scalar(select(PurchaseOrder.id).where(PurchaseOrder.created_by_user_id==v["actor"]))
    if lesson.module=="W":
        row=db.get(IntegrationEvent,"training-retry")
        po=db.get(PurchaseOrder,v["po"])
        ok=row.status=="pending" and row.attempts==0 and row.last_error is None and row.processed_at is None and row.idempotency_key=="training-accounting-retry" and row.payload=={"purchase_order_id":v["po"],"total":"1000"} and po.status=="approved" and po.lines[0].ordered_quantity==5 and bool(db.scalar(select(AuditLog.id).where(AuditLog.actor_user_id==v["actor"],AuditLog.action=="accounting.event_requeued",AuditLog.entity_id==row.id)))
    else:
        row=db.get(IntegrationEvent,"training-connected-request");payload=row.payload
        decision,notes={"accept-accountable-operations-work":("accepted","verified need"),"reject-duplicate-operations-work":("rejected","duplicate demand"),"complete-evidenced-operations-work":("completed","handover confirmed")}[lesson.id]
        outbound=list(db.scalars(select(IntegrationEvent).where(IntegrationEvent.direction=="outbound",IntegrationEvent.event_type=="inventory.operations.request_status_changed")))
        ok=payload.get("workflow_status")==decision and payload.get("decision_notes")==notes and payload.get("decided_by_user_id")==v["actor"] and payload.get("requester_user_id")==v["colleague"] and len(outbound)==1 and outbound[0].destination_system=="staff" and outbound[0].status=="pending" and outbound[0].processed_at is None and outbound[0].payload.get("workflow_status")==decision and outbound[0].payload.get("external_request_id")=="TRAIN-WEEKEND-DUTY"
        if decision in {"accepted","completed"}:ok=ok and payload.get("assigned_to_user_id")==v["colleague"]
        if decision=="completed":
            document=db.get(StockDocument,payload.get("related_entity_id"))
            ok=ok and document is not None and document.posted_by_user_id==v["colleague"] and len(document.movements)==1 and document.movements[0].quantity==-v["quantity"]
    passed=bool(ok and unchanged)
    return passed,{"workflow":lesson.workflow,"passed":passed,"stock_unchanged":bool(unchanged),"external_delivery_started":False,"correction":lesson.situation.format(**v)+" Check the actual assignee, decision notes and local pending handoff. Do not create another business transaction or claim that a journal was posted."}
