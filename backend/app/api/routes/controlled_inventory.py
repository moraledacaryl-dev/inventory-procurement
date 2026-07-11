from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.inventory import Item, Location, StockBalance, StockDocument, StockMovement
from app.models.inventory_operations import InventoryLot, LotBalance, StockReservation, TransferOrder
from app.models.user import User
from app.services.controls import add_audit, add_notification
from app.services.inventory import InventoryError, post_document

router = APIRouter(tags=["controlled-inventory"])

ADJUSTMENT_REASONS = {
    "opening_balance",
    "correction",
    "count_variance",
    "found_stock",
    "system_reconciliation",
    "other",
}
WASTE_REASONS = {
    "spoilage",
    "damage",
    "expired",
    "prep_waste",
    "quality_reject",
    "theft_loss",
    "other",
}


class AdjustmentLine(BaseModel):
    item_id: str
    quantity_delta: Decimal
    unit_cost: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def non_zero(self):
        if self.quantity_delta == 0:
            raise ValueError("Adjustment quantity cannot be zero")
        return self


class ControlledAdjustmentCreate(BaseModel):
    location_id: str
    reason_code: str
    reference: str | None = Field(default=None, max_length=120)
    notes: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=100)
    lines: list[AdjustmentLine] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_reason_and_lines(self):
        if self.reason_code not in ADJUSTMENT_REASONS:
            raise ValueError("Invalid adjustment reason")
        item_ids = [line.item_id for line in self.lines]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Duplicate item lines are not allowed")
        return self


class WasteCreate(BaseModel):
    item_id: str
    location_id: str
    quantity: Decimal = Field(gt=0)
    reason_code: str
    lot_id: str | None = None
    unit_cost: Decimal | None = Field(default=None, ge=0)
    reference: str | None = Field(default=None, max_length=120)
    notes: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_reason(self):
        if self.reason_code not in WASTE_REASONS:
            raise ValueError("Invalid waste reason")
        return self


class TransferReceiptLine(BaseModel):
    item_id: str
    received_quantity: Decimal = Field(ge=0)
    variance_reason: str | None = Field(default=None, max_length=240)


class TransferReceiptCreate(BaseModel):
    lines: list[TransferReceiptLine] = Field(min_length=1)
    notes: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def unique_items(self):
        item_ids = [line.item_id for line in self.lines]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Duplicate receipt lines are not allowed")
        return self


def fail(status: int, message: str):
    raise HTTPException(status_code=status, detail=message)


def now():
    return datetime.now(timezone.utc)


def balance_row(db: Session, item_id: str, location_id: str, lock: bool = False) -> StockBalance | None:
    stmt = select(StockBalance).where(StockBalance.item_id == item_id, StockBalance.location_id == location_id)
    if lock:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def average_cost(db: Session, item_id: str, location_id: str) -> Decimal:
    row = balance_row(db, item_id, location_id, lock=True)
    if row and Decimal(row.average_cost) > 0:
        return Decimal(row.average_cost)
    item = db.get(Item, item_id)
    return Decimal(item.standard_cost or 0) if item else Decimal("0")


def physical_quantity(db: Session, item_id: str, location_id: str) -> Decimal:
    row = balance_row(db, item_id, location_id)
    return Decimal(row.quantity) if row else Decimal("0")


def reserved_quantity(db: Session, item_id: str, location_id: str) -> Decimal:
    current = now()
    rows = db.scalars(
        select(StockReservation).where(
            StockReservation.item_id == item_id,
            StockReservation.location_id == location_id,
            StockReservation.status == "active",
        )
    ).all()
    return sum(
        (Decimal(row.quantity) for row in rows if row.expires_at is None or row.expires_at > current),
        Decimal("0"),
    )


def transit_location(db: Session) -> Location:
    location = db.scalar(select(Location).where(Location.code == "IN-TRANSIT"))
    if location:
        if not location.is_active:
            location.is_active = True
        return location
    location = Location(code="IN-TRANSIT", name="Inventory In Transit", location_type="transit", is_active=True)
    db.add(location)
    db.flush()
    return location


