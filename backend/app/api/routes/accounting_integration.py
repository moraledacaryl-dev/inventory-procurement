from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.operations import IntegrationEvent
from app.models.user import User
from app.services.controls import add_audit, add_notification

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


def utcnow():
    return datetime.now(timezone.utc)


def money(value) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def event_amount(event: IntegrationEvent) -> Decimal:
    payload = event.payload or {}
    for key in ("total_cost", "total_actual_cost", "amount", "inventory_value"):
        if key in payload:
            return money(payload[key])
    total = Decimal("0")
    for line in payload.get("lines", []) if isinstance(payload.get("lines"), list) else []:
        if "cost" in line:
            total += money(line.get("cost"))
        else:
            total += abs(money(line.get("quantity"))) * money(line.get("unit_cost"))
    return total


def event_row(event: IntegrationEvent) -> dict:
    rule = ACCOUNTING_RULES.get(event.event_type, {"debit": "Unmapped", "credit": "Unmapped"})
    return {
        "id": event.id,
        "event_type": event.event_type,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "idempotency_key": event.idempotency_key,
        "status": event.status,
        "attempts": event.attempts,
        "max_attempts": event.max_attempts,
        "last_error": event.last_error,
        "created_at": event.created_at,
        "processed_at": event.processed_at,
        "amount": event_amount(event),
        "debit_account": rule["debit"],
        "credit_account": rule["credit"],
        "mapped": event.event_type in ACCOUNTING_RULES,
    }


class AccountingReceipt(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=120)
    accepted: bool
    external_reference: str | None = Field(default=None, max_length=180)
    message: str | None = Field(default=None, max_length=1000)


@router.get("/integrations/accounting/workspace")
def accounting_workspace(
    status: str | None = None,
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("integrations.read")),
):
    stmt = select(IntegrationEvent).where(IntegrationEvent.destination_system == "accounting").order_by(IntegrationEvent.created_at.desc())
    if status:
        stmt = stmt.where(IntegrationEvent.status == status)
    events = db.scalars(stmt.limit(limit)).all()
    counts = dict(db.execute(select(IntegrationEvent.status, func.count()).where(IntegrationEvent.destination_system == "accounting").group_by(IntegrationEvent.status)).all())
    rows = [event_row(event) for event in events]
    return {
        "summary": {
            "pending": counts.get("pending", 0) + counts.get("processing", 0),
            "completed": counts.get("completed", 0),
            "failed": counts.get("failed", 0),
            "dead_letter": counts.get("dead_letter", 0),
            "unmapped": sum(1 for row in rows if not row["mapped"]),
            "queued_value": sum((row["amount"] for row in rows if row["status"] in {"pending", "processing", "failed"}), Decimal("0")),
        },
        "rules": [{"event_type": event_type, **accounts} for event_type, accounts in sorted(ACCOUNTING_RULES.items())],
        "events": rows,
    }


@router.post("/integrations/accounting/receipts")
def accounting_receipt(payload: AccountingReceipt, db: Session = Depends(get_db), user: User = Depends(require_permission("integrations.*"))):
    event = db.scalar(select(IntegrationEvent).where(IntegrationEvent.idempotency_key == payload.idempotency_key, IntegrationEvent.destination_system == "accounting").with_for_update())
    if not event:
        raise HTTPException(404, "Accounting event not found")
    event.payload = {**(event.payload or {}), "accounting_receipt": {"accepted": payload.accepted, "external_reference": payload.external_reference, "message": payload.message, "received_at": utcnow().isoformat()}}
    event.locked_at = None
    event.locked_by = None
    if payload.accepted:
        event.status = "completed"
        event.processed_at = utcnow()
        event.last_error = None
        action = "accounting.receipt_accepted"
    else:
        event.status = "failed"
        event.last_error = payload.message or "Accounting rejected the event"
        action = "accounting.receipt_rejected"
        add_notification(db, title="Accounting integration rejected", message=f"{event.event_type} for {event.aggregate_id} was rejected by Accounting.", severity="error", user_id=user.id)
    add_audit(db, actor_user_id=user.id, action=action, entity_type="integration_event", entity_id=event.id, details={"external_reference": payload.external_reference, "message": payload.message})
    db.commit()
    return event_row(event)


@router.post("/integrations/accounting/events/{event_id}/requeue")
def requeue_accounting_event(event_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission("integrations.*"))):
    event = db.get(IntegrationEvent, event_id)
    if not event or event.destination_system != "accounting":
        raise HTTPException(404, "Accounting event not found")
    if event.status not in {"failed", "dead_letter"}:
        raise HTTPException(409, "Only failed or dead-letter accounting events can be requeued")
    event.status = "pending"
    event.attempts = 0
    event.last_error = None
    event.locked_at = None
    event.locked_by = None
    event.available_at = utcnow()
    add_audit(db, actor_user_id=user.id, action="accounting.event_requeued", entity_type="integration_event", entity_id=event.id)
    db.commit()
    return event_row(event)
