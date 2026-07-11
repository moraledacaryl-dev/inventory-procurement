from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.inventory import Item, Location, StockDocument
from app.models.inventory_operations import InventoryLot, LotBalance
from app.models.procurement import GoodsReceipt, GoodsReceiptLine, PurchaseOrder, PurchaseReturn, Supplier
from app.models.user import User
from app.services.controls import add_audit, add_notification, enqueue_event, next_document_number
from app.services.inventory import InventoryError, post_document

router = APIRouter(tags=["receiving-workspace"])


class ReceivingLine(BaseModel):
    purchase_order_line_id: str
    received_quantity: Decimal = Field(gt=0)
    accepted_quantity: Decimal = Field(ge=0)
    rejected_quantity: Decimal = Field(ge=0)
    discrepancy_reason: str | None = Field(default=None, max_length=240)
    lot_number: str | None = Field(default=None, max_length=100)
    manufactured_date: date | None = None
    expiry_date: date | None = None

    @model_validator(mode="after")
    def validate_quantities(self):
        if self.accepted_quantity + self.rejected_quantity != self.received_quantity:
            raise ValueError("Accepted plus rejected quantity must equal received quantity")
        if self.rejected_quantity > 0 and not self.discrepancy_reason:
            raise ValueError("Rejected quantities require a discrepancy reason")
        if self.expiry_date and self.manufactured_date and self.expiry_date < self.manufactured_date:
            raise ValueError("Expiry date cannot be before manufactured date")
        return self