def transfer_row(db: Session, transfer_id: str, lock: bool = False) -> TransferOrder | None:
    stmt = select(TransferOrder).where(TransferOrder.id == transfer_id).options(selectinload(TransferOrder.lines))
    if lock:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def transfer_documents(db: Session, transfer_number: str) -> tuple[StockDocument | None, StockDocument | None]:
    dispatch = db.scalar(
        select(StockDocument)
        .where(StockDocument.reference == transfer_number, StockDocument.document_type == "transfer_dispatch")
        .order_by(StockDocument.posted_at.desc())
    )
    receipt = db.scalar(
        select(StockDocument)
        .where(StockDocument.reference == transfer_number, StockDocument.document_type == "transfer_receipt")
        .order_by(StockDocument.posted_at.desc())
    )
    return dispatch, receipt


def transfer_payload(db: Session, row: TransferOrder) -> dict:
    source = db.get(Location, row.source_location_id)
    destination = db.get(Location, row.destination_location_id)
    item_ids = {line.item_id for line in row.lines}
    items = {item.id: item for item in db.scalars(select(Item).where(Item.id.in_(item_ids))).all()} if item_ids else {}
    dispatch_doc, receipt_doc = transfer_documents(db, row.transfer_number)
    received_by_item: dict[str, Decimal] = {}
    if receipt_doc:
        movement_rows = db.scalars(
            select(StockMovement).where(
                StockMovement.document_id == receipt_doc.id,
                StockMovement.location_id == row.destination_location_id,
                StockMovement.quantity > 0,
            )
        ).all()
        for movement in movement_rows:
            received_by_item[movement.item_id] = received_by_item.get(movement.item_id, Decimal("0")) + Decimal(movement.quantity)

    lines = []
    total_requested = Decimal("0")
    total_received = Decimal("0")
    for line in row.lines:
        requested = Decimal(line.quantity)
        received = received_by_item.get(line.item_id, requested if row.status == "received" and not receipt_doc else Decimal("0"))
        variance = requested - received
        total_requested += requested
        total_received += received
        item = items.get(line.item_id)
        lines.append({
            "item_id": line.item_id,
            "sku": item.sku if item else line.item_id,
            "item_name": item.name if item else "Unknown item",
            "requested_quantity": str(requested),
            "received_quantity": str(received),
            "variance_quantity": str(variance),
        })

    return {
        "id": row.id,
        "transfer_number": row.transfer_number,
        "source_location_id": row.source_location_id,
        "source_location_code": source.code if source else row.source_location_id,
        "source_location_name": source.name if source else "Unknown source",
        "destination_location_id": row.destination_location_id,
        "destination_location_code": destination.code if destination else row.destination_location_id,
        "destination_location_name": destination.name if destination else "Unknown destination",
        "status": row.status,
        "notes": row.notes,
        "created_at": row.created_at.isoformat(),
        "dispatched_at": row.dispatched_at.isoformat() if row.dispatched_at else None,
        "received_at": row.received_at.isoformat() if row.received_at else None,
        "dispatch_document_id": dispatch_doc.id if dispatch_doc else None,
        "dispatch_document_number": dispatch_doc.document_number if dispatch_doc else None,
        "receipt_document_id": receipt_doc.id if receipt_doc else row.stock_document_id,
        "receipt_document_number": receipt_doc.document_number if receipt_doc else None,
        "requested_quantity": str(total_requested),
        "received_quantity": str(total_received),
        "variance_quantity": str(total_requested - total_received),
        "lines": lines,
    }


@router.get("/inventory-controls/adjustments")
def list_controlled_adjustments(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.read")),
):
    rows = db.execute(
        select(StockDocument, StockMovement, Item, Location)
        .join(StockMovement, StockMovement.document_id == StockDocument.id)
        .join(Item, Item.id == StockMovement.item_id)
        .join(Location, Location.id == StockMovement.location_id)
        .where(StockDocument.document_type == "adjustment")
        .order_by(StockDocument.posted_at.desc(), StockMovement.line_number)
        .limit(limit)
    ).all()
    return [
        {
            "document_id": document.id,
            "document_number": document.document_number,
            "posted_at": document.posted_at.isoformat(),
            "reference": document.reference,
            "notes": document.notes,
            "item_id": item.id,
            "sku": item.sku,
            "item_name": item.name,
            "location_id": location.id,
            "location_code": location.code,
            "location_name": location.name,
            "quantity_delta": str(movement.quantity),
            "unit_cost": str(movement.unit_cost),
            "value_delta": str(Decimal(movement.quantity) * Decimal(movement.unit_cost)),
            "reason": movement.reason,
        }
        for document, movement, item, location in rows
    ]


