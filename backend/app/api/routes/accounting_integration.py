from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.api.integration_auth import integration_token_header, require_integration_token
from app.db.session import get_db
from app.models.operations import IntegrationEvent
from app.models.user import User
from app.services.controls import add_audit, add_notification
from app.services.operational_authorization import require_global_operational_access

router = APIRouter(tags=["accounting-integration"])

ACCOUNTING_RULES = {
    "inventory.stock_document.posted": {"debit": "Inventory Asset", "credit": "Inventory Clearing"},
    "inventory.receipt.posted": {"debit": "Inventory Asset", "credit": "Goods Received Not Invoiced"},
    "inventory.supplier_return.posted": {"debit": "Accounts Payable / Supplier Returns", "credit": "Inventory Asset"},
    "inventory.production.completed": {"debit": "Finished Goods Inventory", "credit": "Raw Materials Inventory"},
    "inventory.production.executed": {"debit": "Finished Goods Inventory", "credit": "Raw Materials Inventory"},
    "inventory.pos_sale_consumed": {"debit": "Cost of Sales", "credit": "Inventory Asset"},
    "inventory.pos_sale_reversed": {"debit": "Inventory Asset", "credit": "Cost of Sales"},
    "inventory.master_data.snapshot": {"debit": None, "credit": None},
}


def utcnow(): return datetime.now(timezone.utc)

def money(value) -> Decimal:
    """Never disguise malformed financial evidence as an actual zero."""
    if value is None or isinstance(value, bool):
        raise ValueError("Financial quantity or amount is missing")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Financial quantity or amount is not numeric") from exc
    if not amount.is_finite():
        raise ValueError("Financial quantity or amount must be finite")
    return amount


def event_amount(event: IntegrationEvent) -> Decimal:
    payload=event.payload if isinstance(event.payload,dict) else {}
    for key in ("total_cost","total_actual_cost","amount","inventory_value"):
        if key in payload:return money(payload[key])
    total=Decimal("0")
    if "lines" in payload and not isinstance(payload["lines"],list):
        raise ValueError("Financial lines must be a list")
    for line in payload.get("lines",[]):
        if not isinstance(line,dict):
            raise ValueError("Financial line is not an object")
        if event.event_type=="inventory.stock_document.posted":
            # Signed movement quantity; opposing transfer entries must net to
            # zero. A missing cost is UNKNOWN, not a zero-value movement.
            total+=money(line.get("quantity"))*money(line.get("unit_cost"))
        else:
            total+=money(line.get("cost")) if "cost" in line else abs(money(line.get("quantity")))*money(line.get("unit_cost"))
    return total


def journal_lines(event:IntegrationEvent, amount:Decimal|None=None)->list[dict]:
    rule=ACCOUNTING_RULES.get(event.event_type)
    if amount is None:
        amount=event_amount(event)
    if not rule or not rule["debit"] or not rule["credit"] or amount==0:return []
    debit,credit=rule["debit"],rule["credit"]
    if amount<0:debit,credit=credit,debit;amount=-amount
    return [{"side":"debit","account":debit,"amount":amount},{"side":"credit","account":credit,"amount":amount}]


def event_row(event:IntegrationEvent)->dict:
    rule=ACCOUNTING_RULES.get(event.event_type,{"debit":"Unmapped","credit":"Unmapped"})
    payload=event.payload if isinstance(event.payload,dict) else {}
    intake=payload.get("accounting_intake") if isinstance(payload.get("accounting_intake"),dict) else {}
    receipt=payload.get("accounting_receipt") if isinstance(payload.get("accounting_receipt"),dict) else {}
    proof=payload.get("accounting_reconciliation") if isinstance(payload.get("accounting_reconciliation"),dict) else {}
    intake_status=str(proof.get("review_status") or intake.get("status") or ("unverified_delivery" if event.status=="completed" else "not_delivered"))
    # Only a recent verified Accounting journal proof can establish posting.
    # A receipt or accepted review by itself is never a posted GL entry.
    confirmed=proof.get("ledger_posting_confirmed") is True and intake_status=="accepted" and proof.get("journal_status")=="posted"
    try:
        amount=event_amount(event)
        evidence_error=None
    except (ValueError, InvalidOperation, ArithmeticError) as exc:
        # This is a read-only preview. Do not change delivery or GL status and
        # never invent a zero amount for incomplete historical source events.
        amount=None
        evidence_error=str(exc)
    lines=journal_lines(event,amount) if amount is not None else []
    return {"id":event.id,"event_type":event.event_type,"aggregate_type":event.aggregate_type,"aggregate_id":event.aggregate_id,"idempotency_key":event.idempotency_key,"status":event.status,"attempts":event.attempts,"max_attempts":event.max_attempts,"last_error":event.last_error,"created_at":event.created_at,"processed_at":event.processed_at,"amount":amount,"financial_evidence_error":evidence_error,"financial_evidence_valid":evidence_error is None,"debit_account":rule["debit"],"credit_account":rule["credit"],"mapped":event.event_type in ACCOUNTING_RULES,"journal_lines":lines,"accounting_receipt":receipt or None,"accounting_intake_status":intake_status,"accounting_review_id":proof.get("review_id") or intake.get("review_id"),"ledger_posting_confirmed":confirmed,"accounting_journal_entry_id":proof.get("journal_entry_id"),"accounting_journal_status":proof.get("journal_status"),"accounting_verified_at":proof.get("checked_at"),"accounting_verification_error":proof.get("last_error")}


