from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.inventory import Item, Location, StockBalance, StockDocument, StockMovement
from app.services.controls import add_audit, enqueue_event, next_document_number

class InventoryError(ValueError): pass

def _get_item(db: Session, item_id: str) -> Item:
    item = db.get(Item, item_id)
    if not item or not item.is_active or not item.track_stock: raise InventoryError("Invalid or inactive stock item")
    return item
def _get_location(db: Session, location_id: str) -> Location:
    location = db.get(Location, location_id)
    if not location or not location.is_active: raise InventoryError("Invalid or inactive location")
    return location
def _balance(db: Session, item_id: str, location_id: str) -> StockBalance:
    row = db.scalar(select(StockBalance).where(StockBalance.item_id == item_id, StockBalance.location_id == location_id).with_for_update())
    if row is None:
        row = StockBalance(item_id=item_id, location_id=location_id, quantity=Decimal("0"), average_cost=Decimal("0")); db.add(row); db.flush()
    return row

def post_document(db: Session, *, kind: str, actor_id: str, entries: list[dict], reference: str | None = None, notes: str | None = None, idempotency_key: str | None = None, commit: bool = True, allow_empty: bool = False) -> StockDocument:
    if idempotency_key:
        existing = db.scalar(select(StockDocument).where(StockDocument.idempotency_key == idempotency_key))
        if existing: return existing
    if not entries and not allow_empty: raise InventoryError("At least one stock line is required")
    doc = StockDocument(document_number=next_document_number(db,kind), document_type=kind, posted_by_user_id=actor_id, reference=reference, notes=notes, idempotency_key=idempotency_key)
    db.add(doc); db.flush()
    event_lines=[]
    for idx, entry in enumerate(entries, 1):
        item = _get_item(db, entry["item_id"]); _get_location(db, entry["location_id"])
        qty = Decimal(entry["quantity"]); cost = Decimal(entry.get("unit_cost", 0))
        if qty == 0: raise InventoryError("Movement quantity cannot be zero")
        source_location_id = entry.get("cost_from_location_id")
        if qty > 0 and cost == 0 and source_location_id:
            source_balance = _balance(db, item.id, source_location_id); cost = Decimal(source_balance.average_cost)
        bal = _balance(db, item.id, entry["location_id"]); new_qty = Decimal(bal.quantity) + qty
        if new_qty < 0 and not item.allow_negative_stock: raise InventoryError(f"Insufficient stock for {item.sku} at location")
        if qty > 0:
            current_value = Decimal(bal.quantity) * Decimal(bal.average_cost); incoming_value = qty * cost
            bal.average_cost = (current_value + incoming_value) / new_qty if new_qty else Decimal("0")
        bal.quantity = new_qty
        db.add(StockMovement(document_id=doc.id, line_number=idx, item_id=item.id, location_id=entry["location_id"], quantity=qty, unit_cost=cost, reason=entry.get("reason")))
        event_lines.append({'item_id':item.id,'location_id':entry['location_id'],'quantity':str(qty),'unit_cost':str(cost),'reason':entry.get('reason')})
    add_audit(db,actor_user_id=actor_id,action='stock.document_posted',entity_type='stock_document',entity_id=doc.id,details={'document_number':doc.document_number,'document_type':kind,'line_count':len(event_lines),'reference':reference})
    enqueue_event(db,destination_system='accounting',event_type='inventory.stock_document.posted',aggregate_type='stock_document',aggregate_id=doc.id,idempotency_key=f'stock-document:{doc.id}',payload={'document_id':doc.id,'document_number':doc.document_number,'document_type':kind,'reference':reference,'lines':event_lines})
    if not commit:
        db.flush(); return doc
    try: db.commit(); db.refresh(doc)
    except IntegrityError as exc:
        db.rollback()
        if idempotency_key:
            existing = db.scalar(select(StockDocument).where(StockDocument.idempotency_key == idempotency_key))
            if existing: return existing
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