@router.post("/inventory-controls/adjustments", status_code=201)
def create_controlled_adjustment(
    payload: ControlledAdjustmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.*")),
):
    location = db.get(Location, payload.location_id)
    if not location or not location.is_active:
        fail(422, "Active location not found")

    entries = []
    for line in payload.lines:
        item = db.get(Item, line.item_id)
        if not item or not item.is_active or not item.track_stock:
            fail(422, "Invalid or inactive stock item")
        cost = Decimal(line.unit_cost) if line.unit_cost is not None else average_cost(db, item.id, location.id)
        if line.quantity_delta > 0 and cost == 0:
            cost = Decimal(item.standard_cost or 0)
        entries.append({
            "item_id": item.id,
            "location_id": location.id,
            "quantity": Decimal(line.quantity_delta),
            "unit_cost": cost,
            "reason": payload.reason_code,
        })

    try:
        document = post_document(
            db,
            kind="adjustment",
            actor_id=user.id,
            entries=entries,
            reference=payload.reference,
            notes=payload.notes,
            idempotency_key=payload.idempotency_key,
            commit=False,
        )
        add_audit(
            db,
            actor_user_id=user.id,
            action="inventory.adjustment_recorded",
            entity_type="stock_document",
            entity_id=document.id,
            details={"reason_code": payload.reason_code, "line_count": len(entries)},
        )
        db.commit()
        return {
            "document_id": document.id,
            "document_number": document.document_number,
            "reason_code": payload.reason_code,
            "line_count": len(entries),
        }
    except (InventoryError, IntegrityError) as exc:
        db.rollback()
        fail(409, str(exc))


@router.get("/inventory-controls/waste")
def list_waste_events(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.read")),
):
    rows = db.execute(
        select(StockDocument, StockMovement, Item, Location)
        .join(StockMovement, StockMovement.document_id == StockDocument.id)
        .join(Item, Item.id == StockMovement.item_id)
        .join(Location, Location.id == StockMovement.location_id)
        .where(StockDocument.document_type == "waste")
        .order_by(StockDocument.posted_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "document_id": document.id,
            "document_number": document.document_number,
            "posted_at": document.posted_at.isoformat(),
            "reference": document.reference,
            "item_id": item.id,
            "sku": item.sku,
            "item_name": item.name,
            "location_id": location.id,
            "location_code": location.code,
            "location_name": location.name,
            "quantity": str(-Decimal(movement.quantity)),
            "unit_cost": str(movement.unit_cost),
            "value": str(-Decimal(movement.quantity) * Decimal(movement.unit_cost)),
            "reason_code": movement.reason,
            "notes": document.notes,
        }
        for document, movement, item, location in rows
    ]


