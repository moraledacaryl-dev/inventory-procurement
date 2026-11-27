"""Verify safeguards against actual source records and observed HTTP outcomes."""
from sqlalchemy import select
from app.models import StockBalance,StockDocument,StockReservation,IntegrationEvent,AuditLog
from app.models.staff_meals import StaffMeal


def prepare_safety(db,lesson,v):
    if not lesson.workflow.startswith("safety_") or lesson.module!="W":return
    accepted=lesson.id.startswith("refuse-")
    db.add(IntegrationEvent(id="training-safety-event",direction="outbound",source_system="inventory",
        destination_system="accounting" if accepted else "operations",event_type="inventory.stock_document.posted" if accepted else "inventory.exception.created",
        aggregate_type="stock_document" if accepted else "inventory_exception",aggregate_id="TRAIN-SAFETY",
        idempotency_key="training-safety-original",status="failed",attempts=3,last_error="Historical failure awaiting review",
        payload={"total_cost":"1000","accounting_receipt":{"accepted":True,"external_receipt_id":"TRAIN-ACCEPTED"}} if accepted else {"title":"Training reviewed stock alert","quantity":"2"}))


def verify_safety(db,lesson,v,actions):
    stock=db.scalar(select(StockBalance.quantity).where(StockBalance.item_id==v["chicken"],StockBalance.location_id==v["store"]))
    untouched=stock==v["base"] and not db.scalar(select(StockDocument.id).where(StockDocument.posted_by_user_id==v["actor"]))
    observed={(row.get("path"),row.get("status")) for row in actions}
    if lesson.id=="staff-meal-reserved-stock":
        reservation=db.scalar(select(StockReservation).where(StockReservation.item_id==v["chicken"]))
        from app.schemas.staff_meals import StaffMealCreate
        exact=set()
        for action in actions:
            try:
                proposal=StaffMealCreate.model_validate(action.get("meal_proposal"))
                matches=proposal.meal_name=="Training reserved-stock check" and proposal.location_id==v["store"] and proposal.servings==4 and len(proposal.lines)==1 and proposal.lines[0].item_id==v["chicken"] and proposal.lines[0].quantity==v["meal_reserved_need"]
                if matches:exact.add((action.get("path"),action.get("status")))
            except (ValueError,TypeError):pass
        ok=all(("/api/v1"+path,409) in exact for path in ["/staff-meals/preview","/staff-meals"]) and db.scalar(select(StaffMeal.id)) is None and reservation.status=="active" and reservation.quantity==4
    else:
        row=db.get(IntegrationEvent,"training-safety-event")
        accepted=lesson.id.startswith("refuse-")
        endpoint="/integrations/accounting/events/training-safety-event/requeue" if lesson.id.endswith("dedicated") else "/integration-events/training-safety-event/retry"
        expected_payload={"total_cost":"1000","accounting_receipt":{"accepted":True,"external_receipt_id":"TRAIN-ACCEPTED"}} if accepted else {"title":"Training reviewed stock alert","quantity":"2"}
        audit=db.scalar(select(AuditLog.id).where(AuditLog.actor_user_id==v["actor"],AuditLog.entity_id==row.id))
        ok=("/api/v1"+endpoint,409 if accepted else 200) in observed and row.status==("failed" if accepted else "pending") and row.attempts==(3 if accepted else 0) and row.payload==expected_payload and row.idempotency_key=="training-safety-original" and row.aggregate_id=="TRAIN-SAFETY" and (not audit if accepted else bool(audit)) and row.processed_at is None and row.locked_at is None and row.locked_by is None
    passed=bool(ok and untouched)
    return passed,{"passed":passed,"stock_integrity":bool(untouched),"source_safeguard_preserved":bool(ok),"correction":lesson.situation.format(**v)+" Read the actual response and preserve the original stock and financial evidence."}