class ControlledReceiptCreate(BaseModel):
    delivery_reference: str = Field(min_length=1, max_length=120)
    notes: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=100)
    lines: list[ReceivingLine] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_lines(self):
        ids = [line.purchase_order_line_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate purchase order lines are not allowed")
        return self


class ReturnLine(BaseModel):
    purchase_order_line_id: str
    quantity: Decimal = Field(gt=0)


class ControlledReturnCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=240)
    supplier_reference: str | None = Field(default=None, max_length=120)
    notes: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=100)
    lines: list[ReturnLine] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_lines(self):
        ids = [line.purchase_order_line_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate purchase order lines are not allowed")
        return self


def fail(status: int, message: str):
    raise HTTPException(status_code=status, detail=message)


def load_po(db: Session, po_id: str, lock: bool = False):
    stmt = select(PurchaseOrder).where(PurchaseOrder.id == po_id).options(selectinload(PurchaseOrder.lines))
    if lock:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def receipt_payload(db: Session, receipt: GoodsReceipt) -> dict:
    po = load_po(db, receipt.purchase_order_id)
    supplier = db.get(Supplier, po.supplier_id) if po else None
    location = db.get(Location, po.delivery_location_id) if po else None
    item_ids = {line.item_id for line in receipt.lines}
    items = {row.id: row for row in db.scalars(select(Item).where(Item.id.in_(item_ids))).all()} if item_ids else {}
    received_value = sum((Decimal(line.received_quantity) * Decimal(line.unit_cost) for line in receipt.lines), Decimal("0"))
    accepted_value = sum((Decimal(line.accepted_quantity) * Decimal(line.unit_cost) for line in receipt.lines), Decimal("0"))
    rejected_value = sum((Decimal(line.rejected_quantity) * Decimal(line.unit_cost) for line in receipt.lines), Decimal("0"))
    return {
        "id": receipt.id,
        "goods_receipt_number": receipt.goods_receipt_number,
        "purchase_order_id": receipt.purchase_order_id,
        "purchase_order_number": po.purchase_order_number if po else receipt.purchase_order_id,
        "supplier_id": po.supplier_id if po else None,
        "supplier_code": supplier.code if supplier else None,
        "supplier_name": supplier.name if supplier else None,
        "delivery_location_id": po.delivery_location_id if po else None,
        "delivery_location_code": location.code if location else None,
        "delivery_location_name": location.name if location else None,
        "stock_document_id": receipt.stock_document_id,
        "delivery_reference": receipt.delivery_reference,
        "notes": receipt.notes,
        "received_at": receipt.received_at.isoformat(),
        "received_value": str(received_value),
        "accepted_value": str(accepted_value),
        "rejected_value": str(rejected_value),
        "has_discrepancy": rejected_value > 0,
        "lines": [
            {
                "id": line.id,
                "purchase_order_line_id": line.purchase_order_line_id,
                "item_id": line.item_id,
                "sku": items[line.item_id].sku if line.item_id in items else line.item_id,
                "item_name": items[line.item_id].name if line.item_id in items else "Unknown item",
                "received_quantity": str(line.received_quantity),
                "accepted_quantity": str(line.accepted_quantity),
                "rejected_quantity": str(line.rejected_quantity),
                "unit_cost": str(line.unit_cost),
            }
            for line in receipt.lines
        ],
    }


def return_payload(db: Session, row: PurchaseReturn) -> dict:
    po = load_po(db, row.purchase_order_id)
    supplier = db.get(Supplier, po.supplier_id) if po else None
    return {
        "id": row.id,
        "return_number": row.return_number,
        "purchase_order_id": row.purchase_order_id,
        "purchase_order_number": po.purchase_order_number if po else row.purchase_order_id,
        "supplier_id": po.supplier_id if po else None,
        "supplier_code": supplier.code if supplier else None,
        "supplier_name": supplier.name if supplier else None,
        "stock_document_id": row.stock_document_id,
        "reason": row.reason,
        "created_at": row.created_at.isoformat(),
    }


@router.get("/receiving/workspace")
def receiving_workspace(db: Session = Depends(get_db), _: User = Depends(require_permission("receiving.read"))):
    pos = db.scalars(
        select(PurchaseOrder)
        .where(PurchaseOrder.status.in_(["approved", "partially_received", "received"]))
        .options(selectinload(PurchaseOrder.lines))
        .order_by(PurchaseOrder.created_at.desc())
    ).unique().all()
    receipts = db.scalars(select(GoodsReceipt).options(selectinload(GoodsReceipt.lines)).order_by(GoodsReceipt.received_at.desc())).unique().all()
    returns = db.scalars(select(PurchaseReturn).order_by(PurchaseReturn.created_at.desc())).all()
    items = {row.id: row for row in db.scalars(select(Item)).all()}
    suppliers = {row.id: row for row in db.scalars(select(Supplier)).all()}
    locations = {row.id: row for row in db.scalars(select(Location)).all()}
    po_rows = []
    for po in pos:
        supplier = suppliers.get(po.supplier_id)
        location = locations.get(po.delivery_location_id)
        ordered = sum((Decimal(line.ordered_quantity) for line in po.lines), Decimal("0"))
        received = sum((Decimal(line.received_quantity) for line in po.lines), Decimal("0"))
        po_rows.append({
            "id": po.id,
            "purchase_order_number": po.purchase_order_number,
            "supplier_id": po.supplier_id,
            "supplier_code": supplier.code if supplier else po.supplier_id,
            "supplier_name": supplier.name if supplier else "Unknown supplier",
            "delivery_location_id": po.delivery_location_id,
            "delivery_location_code": location.code if location else po.delivery_location_id,
            "delivery_location_name": location.name if location else "Unknown location",
            "expected_delivery_date": po.expected_delivery_date.isoformat() if po.expected_delivery_date else None,
            "status": po.status,
            "ordered_quantity": str(ordered),
            "received_quantity": str(received),
            "outstanding_quantity": str(max(Decimal("0"), ordered - received)),
            "lines": [
                {
                    "id": line.id,
                    "item_id": line.item_id,
                    "sku": items[line.item_id].sku if line.item_id in items else line.item_id,
                    "item_name": items[line.item_id].name if line.item_id in items else "Unknown item",
                    "ordered_quantity": str(line.ordered_quantity),
                    "received_quantity": str(line.received_quantity),
                    "returned_quantity": str(line.returned_quantity),
                    "outstanding_quantity": str(max(Decimal("0"), Decimal(line.ordered_quantity) - Decimal(line.received_quantity))),
                    "returnable_quantity": str(max(Decimal("0"), Decimal(line.received_quantity) - Decimal(line.returned_quantity))),
                    "unit_price": str(line.unit_price),
                }
                for line in po.lines
            ],
        })
    receipt_rows = [receipt_payload(db, row) for row in receipts]
    return_rows = [return_payload(db, row) for row in returns]
    return {
        "summary": {
            "receivable_orders": sum(1 for po in pos if po.status in {"approved", "partially_received"}),
            "partial_orders": sum(1 for po in pos if po.status == "partially_received"),
            "receipts": len(receipts),
            "discrepant_receipts": sum(1 for row in receipt_rows if row["has_discrepancy"]),
            "accepted_value": str(sum((Decimal(row["accepted_value"]) for row in receipt_rows), Decimal("0"))),
            "rejected_value": str(sum((Decimal(row["rejected_value"]) for row in receipt_rows), Decimal("0"))),
            "returns": len(returns),
        },
        "purchase_orders": po_rows,
        "receipts": receipt_rows,
        "returns": return_rows,
    }


@router.post("/receiving/purchase-orders/{po_id}", status_code=201)
def post_controlled_receipt(po_id: str, payload: ControlledReceiptCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("receiving.*"))):
    if payload.idempotency_key:
        existing_doc = db.scalar(select(StockDocument).where(StockDocument.idempotency_key == payload.idempotency_key))
        if existing_doc:
            existing = db.scalar(select(GoodsReceipt).where(GoodsReceipt.stock_document_id == existing_doc.id).options(selectinload(GoodsReceipt.lines)))
            if existing:
                return receipt_payload(db, existing)
            fail(409, "Idempotency key is already used")
    po = load_po(db, po_id, lock=True)
    if not po:
        fail(404, "Purchase order not found")
    if po.status not in {"approved", "partially_received"}:
        fail(409, "Purchase order is not receivable")
    po_lines = {line.id: line for line in po.lines}
    entries = []
    lot_updates = []
    discrepancy_lines = []
    for received in payload.lines:
        line = po_lines.get(received.purchase_order_line_id)
        if not line:
            fail(422, "Purchase order line not found")
        outstanding = Decimal(line.ordered_quantity) - Decimal(line.received_quantity)
        if received.received_quantity > outstanding:
            fail(409, "Received quantity exceeds outstanding quantity")
        if received.accepted_quantity > 0:
            entries.append({"item_id": line.item_id, "location_id": po.delivery_location_id, "quantity": received.accepted_quantity, "unit_cost": line.unit_price, "reason": "purchase order receipt"})
        if received.lot_number and received.accepted_quantity > 0:
            lot_updates.append((line, received))
        if received.rejected_quantity > 0:
            discrepancy_lines.append({"item_id": line.item_id, "rejected_quantity": str(received.rejected_quantity), "reason": received.discrepancy_reason})
    try:
        document = post_document(db, kind="po_receipt", actor_id=user.id, entries=entries, reference=po.purchase_order_number, notes=payload.notes, idempotency_key=payload.idempotency_key, commit=False, allow_empty=True)
        receipt = GoodsReceipt(goods_receipt_number=next_document_number(db, "GRN"), purchase_order_id=po.id, stock_document_id=document.id, delivery_reference=payload.delivery_reference, received_by_user_id=user.id, notes=payload.notes)
        for received in payload.lines:
            line = po_lines[received.purchase_order_line_id]
            line.received_quantity = Decimal(line.received_quantity) + received.received_quantity
            receipt.lines.append(GoodsReceiptLine(purchase_order_line_id=line.id, item_id=line.item_id, received_quantity=received.received_quantity, accepted_quantity=received.accepted_quantity, rejected_quantity=received.rejected_quantity, unit_cost=line.unit_price))
        for line, received in lot_updates:
            lot = db.scalar(select(InventoryLot).where(InventoryLot.item_id == line.item_id, InventoryLot.lot_number == received.lot_number))
            if not lot:
                lot = InventoryLot(item_id=line.item_id, lot_number=received.lot_number, manufactured_date=received.manufactured_date, expiry_date=received.expiry_date, supplier_id=po.supplier_id, status="active")
                db.add(lot)
                db.flush()
            lot_balance = db.scalar(select(LotBalance).where(LotBalance.lot_id == lot.id, LotBalance.location_id == po.delivery_location_id).with_for_update())
            if not lot_balance:
                lot_balance = LotBalance(lot_id=lot.id, location_id=po.delivery_location_id, quantity=Decimal("0"))
                db.add(lot_balance)
            lot_balance.quantity = Decimal(lot_balance.quantity) + received.accepted_quantity
        po.status = "received" if all(Decimal(line.received_quantity) >= Decimal(line.ordered_quantity) for line in po.lines) else "partially_received"
        db.add(receipt)
        db.flush()
        add_audit(db, actor_user_id=user.id, action="goods_receipt.controlled_posted", entity_type="goods_receipt", entity_id=receipt.id, details={"purchase_order_id": po.id, "line_count": len(receipt.lines), "discrepancies": discrepancy_lines, "lot_lines": len(lot_updates)})
        if discrepancy_lines:
            add_notification(db, title="Receiving discrepancy recorded", message=f"{receipt.goods_receipt_number} includes {len(discrepancy_lines)} rejected line(s).", severity="warning")
        enqueue_event(db, destination_system="accounting", event_type="procurement.goods_received", aggregate_type="goods_receipt", aggregate_id=receipt.id, idempotency_key=f"goods-received:{receipt.id}", payload={"goods_receipt_id": receipt.id, "goods_receipt_number": receipt.goods_receipt_number, "purchase_order_id": po.id, "supplier_id": po.supplier_id, "delivery_reference": payload.delivery_reference, "lines": [{"item_id": line.item_id, "accepted_quantity": str(line.accepted_quantity), "rejected_quantity": str(line.rejected_quantity), "unit_cost": str(line.unit_cost)} for line in receipt.lines]})
        db.commit()
        db.refresh(receipt)
        return receipt_payload(db, receipt)
    except (InventoryError, IntegrityError) as exc:
        db.rollback()
        fail(409, str(exc) if isinstance(exc, InventoryError) else "Goods receipt could not be posted")