@router.post("/inventory-controls/waste", status_code=201)
def create_waste_event(
    payload: WasteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.*")),
):
    item = db.get(Item, payload.item_id)
    location = db.get(Location, payload.location_id)
    if not item or not item.is_active or not item.track_stock:
        fail(422, "Invalid or inactive stock item")
    if not location or not location.is_active:
        fail(422, "Active location not found")

    lot = None
    lot_balance = None
    if payload.lot_id:
        lot = db.get(InventoryLot, payload.lot_id)
        if not lot or lot.item_id != item.id:
            fail(422, "Lot does not belong to the selected item")
        lot_balance = db.scalar(
            select(LotBalance)
            .where(LotBalance.lot_id == lot.id, LotBalance.location_id == location.id)
            .with_for_update()
        )
        if not lot_balance or Decimal(lot_balance.quantity) < payload.quantity:
            fail(409, "Insufficient quantity in the selected lot")

    cost = Decimal(payload.unit_cost) if payload.unit_cost is not None else average_cost(db, item.id, location.id)
    reference = payload.reference or (lot.lot_number if lot else None)
    try:
        document = post_document(
            db,
            kind="waste",
            actor_id=user.id,
            entries=[{
                "item_id": item.id,
                "location_id": location.id,
                "quantity": -payload.quantity,
                "unit_cost": cost,
                "reason": payload.reason_code,
            }],
            reference=reference,
            notes=payload.notes,
            idempotency_key=payload.idempotency_key,
            commit=False,
        )
        if lot_balance:
            lot_balance.quantity = Decimal(lot_balance.quantity) - payload.quantity
        add_audit(
            db,
            actor_user_id=user.id,
            action="inventory.waste_recorded",
            entity_type="stock_document",
            entity_id=document.id,
            details={
                "reason_code": payload.reason_code,
                "item_id": item.id,
                "location_id": location.id,
                "lot_id": lot.id if lot else None,
                "quantity": str(payload.quantity),
                "value": str(payload.quantity * cost),
            },
        )
        add_notification(
            db,
            title="Inventory write-off recorded",
            message=f"{payload.quantity} {item.sku} was recorded as {payload.reason_code.replace('_', ' ')} at {location.code}.",
            severity="warning",
        )
        db.commit()
        return {
            "document_id": document.id,
            "document_number": document.document_number,
            "quantity": str(payload.quantity),
            "value": str(payload.quantity * cost),
            "lot_quantity": str(lot_balance.quantity) if lot_balance else None,
        }
    except (InventoryError, IntegrityError) as exc:
        db.rollback()
        fail(409, str(exc))


@router.get("/transfer-orders/workspace")
def transfer_workspace(
    status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.read")),
):
    stmt = select(TransferOrder).options(selectinload(TransferOrder.lines)).order_by(TransferOrder.created_at.desc())
    if status:
        stmt = stmt.where(TransferOrder.status == status)
    return [transfer_payload(db, row) for row in db.scalars(stmt).unique().all()]


@router.get("/transfer-orders/{transfer_id}/detail")
def transfer_detail(
    transfer_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.read")),
):
    row = transfer_row(db, transfer_id)
    if not row:
        fail(404, "Transfer order not found")
    return transfer_payload(db, row)


@router.post("/transfer-orders/{transfer_id}/dispatch")
def dispatch_transfer_controlled(
    transfer_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.*")),
):
    row = transfer_row(db, transfer_id, lock=True)
    if not row:
        fail(404, "Transfer order not found")
    if row.status != "draft":
        fail(409, "Only draft transfers can be dispatched")

    transit = transit_location(db)
    entries = []
    for line in row.lines:
        available = physical_quantity(db, line.item_id, row.source_location_id) - reserved_quantity(db, line.item_id, row.source_location_id)
        if Decimal(line.quantity) > available:
            item = db.get(Item, line.item_id)
            fail(409, f"Insufficient available stock for {item.sku if item else line.item_id}")
        cost = average_cost(db, line.item_id, row.source_location_id)
        entries.extend([
            {
                "item_id": line.item_id,
                "location_id": row.source_location_id,
                "quantity": -Decimal(line.quantity),
                "unit_cost": cost,
                "reason": "transfer dispatch out",
            },
            {
                "item_id": line.item_id,
                "location_id": transit.id,
                "quantity": Decimal(line.quantity),
                "unit_cost": cost,
                "reason": "transfer in transit",
            },
        ])

    try:
        document = post_document(
            db,
            kind="transfer_dispatch",
            actor_id=user.id,
            entries=entries,
            reference=row.transfer_number,
            notes=row.notes,
            idempotency_key=f"transfer-dispatch:{row.id}",
            commit=False,
        )
        row.status = "dispatched"
        row.dispatched_by_user_id = user.id
        row.dispatched_at = now()
        add_audit(
            db,
            actor_user_id=user.id,
            action="transfer_order.dispatched",
            entity_type="transfer_order",
            entity_id=row.id,
            details={"dispatch_document_id": document.id, "transit_location_id": transit.id},
        )
        db.commit()
        return transfer_payload(db, row)
    except (InventoryError, IntegrityError) as exc:
        db.rollback()
        fail(409, str(exc))


