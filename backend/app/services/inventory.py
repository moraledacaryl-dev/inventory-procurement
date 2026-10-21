from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.roles import has_permission
from app.models.inventory import CountSession, Item, Location, StockBalance, StockDocument, StockMovement
from app.services.controls import add_audit, enqueue_event, next_document_number

class InventoryError(ValueError): pass


def count_requires_approval(*, role: str, max_variance: Decimal, approval_threshold: Decimal) -> bool:
    """A count-only operator cannot post an adjustment by choosing a permissive threshold.

    Variance-free counts do not mutate stock. Roles allowed to approve counts retain
    the configured threshold behavior; any nonzero Counter variance requires review.
    """
    variance = Decimal(max_variance)
    threshold = Decimal(approval_threshold)
    return (
        (variance > 0 and not has_permission(role, "counts.approve"))
        or (threshold > 0 and variance > threshold)
    )


def _number(value) -> str:
    number = Decimal(str(value if value is not None else 0))
    if not number.is_finite():
        raise InventoryError("Movement quantity and unit cost must be finite")
    return str(number.normalize()) if number else "0"


def _request_fingerprint(*, kind: str, actor_id: str, entries: list[dict],
                         reference: str | None, notes: str | None,
                         allow_empty: bool) -> str:
    # Bind a retry key to the supplied request, not the computed book cost.
    body = {
        "kind": kind, "actor_id": actor_id, "reference": reference,
        "notes": notes, "allow_empty": allow_empty,
        "entries": [
            {
                "item_id": str(line["item_id"]),
                "location_id": str(line["location_id"]),
                "quantity": _number(line["quantity"]),
                "unit_cost": _number(line.get("unit_cost", 0)),
                "reason": line.get("reason"),
                "cost_from_location_id": line.get("cost_from_location_id"),
            }
            for line in entries
        ],
    }
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _verified_replay(existing: StockDocument, *, fingerprint: str, kind: str,
                     actor_id: str, reference: str | None, notes: str | None,
                     entries: list[dict]) -> StockDocument:
    if existing.request_fingerprint:
        if existing.request_fingerprint != fingerprint:
            raise InventoryError("Idempotency key was already used for a different stock request")
        return existing

    # Historical documents predate fingerprints. Permit matching replays only.
    movements = sorted(existing.movements, key=lambda line: line.line_number)
    matches = (
        existing.document_type == kind
        and existing.posted_by_user_id == actor_id
        and existing.reference == reference
        and existing.notes == notes
        and len(movements) == len(entries)
    )
    if matches:
        for movement, request in zip(movements, entries):
            qty = _number(request["quantity"])
            supplied_cost = _number(request.get("unit_cost", 0))
            if (
                movement.item_id != request["item_id"]
                or movement.location_id != request["location_id"]
                or _number(movement.quantity) != qty
                or movement.reason != request.get("reason")
            ):
                matches = False
                break
            computed_cost = (
                Decimal(qty) < 0
                or bool(request.get("cost_from_location_id"))
                or (kind in {"adjustment", "count_adjustment"} and Decimal(supplied_cost) == 0)
            )
            if not computed_cost and _number(movement.unit_cost) != supplied_cost:
                matches = False
                break
    if not matches:
        raise InventoryError("Idempotency key was already used for a different stock request")
    return existing

def _get_item(db: Session, item_id: str) -> Item:
    item = db.get(Item, item_id)
    if not item or not item.is_active or not item.track_stock: raise InventoryError("Invalid or inactive stock item")
    return item
def _get_location(db: Session, location_id: str) -> Location:
    location = db.get(Location, location_id)
    if not location or not location.is_active: raise InventoryError("Invalid or inactive location")
    return location
def _balance(db: Session, item_id: str, location_id: str) -> StockBalance:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("select pg_advisory_xact_lock(hashtext(:key))"),
                   {"key": f"stock-balance:{item_id}:{location_id}"})
    row = db.scalar(select(StockBalance).where(StockBalance.item_id == item_id, StockBalance.location_id == location_id).with_for_update())
    if row is None:
        row = StockBalance(item_id=item_id, location_id=location_id, quantity=Decimal("0"), average_cost=Decimal("0")); db.add(row); db.flush()
    return row

def assert_count_snapshot_current(db: Session, session: CountSession) -> None:
    """Lock counted item balances and reject posting against a stale count.

    Lock acquisition follows item ID order and uses the same advisory/row locks
    as every stock document. These locks must remain held until the caller
    commits both the physical-count status and its adjustment document.
    """
    for line in sorted(session.lines, key=lambda row: row.item_id):
        if line.counted_quantity is None:
            continue
        balance = _balance(db, line.item_id, session.location_id)
        if Decimal(balance.quantity) != Decimal(line.system_quantity):
            raise InventoryError(
                "Stock changed since this count started; create a new physical count"
            )
        # A sale followed by a receipt can restore the same balance; that still
        # makes the original count window ambiguous and requires a fresh count.
        newer_movement = db.scalar(
            select(StockMovement.id)
            .where(
                StockMovement.item_id == line.item_id,
                StockMovement.location_id == session.location_id,
                StockMovement.created_at >= session.created_at,
            )
            .limit(1)
        )
        if newer_movement is not None:
            raise InventoryError(
                "Stock moved after this count started; create a new physical count"
            )


