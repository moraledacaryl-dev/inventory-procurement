from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.inventory import Item, Location, StockDocument, StockMovement
from app.models.user import User
from app.services.operational_authorization import require_scoped_locations, visible_location_ids

router = APIRouter(prefix="/stock", tags=["stock-ledger"])


def fail(status: int, message: str):
    raise HTTPException(status_code=status, detail=message)


@router.get("/ledger")
def stock_ledger(
    item_id: str | None = None,
    location_id: str | None = None,
    document_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(250, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.read")),
):
    allowed = visible_location_ids(db, user)
    if location_id:
        require_scoped_locations(db, user, {location_id})
    filters = []
    if allowed is not None:
        # Apply the restriction in SQL so prices, totals and counts cannot leak.
        filters.append(StockMovement.location_id.in_(allowed))
    if item_id:
        filters.append(StockMovement.item_id == item_id)
    if location_id:
        filters.append(StockMovement.location_id == location_id)
    if document_type:
        filters.append(StockDocument.document_type == document_type)
    if date_from:
        filters.append(StockMovement.created_at >= date_from)
    if date_to:
        filters.append(StockMovement.created_at <= date_to)

    rows = db.execute(
        select(StockMovement, StockDocument, Item, Location)
        .join(StockDocument, StockDocument.id == StockMovement.document_id)
        .join(Item, Item.id == StockMovement.item_id)
        .join(Location, Location.id == StockMovement.location_id)
        .where(*filters)
        .order_by(StockMovement.created_at, StockDocument.document_number, StockMovement.line_number)
        .limit(limit)
    ).all()

    running: dict[tuple[str, str], Decimal] = {}
    result = []
    for movement, document, item, location in rows:
        key = (movement.item_id, movement.location_id)
        running[key] = running.get(key, Decimal("0")) + Decimal(movement.quantity)
        result.append({
            "id": movement.id,
            "document_id": document.id,
            "document_number": document.document_number,
            "document_type": document.document_type,
            "document_status": document.status,
            "reference": document.reference,
            "item_id": item.id,
            "sku": item.sku,
            "item_name": item.name,
            "location_id": location.id,
            "location_code": location.code,
            "location_name": location.name,
            "quantity": str(movement.quantity),
            "unit_cost": str(movement.unit_cost),
            "line_value": str(Decimal(movement.quantity) * Decimal(movement.unit_cost)),
            "book_value_change": str(movement.book_value_delta) if movement.book_value_delta is not None else None,
            "valuation_difference": str(
                Decimal(movement.book_value_delta) - Decimal(movement.quantity) * Decimal(movement.unit_cost)
            ) if movement.book_value_delta is not None else None,
            "running_quantity": str(running[key]),
            "reason": movement.reason,
            "created_at": movement.created_at.isoformat(),
            "posted_at": document.posted_at.isoformat(),
        })

    total_quantity = sum((Decimal(row["quantity"]) for row in result), Decimal("0"))
    total_value = sum((Decimal(row["line_value"]) for row in result), Decimal("0"))
    missing_book_values = sum(row["book_value_change"] is None for row in result)
    actual_book_change = sum((Decimal(row["book_value_change"]) for row in result
                              if row["book_value_change"] is not None), Decimal("0"))
    return {
        "filters": {
            "item_id": item_id,
            "location_id": location_id,
            "document_type": document_type,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "limit": limit,
        },
        "summary": {
            "movement_count": len(result),
            "net_quantity": str(total_quantity),
            "net_value": str(total_value),
            "book_value_change": str(actual_book_change) if not missing_book_values else None,
            "legacy_unverified_value_lines": missing_book_values,
            "document_count": len({row["document_id"] for row in result}),
        },
        "rows": result,
    }


@router.get("/documents/{document_id}")
def stock_document_detail(
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.read")),
):
    document = db.scalar(
        select(StockDocument)
        .where(StockDocument.id == document_id)
        .options(selectinload(StockDocument.movements))
    )
    if not document:
        fail(404, "Stock document not found")
    allowed = visible_location_ids(db, user)
    document_locations = {row.location_id for row in document.movements}
    if allowed is not None and (not document_locations or not document_locations.issubset(allowed)):
        # Multi-location transfers are atomic: never expose a partial document
        # or its unredacted totals to a user scoped to just one side.
        fail(403, "Operational access scope does not authorize this stock document")

    item_ids = {row.item_id for row in document.movements}
    location_ids = {row.location_id for row in document.movements}
    items = {row.id: row for row in db.scalars(select(Item).where(Item.id.in_(item_ids))).all()} if item_ids else {}
    locations = {row.id: row for row in db.scalars(select(Location).where(Location.id.in_(location_ids))).all()} if location_ids else {}

    total_value = sum((Decimal(row.quantity) * Decimal(row.unit_cost) for row in document.movements), Decimal("0"))
    all_book_values = all(line.book_value_delta is not None for line in document.movements)
    book_delta = sum((Decimal(line.book_value_delta) for line in document.movements
                      if line.book_value_delta is not None), Decimal("0"))
    return {
        "document": {
            "id": document.id,
            "document_number": document.document_number,
            "document_type": document.document_type,
            "status": document.status,
            "reference": document.reference,
            "notes": document.notes,
            "posted_by_user_id": document.posted_by_user_id,
            "posted_at": document.posted_at.isoformat(),
            "reversed_document_id": document.reversed_document_id,
            "idempotency_key": document.idempotency_key,
        },
        "summary": {
            "line_count": len(document.movements),
            "net_quantity": str(sum((Decimal(row.quantity) for row in document.movements), Decimal("0"))),
            "net_value": str(total_value),
            "book_value_change": str(book_delta) if all_book_values else None,
            "legacy_unverified_value_lines": sum(line.book_value_delta is None for line in document.movements),
        },
        "lines": [
            {
                "id": row.id,
                "line_number": row.line_number,
                "item_id": row.item_id,
                "sku": items[row.item_id].sku,
                "item_name": items[row.item_id].name,
                "location_id": row.location_id,
                "location_code": locations[row.location_id].code,
                "location_name": locations[row.location_id].name,
                "quantity": str(row.quantity),
                "unit_cost": str(row.unit_cost),
                "line_value": str(Decimal(row.quantity) * Decimal(row.unit_cost)),
                "book_value_change": str(row.book_value_delta) if row.book_value_delta is not None else None,
                "valuation_difference": str(
                    Decimal(row.book_value_delta) - Decimal(row.quantity) * Decimal(row.unit_cost)
                ) if row.book_value_delta is not None else None,
                "reason": row.reason,
                "created_at": row.created_at.isoformat(),
            }
            for row in sorted(document.movements, key=lambda movement: movement.line_number)
        ],
    }
