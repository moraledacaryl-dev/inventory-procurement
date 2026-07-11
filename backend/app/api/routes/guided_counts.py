from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.inventory import CountLine, CountSession, Item, Location, StockBalance
from app.models.user import User
from app.services.controls import add_audit, add_notification
from app.services.inventory import InventoryError, post_document

router = APIRouter(prefix="/counts", tags=["guided-counts"])


class CountEntryUpdate(BaseModel):
    item_id: str
    counted_quantity: Decimal = Field(ge=0)
    note: str | None = Field(default=None, max_length=240)


class CountEntriesUpdate(BaseModel):
    lines: list[CountEntryUpdate] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_items(self):
        ids = [line.item_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate count lines are not allowed")
        return self


class RecountRequest(BaseModel):
    item_ids: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=240)


def fail(status: int, message: str):
    raise HTTPException(status_code=status, detail=message)


def session_row(db: Session, count_id: str, lock: bool = False) -> CountSession | None:
    stmt = select(CountSession).where(CountSession.id == count_id).options(selectinload(CountSession.lines))
    if lock:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def live_balances(db: Session, location_id: str) -> dict[str, Decimal]:
    return {
        row.item_id: Decimal(row.quantity)
        for row in db.scalars(select(StockBalance).where(StockBalance.location_id == location_id)).all()
    }


def serialize_session(db: Session, session: CountSession) -> dict:
    location = db.get(Location, session.location_id)
    item_ids = {line.item_id for line in session.lines}
    items = {row.id: row for row in db.scalars(select(Item).where(Item.id.in_(item_ids))).all()} if item_ids else {}
    current = live_balances(db, session.location_id)
    counted = 0
    variance_lines = 0
    absolute_variance = Decimal("0")
    value_variance = Decimal("0")
    lines = []
    for line in sorted(session.lines, key=lambda row: items.get(row.item_id).sku if items.get(row.item_id) else row.item_id):
        item = items.get(line.item_id)
        counted_quantity = Decimal(line.counted_quantity) if line.counted_quantity is not None else None
        snapshot = Decimal(line.system_quantity)
        variance = counted_quantity - snapshot if counted_quantity is not None else None
        live = current.get(line.item_id, Decimal("0"))
        drift = live - snapshot
        if counted_quantity is not None:
            counted += 1
            if variance != 0:
                variance_lines += 1
                absolute_variance += abs(variance)
                value_variance += variance * Decimal(item.standard_cost or 0 if item else 0)
        lines.append({
            "id": line.id,
            "item_id": line.item_id,
            "sku": item.sku if item else line.item_id,
            "item_name": item.name if item else "Unknown item",
            "system_quantity": None if session.blind_count and session.status == "open" else str(snapshot),
            "snapshot_quantity": str(snapshot),
            "live_quantity": str(live),
            "counted_quantity": str(counted_quantity) if counted_quantity is not None else None,
            "variance_quantity": str(variance) if variance is not None else None,
            "live_drift_quantity": str(drift),
            "note": line.note,
        })
    return {
        "id": session.id,
        "count_number": session.count_number,
        "location_id": session.location_id,
        "location_code": location.code if location else session.location_id,
        "location_name": location.name if location else "Unknown location",
        "status": session.status,
        "notes": session.notes,
        "blind_count": session.blind_count,
        "approval_threshold": str(session.approval_threshold),
        "created_by_user_id": session.created_by_user_id,
        "approved_by_user_id": session.approved_by_user_id,
        "approved_at": session.approved_at.isoformat() if session.approved_at else None,
        "created_at": session.created_at.isoformat(),
        "posted_document_id": session.posted_document_id,
        "progress": {
            "total_lines": len(lines),
            "counted_lines": counted,
            "remaining_lines": len(lines) - counted,
            "completion_percent": round((counted / len(lines) * 100), 1) if lines else 100,
            "variance_lines": variance_lines,
            "absolute_variance": str(absolute_variance),
            "estimated_value_variance": str(value_variance),
            "live_drift_lines": sum(1 for row in lines if Decimal(row["live_drift_quantity"]) != 0),
        },
        "lines": lines,
    }


def finalize_count(db: Session, session: CountSession, user: User):
    current = live_balances(db, session.location_id)
    entries = []
    for line in session.lines:
        if line.counted_quantity is None:
            continue
        delta = Decimal(line.counted_quantity) - current.get(line.item_id, Decimal("0"))
        if delta:
            balance = db.scalar(select(StockBalance).where(StockBalance.item_id == line.item_id, StockBalance.location_id == session.location_id))
            cost = Decimal(balance.average_cost) if balance else Decimal("0")
            entries.append({"item_id": line.item_id, "location_id": session.location_id, "quantity": delta, "unit_cost": cost, "reason": "physical count variance"})
    if entries:
        document = post_document(db, kind="count_adjustment", actor_id=user.id, entries=entries, reference=session.count_number, notes=session.notes, idempotency_key=f"count-post:{session.id}", commit=False)
        session.posted_document_id = document.id
    session.status = "posted"
    add_audit(db, actor_user_id=user.id, action="count.posted", entity_type="count_session", entity_id=session.id, details={"adjustment_lines": len(entries)})