def post_document(db: Session, *, kind: str, actor_id: str, entries: list[dict], reference: str | None = None, notes: str | None = None, idempotency_key: str | None = None, commit: bool = True, allow_empty: bool = False) -> StockDocument:
    if not entries and not allow_empty: raise InventoryError("At least one stock line is required")
    fingerprint = _request_fingerprint(
        kind=kind, actor_id=actor_id, entries=entries,
        reference=reference, notes=notes, allow_empty=allow_empty,
    )
    if idempotency_key:
        if db.bind is not None and db.bind.dialect.name == 'postgresql':
            db.execute(text('select pg_advisory_xact_lock(hashtext(:key))'), {'key': idempotency_key})
        existing = db.scalar(select(StockDocument).where(StockDocument.idempotency_key == idempotency_key))
        if existing:
            return _verified_replay(existing, fingerprint=fingerprint, kind=kind,
                                    actor_id=actor_id, reference=reference,
                                    notes=notes, entries=entries)
    doc = StockDocument(document_number=next_document_number(db,kind), document_type=kind, posted_by_user_id=actor_id, reference=reference, notes=notes, idempotency_key=idempotency_key, request_fingerprint=fingerprint)
    db.add(doc); db.flush()
    event_lines=[]
    for idx, entry in enumerate(entries, 1):
        item = _get_item(db, entry["item_id"]); _get_location(db, entry["location_id"])
        # Match the ledger's Numeric(18, 4) storage precision before
        # calculating value changes; avoid a misleading in-memory precision.
        precision = Decimal("0.0001")
        qty = Decimal(entry["quantity"]).quantize(precision, rounding=ROUND_HALF_UP)
        cost = Decimal(entry.get("unit_cost", 0)).quantize(precision, rounding=ROUND_HALF_UP)
        if qty == 0: raise InventoryError("Movement quantity cannot be zero at stock precision")
        if cost < 0: raise InventoryError("Movement unit cost cannot be negative")
        source_location_id = entry.get("cost_from_location_id")
        bal = _balance(db, item.id, entry["location_id"])
        old_qty = Decimal(bal.quantity)
        old_cost = Decimal(bal.average_cost)
        old_book_value = old_qty * old_cost
        if qty < 0:
            cost = old_cost
        elif kind in {"adjustment", "count_adjustment"} and cost == 0:
            # Found inventory is not free: keep its existing valuation, or use
            # the item standard cost when this location has no valuation yet.
            cost = old_cost or Decimal(item.standard_cost)
        elif source_location_id:
            # Transfers carry the source's book value, never a supplied line price.
            source_balance = _balance(db, item.id, source_location_id)
            cost = Decimal(source_balance.average_cost)
        cost = cost.quantize(precision, rounding=ROUND_HALF_UP)
        new_qty = old_qty + qty
        if new_qty < 0 and not item.allow_negative_stock: raise InventoryError(f"Insufficient stock for {item.sku} at location")
        if qty > 0:
            incoming_value = qty * cost
            if old_qty < 0:
                # A negative shortage covered by fresh stock requires a
                # replacement cost once positive, not a negative-cost average.
                next_cost = cost if new_qty > 0 else old_cost
            else:
                next_cost = (old_book_value + incoming_value) / new_qty if new_qty else Decimal("0")
            bal.average_cost = next_cost.quantize(precision, rounding=ROUND_HALF_UP)
        bal.quantity = new_qty
        # A revaluation occurs when negative stock becomes positive at a new
        # replacement cost. quantity * unit_cost alone is not the change in
        # actual book value. Capture the real balance transition instead.
        book_value_delta = new_qty * Decimal(bal.average_cost) - old_book_value
        db.add(StockMovement(document_id=doc.id, line_number=idx, item_id=item.id,
                             location_id=entry["location_id"], quantity=qty,
                             unit_cost=cost, book_value_delta=book_value_delta,
                             reason=entry.get("reason")))
        event_lines.append({'item_id':item.id,'location_id':entry['location_id'],'quantity':str(qty),'unit_cost':str(cost),
                            'book_value_delta':str(book_value_delta),'reason':entry.get('reason')})
    add_audit(db,actor_user_id=actor_id,action='stock.document_posted',entity_type='stock_document',entity_id=doc.id,details={'document_number':doc.document_number,'document_type':kind,'line_count':len(event_lines),'reference':reference})
    enqueue_event(db,destination_system='accounting',event_type='inventory.stock_document.posted',aggregate_type='stock_document',aggregate_id=doc.id,idempotency_key=f'stock-document:{doc.id}',payload={'document_id':doc.id,'document_number':doc.document_number,'document_type':kind,'reference':reference,'lines':event_lines})
    if not commit:
        db.flush(); return doc
    try: db.commit(); db.refresh(doc)
    except IntegrityError as exc:
        db.rollback()
        if idempotency_key:
            existing = db.scalar(select(StockDocument).where(StockDocument.idempotency_key == idempotency_key))
            if existing:
                return _verified_replay(existing, fingerprint=fingerprint, kind=kind,
                                        actor_id=actor_id, reference=reference,
                                        notes=notes, entries=entries)
        raise InventoryError("Stock document could not be posted") from exc
    return doc

def receipt_entries(location_id: str, lines): return [{"item_id":x.item_id,"location_id":location_id,"quantity":x.quantity,"unit_cost":x.unit_cost,"reason":x.reason or "receipt"} for x in lines]
def issue_entries(location_id: str, lines): return [{"item_id":x.item_id,"location_id":location_id,"quantity":-x.quantity,"unit_cost":x.unit_cost,"reason":x.reason or "issue"} for x in lines]
def transfer_entries(source: str, destination: str, lines):
    if source == destination: raise InventoryError("Source and destination locations must differ")
    entries=[]
    for x in lines:
        entries += [
            {"item_id":x.item_id,"location_id":source,"quantity":-x.quantity,"unit_cost":x.unit_cost,"reason":x.reason or "transfer out"},
            {"item_id":x.item_id,"location_id":destination,"quantity":x.quantity,"unit_cost":x.unit_cost,"cost_from_location_id":source,"reason":x.reason or "transfer in"},
        ]
    return entries