@router.post("/transfer-orders/{transfer_id}/receive")
def receive_transfer_controlled(
    transfer_id: str,
    payload: TransferReceiptCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.*")),
):
    row = transfer_row(db, transfer_id, lock=True)
    if not row:
        fail(404, "Transfer order not found")
    if row.status != "dispatched":
        fail(409, "Only dispatched transfers can be received")

    request_by_item = {line.item_id: Decimal(line.quantity) for line in row.lines}
    received_by_item = {line.item_id: line for line in payload.lines}
    if set(received_by_item) != set(request_by_item):
        fail(422, "Receipt must include every transfer item exactly once")
    for item_id, receipt_line in received_by_item.items():
        if receipt_line.received_quantity > request_by_item[item_id]:
            fail(422, "Received quantity cannot exceed dispatched quantity")
        if receipt_line.received_quantity < request_by_item[item_id] and not receipt_line.variance_reason:
            fail(422, "A variance reason is required for shortages or rejected quantities")

    transit = transit_location(db)
    dispatch_doc, _ = transfer_documents(db, row.transfer_number)
    entries = []
    variance_details = []
    total_variance = Decimal("0")

    for line in row.lines:
        requested = Decimal(line.quantity)
        receipt_line = received_by_item[line.item_id]
        received = Decimal(receipt_line.received_quantity)
        variance = requested - received
        total_variance += variance

        if dispatch_doc:
            cost = average_cost(db, line.item_id, transit.id)
            if received > 0:
                entries.extend([
                    {
                        "item_id": line.item_id,
                        "location_id": transit.id,
                        "quantity": -received,
                        "unit_cost": cost,
                        "reason": "transfer received from transit",
                    },
                    {
                        "item_id": line.item_id,
                        "location_id": row.destination_location_id,
                        "quantity": received,
                        "unit_cost": cost,
                        "reason": "transfer received",
                    },
                ])
            if variance > 0:
                entries.append({
                    "item_id": line.item_id,
                    "location_id": transit.id,
                    "quantity": -variance,
                    "unit_cost": cost,
                    "reason": f"transfer variance: {receipt_line.variance_reason}",
                })
        else:
            cost = average_cost(db, line.item_id, row.source_location_id)
            entries.append({
                "item_id": line.item_id,
                "location_id": row.source_location_id,
                "quantity": -requested,
                "unit_cost": cost,
                "reason": "legacy transfer dispatch reconciliation",
            })
            if received > 0:
                entries.append({
                    "item_id": line.item_id,
                    "location_id": row.destination_location_id,
                    "quantity": received,
                    "unit_cost": cost,
                    "reason": "transfer received",
                })

        variance_details.append({
            "item_id": line.item_id,
            "requested_quantity": str(requested),
            "received_quantity": str(received),
            "variance_quantity": str(variance),
            "variance_reason": receipt_line.variance_reason,
        })

    try:
        document = post_document(
            db,
            kind="transfer_receipt",
            actor_id=user.id,
            entries=entries,
            reference=row.transfer_number,
            notes=payload.notes,
            idempotency_key=payload.idempotency_key or f"transfer-receipt:{row.id}",
            commit=False,
        )
        row.status = "received_with_variance" if total_variance else "received"
        row.received_by_user_id = user.id
        row.received_at = now()
        row.stock_document_id = document.id
        add_audit(
            db,
            actor_user_id=user.id,
            action="transfer_order.received",
            entity_type="transfer_order",
            entity_id=row.id,
            details={
                "receipt_document_id": document.id,
                "total_variance": str(total_variance),
                "lines": variance_details,
            },
        )
        if total_variance:
            add_notification(
                db,
                title="Transfer received with variance",
                message=f"{row.transfer_number} has a total quantity variance of {total_variance}.",
                severity="warning",
            )
        db.commit()
        return transfer_payload(db, row)
    except (InventoryError, IntegrityError) as exc:
        db.rollback()
        fail(409, str(exc))


@router.post("/transfer-orders/{transfer_id}/cancel")
def cancel_transfer(
    transfer_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.*")),
):
    row = transfer_row(db, transfer_id, lock=True)
    if not row:
        fail(404, "Transfer order not found")
    if row.status != "draft":
        fail(409, "Only draft transfers can be cancelled")
    row.status = "cancelled"
    add_audit(
        db,
        actor_user_id=user.id,
        action="transfer_order.cancelled",
        entity_type="transfer_order",
        entity_id=row.id,
    )
    db.commit()
    return transfer_payload(db, row)