class AccountingReceipt(BaseModel):
    idempotency_key:str=Field(min_length=1,max_length=120)
    external_receipt_id:str=Field(min_length=1,max_length=180)
    accepted:bool
    external_reference:str|None=Field(default=None,max_length=180)
    message:str|None=Field(default=None,max_length=1000)


@router.get("/integrations/accounting/workspace")
def accounting_workspace(status:str|None=None,limit:int=Query(200,ge=1,le=500),db:Session=Depends(get_db),user:User=Depends(require_permission("integrations.read"))):
    require_global_operational_access(db,user)
    stmt=select(IntegrationEvent).where(IntegrationEvent.destination_system=="accounting").order_by(IntegrationEvent.created_at.desc())
    if status:stmt=stmt.where(IntegrationEvent.status==status)
    events=db.scalars(stmt.limit(limit)).all()
    counts=dict(db.execute(select(IntegrationEvent.status,func.count()).where(IntegrationEvent.destination_system=="accounting").group_by(IntegrationEvent.status)).all())
    rows=[event_row(event) for event in events]
    total_events=sum(counts.values())
    return {
        "summary":{
            # Backlog counts reflect ALL Accounting events; all other event
            # metrics reflect displayed rows, which may be truncated by limit.
            "pending":counts.get("pending",0)+counts.get("processing",0),
            "completed":counts.get("completed",0),
            "failed":counts.get("failed",0),
            "dead_letter":counts.get("dead_letter",0),
            "total_events":total_events,
            "displayed_events":len(rows),
            "has_more":total_events>len(rows),
            "event_metrics_scope":"displayed_rows",
            "unmapped":sum(1 for row in rows if not row["mapped"]),
            "financial_evidence_errors":sum(1 for row in rows if not row["financial_evidence_valid"]),
            "queued_value":sum((row["amount"] for row in rows if row["status"] in {"pending","processing","failed"} and row["amount"] is not None),Decimal("0")),
            "ready_for_review":sum(1 for row in rows if row["accounting_intake_status"]=="ready_for_review"),
            "review_rejected":sum(1 for row in rows if row["accounting_intake_status"]=="rejected"),
            "unverified_delivery":sum(1 for row in rows if row["accounting_intake_status"]=="unverified_delivery"),
            "posted_journals_verified":sum(1 for row in rows if row["ledger_posting_confirmed"]),
            "verification_unavailable":sum(1 for row in rows if row["accounting_intake_status"]=="verification_unavailable"),
        },
        "rules":[{"event_type":event_type,**accounts} for event_type,accounts in sorted(ACCOUNTING_RULES.items())],
        "events":rows,
    }


@router.post("/integrations/accounting/receipts")
def accounting_receipt(payload:AccountingReceipt,token:str|None=Depends(integration_token_header),db:Session=Depends(get_db)):
    require_integration_token("accounting",token)
    event=db.scalar(select(IntegrationEvent).where(IntegrationEvent.idempotency_key==payload.idempotency_key,IntegrationEvent.destination_system=="accounting").with_for_update())
    if not event:raise HTTPException(404,"Accounting event not found")
    existing=(event.payload or {}).get("accounting_receipt")
    if existing:
        if existing.get("external_receipt_id")==payload.external_receipt_id and existing.get("accepted")==payload.accepted:return event_row(event)
        raise HTTPException(409,"Accounting event already has a conflicting final acknowledgement")
    receipt={"external_receipt_id":payload.external_receipt_id,"accepted":payload.accepted,"external_reference":payload.external_reference,"message":payload.message,"received_at":utcnow().isoformat()}
    event.payload={**(event.payload or {}),"accounting_receipt":receipt};event.locked_at=None;event.locked_by=None
    if payload.accepted:
        event.status="completed";event.processed_at=utcnow();event.last_error=None;action="accounting.receipt_accepted"
    else:
        event.status="failed";event.last_error=payload.message or "Accounting rejected the event";action="accounting.receipt_rejected"
        recipients=db.scalars(select(User).where(User.is_active.is_(True),User.role.in_(["owner","inventory_manager"]))).all()
        for recipient in recipients:add_notification(db,title="Accounting integration rejected",message=f"{event.event_type} for {event.aggregate_id} was rejected by Accounting.",severity="error",user_id=recipient.id)
    add_audit(db,actor_user_id=None,action=action,entity_type="integration_event",entity_id=event.id,details=receipt);db.commit();return event_row(event)


@router.post("/integrations/accounting/events/{event_id}/requeue")
def requeue_accounting_event(event_id:str,db:Session=Depends(get_db),user:User=Depends(require_permission("integrations.*"))):
    require_global_operational_access(db,user)
    event=db.get(IntegrationEvent,event_id)
    if not event or event.destination_system!="accounting":raise HTTPException(404,"Accounting event not found")
    if event.status not in {"failed","dead_letter"}:raise HTTPException(409,"Only failed or dead-letter accounting events can be requeued")
    if (event.payload or {}).get("accounting_receipt",{}).get("accepted") is True:raise HTTPException(409,"Accepted accounting events cannot be requeued")
    event.status="pending";event.attempts=0;event.last_error=None;event.locked_at=None;event.locked_by=None;event.available_at=utcnow();add_audit(db,actor_user_id=user.id,action="accounting.event_requeued",entity_type="integration_event",entity_id=event.id);db.commit();return event_row(event)