@router.get("/workspace")
def count_workspace(db: Session = Depends(get_db), _: User = Depends(require_permission("counts.create"))):
    sessions = db.scalars(select(CountSession).options(selectinload(CountSession.lines)).order_by(CountSession.created_at.desc())).unique().all()
    return [serialize_session(db, session) for session in sessions]


@router.get("/{count_id}/detail")
def count_detail(count_id: str, db: Session = Depends(get_db), _: User = Depends(require_permission("counts.create"))):
    session = session_row(db, count_id)
    if not session:
        fail(404, "Count session not found")
    return serialize_session(db, session)


@router.put("/{count_id}/entries")
def save_count_entries(count_id: str, payload: CountEntriesUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("counts.create"))):
    session = session_row(db, count_id, lock=True)
    if not session:
        fail(404, "Count session not found")
    if session.status != "open":
        fail(409, "Only open count sessions can be edited")
    by_item = {line.item_id: line for line in session.lines}
    unknown = [line.item_id for line in payload.lines if line.item_id not in by_item]
    if unknown:
        fail(422, "One or more items do not belong to this count session")
    for entry in payload.lines:
        row = by_item[entry.item_id]
        row.counted_quantity = entry.counted_quantity
        row.note = entry.note.strip() if entry.note else None
    add_audit(db, actor_user_id=user.id, action="count.entries_saved", entity_type="count_session", entity_id=session.id, details={"saved_lines": len(payload.lines)})
    db.commit()
    return serialize_session(db, session)


@router.post("/{count_id}/submit")
def submit_count(count_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission("counts.submit"))):
    session = session_row(db, count_id, lock=True)
    if not session:
        fail(404, "Count session not found")
    if session.status != "open":
        fail(409, "Only open count sessions can be submitted")
    missing = [line.item_id for line in session.lines if line.counted_quantity is None]
    if missing:
        fail(422, f"Count is incomplete: {len(missing)} item(s) remain uncounted")
    max_variance = max((abs(Decimal(line.counted_quantity) - Decimal(line.system_quantity)) for line in session.lines), default=Decimal("0"))
    try:
        if Decimal(session.approval_threshold) > 0 and max_variance > Decimal(session.approval_threshold):
            session.status = "pending_approval"
            add_audit(db, actor_user_id=user.id, action="count.approval_requested", entity_type="count_session", entity_id=session.id, details={"max_variance": str(max_variance)})
            add_notification(db, title="Count variance requires approval", message=f"{session.count_number} has a maximum quantity variance of {max_variance}.", severity="warning")
        else:
            finalize_count(db, session, user)
        db.commit()
        return serialize_session(db, session)
    except (InventoryError, IntegrityError) as exc:
        db.rollback()
        fail(409, str(exc))


@router.post("/{count_id}/recount")
def request_recount(count_id: str, payload: RecountRequest, db: Session = Depends(get_db), user: User = Depends(require_permission("counts.submit"))):
    session = session_row(db, count_id, lock=True)
    if not session:
        fail(404, "Count session not found")
    if session.status != "pending_approval":
        fail(409, "Only counts pending approval can be returned for recount")
    by_item = {line.item_id: line for line in session.lines}
    unknown = [item_id for item_id in payload.item_ids if item_id not in by_item]
    if unknown:
        fail(422, "One or more recount items do not belong to this session")
    for item_id in payload.item_ids:
        by_item[item_id].counted_quantity = None
        by_item[item_id].note = f"Recount requested: {payload.reason}"
    session.status = "open"
    session.approved_by_user_id = None
    session.approved_at = None
    add_audit(db, actor_user_id=user.id, action="count.recount_requested", entity_type="count_session", entity_id=session.id, details={"item_ids": payload.item_ids, "reason": payload.reason})
    db.commit()
    return serialize_session(db, session)


@router.post("/{count_id}/approve-guided")
def approve_guided_count(count_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission("counts.submit"))):
    session = session_row(db, count_id, lock=True)
    if not session:
        fail(404, "Count session not found")
    if session.status != "pending_approval":
        fail(409, "Count is not pending approval")
    if session.created_by_user_id == user.id:
        fail(409, "Count creator cannot approve their own variance")
    try:
        session.approved_by_user_id = user.id
        session.approved_at = datetime.now(timezone.utc)
        finalize_count(db, session, user)
        add_audit(db, actor_user_id=user.id, action="count.approved", entity_type="count_session", entity_id=session.id)
        db.commit()
        return serialize_session(db, session)
    except (InventoryError, IntegrityError) as exc:
        db.rollback()
        fail(409, str(exc))


@router.post("/{count_id}/cancel-guided")
def cancel_guided_count(count_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission("counts.submit"))):
    session = session_row(db, count_id, lock=True)
    if not session:
        fail(404, "Count session not found")
    if session.status not in {"open", "pending_approval"}:
        fail(409, "Only open or pending counts can be cancelled")
    session.status = "cancelled"
    add_audit(db, actor_user_id=user.id, action="count.cancelled", entity_type="count_session", entity_id=session.id)
    db.commit()
    return serialize_session(db, session)