@router.post("/receiving/purchase-orders/{po_id}/returns", status_code=201)
def post_controlled_return(po_id: str, payload: ControlledReturnCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("receiving.*"))):
    if payload.idempotency_key:
        existing_doc = db.scalar(select(StockDocument).where(StockDocument.idempotency_key == payload.idempotency_key))
        if existing_doc:
            existing = db.scalar(select(PurchaseReturn).where(PurchaseReturn.stock_document_id == existing_doc.id))
            if existing:
                return return_payload(db, existing)
            fail(409, "Idempotency key is already used")
    po = load_po(db, po_id, lock=True)
    if not po:
        fail(404, "Purchase order not found")
    po_lines = {line.id: line for line in po.lines}
    entries = []
    for returned in payload.lines:
        line = po_lines.get(returned.purchase_order_line_id)
        if not line:
            fail(422, "Purchase order line not found")
        returnable = Decimal(line.received_quantity) - Decimal(line.returned_quantity)
        if returned.quantity > returnable:
            fail(409, "Return quantity exceeds received quantity")
        entries.append({"item_id": line.item_id, "location_id": po.delivery_location_id, "quantity": -returned.quantity, "unit_cost": line.unit_price, "reason": f"purchase return: {payload.reason}"})
    try:
        document = post_document(db, kind="purchase_return", actor_id=user.id, entries=entries, reference=payload.supplier_reference or po.purchase_order_number, notes=payload.notes or payload.reason, idempotency_key=payload.idempotency_key, commit=False)
        for returned in payload.lines:
            line = po_lines[returned.purchase_order_line_id]
            line.returned_quantity = Decimal(line.returned_quantity) + returned.quantity
        row = PurchaseReturn(return_number=next_document_number(db, "PRTN"), purchase_order_id=po.id, stock_document_id=document.id, reason=payload.reason, created_by_user_id=user.id)
        db.add(row)
        db.flush()
        add_audit(db, actor_user_id=user.id, action="purchase_return.controlled_posted", entity_type="purchase_return", entity_id=row.id, details={"purchase_order_id": po.id, "supplier_reference": payload.supplier_reference, "line_count": len(payload.lines)})
        add_notification(db, title="Supplier return posted", message=f"{row.return_number} was posted against {po.purchase_order_number}.", severity="info")
        enqueue_event(db, destination_system="accounting", event_type="procurement.purchase_return.posted", aggregate_type="purchase_return", aggregate_id=row.id, idempotency_key=f"purchase-return:{row.id}", payload={"purchase_return_id": row.id, "return_number": row.return_number, "purchase_order_id": po.id, "supplier_id": po.supplier_id, "reason": row.reason, "supplier_reference": payload.supplier_reference})
        db.commit()
        db.refresh(row)
        return return_payload(db, row)
    except (InventoryError, IntegrityError) as exc:
        db.rollback()
        fail(409, str(exc) if isinstance(exc, InventoryError) else "Purchase return could not be posted")
