from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.inventory import Item, Location
from app.models.procurement import PurchaseOrder, PurchaseOrderLine, PurchaseRequisition, Supplier, SupplierQuotation
from app.models.user import User
from app.services.controls import add_audit, add_notification, enqueue_event, next_document_number

router = APIRouter(tags=["quotation-po-workspace"])


class QuoteAwardCreate(BaseModel):
    quotation_id: str
    delivery_location_id: str
    expected_delivery_date: date | None = None
    notes: str | None = None


class PurchaseOrderAmendLine(BaseModel):
    line_id: str | None = None
    item_id: str
    ordered_quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(gt=0)


class PurchaseOrderAmend(BaseModel):
    expected_delivery_date: date | None = None
    notes: str | None = None
    lines: list[PurchaseOrderAmendLine] = Field(min_length=1)


def fail(status: int, message: str):
    raise HTTPException(status_code=status, detail=message)


def load_requisition(db: Session, requisition_id: str):
    return db.scalar(select(PurchaseRequisition).where(PurchaseRequisition.id == requisition_id).options(selectinload(PurchaseRequisition.lines)))


def load_quote(db: Session, quotation_id: str):
    return db.scalar(select(SupplierQuotation).where(SupplierQuotation.id == quotation_id).options(selectinload(SupplierQuotation.lines)))


def load_po(db: Session, po_id: str, lock: bool = False):
    stmt = select(PurchaseOrder).where(PurchaseOrder.id == po_id).options(selectinload(PurchaseOrder.lines))
    if lock:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def quotation_total(quote: SupplierQuotation) -> Decimal:
    return sum((Decimal(line.quantity) * Decimal(line.unit_price) for line in quote.lines), Decimal("0"))


def po_total(po: PurchaseOrder) -> Decimal:
    return sum((Decimal(line.ordered_quantity) * Decimal(line.unit_price) for line in po.lines), Decimal("0"))


def po_outstanding(po: PurchaseOrder) -> Decimal:
    return sum((max(Decimal("0"), Decimal(line.ordered_quantity) - Decimal(line.received_quantity)) * Decimal(line.unit_price) for line in po.lines), Decimal("0"))


@router.get("/procurement/quotation-workspace")
def quotation_workspace(db: Session = Depends(get_db), _: User = Depends(require_permission("procurement.read"))):
    requisitions = db.scalars(
        select(PurchaseRequisition)
        .where(PurchaseRequisition.status == "approved")
        .options(selectinload(PurchaseRequisition.lines))
        .order_by(PurchaseRequisition.created_at.desc())
    ).unique().all()
    quotes = db.scalars(select(SupplierQuotation).options(selectinload(SupplierQuotation.lines)).order_by(SupplierQuotation.created_at.desc())).unique().all()
    purchase_orders = db.scalars(select(PurchaseOrder).options(selectinload(PurchaseOrder.lines)).order_by(PurchaseOrder.created_at.desc())).unique().all()
    items = {row.id: row for row in db.scalars(select(Item)).all()}
    suppliers = {row.id: row for row in db.scalars(select(Supplier)).all()}
    locations = {row.id: row for row in db.scalars(select(Location)).all()}

    quotes_by_req: dict[str, list[SupplierQuotation]] = {}
    for quote in quotes:
        quotes_by_req.setdefault(quote.requisition_id, []).append(quote)
    po_by_quote = {po.quotation_id: po for po in purchase_orders if po.quotation_id}

    requisition_rows = []
    for req in requisitions:
        req_quotes = quotes_by_req.get(req.id, [])
        totals = [quotation_total(quote) for quote in req_quotes]
        lowest = min(totals) if totals else None
        requisition_rows.append({
            "id": req.id,
            "requisition_number": req.requisition_number,
            "department": req.department,
            "needed_by": req.needed_by.isoformat() if req.needed_by else None,
            "justification": req.justification,
            "created_at": req.created_at.isoformat(),
            "line_count": len(req.lines),
            "quotation_count": len(req_quotes),
            "lowest_total": str(lowest) if lowest is not None else None,
            "awarded": any(quote.id in po_by_quote for quote in req_quotes),
            "lines": [
                {
                    "item_id": line.item_id,
                    "sku": items[line.item_id].sku if line.item_id in items else line.item_id,
                    "item_name": items[line.item_id].name if line.item_id in items else "Unknown item",
                    "quantity": str(line.quantity),
                    "estimated_unit_cost": str(line.estimated_unit_cost),
                }
                for line in req.lines
            ],
            "quotations": [
                {
                    "id": quote.id,
                    "quotation_number": quote.quotation_number,
                    "supplier_id": quote.supplier_id,
                    "supplier_code": suppliers[quote.supplier_id].code if quote.supplier_id in suppliers else quote.supplier_id,
                    "supplier_name": suppliers[quote.supplier_id].name if quote.supplier_id in suppliers else "Unknown supplier",
                    "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
                    "delivery_days": quote.delivery_days,
                    "payment_terms_days": quote.payment_terms_days,
                    "notes": quote.notes,
                    "status": "awarded" if quote.id in po_by_quote else quote.status,
                    "total": str(quotation_total(quote)),
                    "variance_from_lowest": str(quotation_total(quote) - lowest) if lowest is not None else "0",
                    "purchase_order_id": po_by_quote[quote.id].id if quote.id in po_by_quote else None,
                    "purchase_order_number": po_by_quote[quote.id].purchase_order_number if quote.id in po_by_quote else None,
                    "lines": [
                        {
                            "item_id": line.item_id,
                            "sku": items[line.item_id].sku if line.item_id in items else line.item_id,
                            "item_name": items[line.item_id].name if line.item_id in items else "Unknown item",
                            "quantity": str(line.quantity),
                            "unit_price": str(line.unit_price),
                            "line_total": str(Decimal(line.quantity) * Decimal(line.unit_price)),
                        }
                        for line in quote.lines
                    ],
                }
                for quote in sorted(req_quotes, key=lambda row: (quotation_total(row), row.delivery_days))
            ],
        })

    po_rows = []
    for po in purchase_orders:
        supplier = suppliers.get(po.supplier_id)
        location = locations.get(po.delivery_location_id)
        po_rows.append({
            "id": po.id,
            "purchase_order_number": po.purchase_order_number,
            "supplier_id": po.supplier_id,
            "supplier_code": supplier.code if supplier else po.supplier_id,
            "supplier_name": supplier.name if supplier else "Unknown supplier",
            "requisition_id": po.requisition_id,
            "quotation_id": po.quotation_id,
            "delivery_location_id": po.delivery_location_id,
            "delivery_location_code": location.code if location else po.delivery_location_id,
            "delivery_location_name": location.name if location else "Unknown location",
            "expected_delivery_date": po.expected_delivery_date.isoformat() if po.expected_delivery_date else None,
            "status": po.status,
            "notes": po.notes,
            "created_by_user_id": po.created_by_user_id,
            "approved_by_user_id": po.approved_by_user_id,
            "approved_at": po.approved_at.isoformat() if po.approved_at else None,
            "created_at": po.created_at.isoformat(),
            "total": str(po_total(po)),
            "outstanding_value": str(po_outstanding(po)),
            "received_percent": str((Decimal("100") - (po_outstanding(po) / po_total(po) * Decimal("100"))).quantize(Decimal("0.01")) if po_total(po) else Decimal("0")),
            "line_count": len(po.lines),
        })

    return {
        "summary": {
            "approved_requisitions": len(requisition_rows),
            "requisitions_without_quotes": sum(1 for row in requisition_rows if row["quotation_count"] == 0),
            "quotations": len(quotes),
            "open_purchase_orders": sum(1 for po in purchase_orders if po.status not in {"received", "closed", "cancelled"}),
            "open_commitment_value": str(sum((po_outstanding(po) for po in purchase_orders if po.status not in {"received", "closed", "cancelled"}), Decimal("0"))),
        },
        "requisitions": requisition_rows,
        "purchase_orders": po_rows,
    }


@router.post("/requisitions/{requisition_id}/award-quotation", status_code=201)
def award_quotation(requisition_id: str, payload: QuoteAwardCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("procurement.*"))):
    requisition = load_requisition(db, requisition_id)
    quotation = load_quote(db, payload.quotation_id)
    location = db.get(Location, payload.delivery_location_id)
    if not requisition or requisition.status != "approved":
        fail(409, "Quotation award requires an approved requisition")
    if not quotation or quotation.requisition_id != requisition_id:
        fail(422, "Quotation does not belong to this requisition")
    if not location or not location.is_active:
        fail(422, "Active delivery location not found")
    existing = db.scalar(select(PurchaseOrder).where(PurchaseOrder.quotation_id == quotation.id))
    if existing:
        fail(409, "This quotation has already been awarded")
    supplier = db.get(Supplier, quotation.supplier_id)
    if not supplier or not supplier.is_active:
        fail(409, "Quotation supplier is inactive")
    row = PurchaseOrder(
        purchase_order_number=next_document_number(db, "PO"),
        supplier_id=quotation.supplier_id,
        requisition_id=requisition.id,
        quotation_id=quotation.id,
        delivery_location_id=payload.delivery_location_id,
        expected_delivery_date=payload.expected_delivery_date,
        notes=payload.notes or quotation.notes,
        created_by_user_id=user.id,
        status="draft",
    )
    row.lines = [PurchaseOrderLine(item_id=line.item_id, ordered_quantity=line.quantity, unit_price=line.unit_price) for line in quotation.lines]
    try:
        db.add(row)
        db.flush()
        quotation.status = "awarded"
        for competitor in db.scalars(select(SupplierQuotation).where(SupplierQuotation.requisition_id == requisition_id, SupplierQuotation.id != quotation.id)).all():
            if competitor.status == "submitted":
                competitor.status = "not_awarded"
        add_audit(db, actor_user_id=user.id, action="quotation.awarded", entity_type="supplier_quotation", entity_id=quotation.id, details={"purchase_order_id": row.id, "total": str(quotation_total(quotation))})
        add_notification(db, title="Quotation awarded", message=f"{quotation.quotation_number} was awarded and draft {row.purchase_order_number} was created.", severity="info")
        db.commit()
        return {"purchase_order_id": row.id, "purchase_order_number": row.purchase_order_number, "status": row.status}
    except IntegrityError:
        db.rollback()
        fail(409, "Quotation award could not be saved")


@router.get("/purchase-orders/{po_id}/detail")
def purchase_order_detail(po_id: str, db: Session = Depends(get_db), _: User = Depends(require_permission("procurement.read"))):
    po = load_po(db, po_id)
    if not po:
        fail(404, "Purchase order not found")
    supplier = db.get(Supplier, po.supplier_id)
    location = db.get(Location, po.delivery_location_id)
    items = {row.id: row for row in db.scalars(select(Item).where(Item.id.in_({line.item_id for line in po.lines}))).all()}
    return {
        "purchase_order": {
            "id": po.id,
            "purchase_order_number": po.purchase_order_number,
            "supplier_id": po.supplier_id,
            "supplier_code": supplier.code if supplier else po.supplier_id,
            "supplier_name": supplier.name if supplier else "Unknown supplier",
            "requisition_id": po.requisition_id,
            "quotation_id": po.quotation_id,
            "delivery_location_id": po.delivery_location_id,
            "delivery_location_code": location.code if location else po.delivery_location_id,
            "delivery_location_name": location.name if location else "Unknown location",
            "expected_delivery_date": po.expected_delivery_date.isoformat() if po.expected_delivery_date else None,
            "status": po.status,
            "notes": po.notes,
            "created_by_user_id": po.created_by_user_id,
            "approved_by_user_id": po.approved_by_user_id,
            "approved_at": po.approved_at.isoformat() if po.approved_at else None,
            "created_at": po.created_at.isoformat(),
        },
        "summary": {
            "total": str(po_total(po)),
            "outstanding_value": str(po_outstanding(po)),
            "line_count": len(po.lines),
            "received_lines": sum(1 for line in po.lines if Decimal(line.received_quantity) >= Decimal(line.ordered_quantity)),
        },
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
                "unit_price": str(line.unit_price),
                "line_total": str(Decimal(line.ordered_quantity) * Decimal(line.unit_price)),
            }
            for line in po.lines
        ],
        "controls": {
            "can_amend": po.status == "draft",
            "can_approve": po.status == "draft",
            "can_cancel": po.status in {"draft", "approved"} and all(Decimal(line.received_quantity) == 0 for line in po.lines),
        },
    }


@router.patch("/purchase-orders/{po_id}/amend")
def amend_purchase_order(po_id: str, payload: PurchaseOrderAmend, db: Session = Depends(get_db), user: User = Depends(require_permission("procurement.*"))):
    po = load_po(db, po_id, lock=True)
    if not po:
        fail(404, "Purchase order not found")
    if po.status != "draft":
        fail(409, "Only draft purchase orders can be amended")
    if len({line.item_id for line in payload.lines}) != len(payload.lines):
        fail(422, "Duplicate item lines are not allowed")
    for line in payload.lines:
        if not db.get(Item, line.item_id):
            fail(422, "Item not found")
    before_total = po_total(po)
    po.expected_delivery_date = payload.expected_delivery_date
    po.notes = payload.notes
    po.lines.clear()
    po.lines.extend([PurchaseOrderLine(item_id=line.item_id, ordered_quantity=line.ordered_quantity, unit_price=line.unit_price) for line in payload.lines])
    add_audit(db, actor_user_id=user.id, action="purchase_order.amended", entity_type="purchase_order", entity_id=po.id, details={"before_total": str(before_total), "after_total": str(po_total(po)), "line_count": len(po.lines)})
    db.commit()
    return purchase_order_detail(po.id, db, user)


@router.post("/purchase-orders/{po_id}/cancel-workspace")
def cancel_purchase_order(po_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission("procurement.*"))):
    po = load_po(db, po_id, lock=True)
    if not po:
        fail(404, "Purchase order not found")
    if po.status not in {"draft", "approved"}:
        fail(409, "Purchase order cannot be cancelled in its current status")
    if any(Decimal(line.received_quantity) > 0 for line in po.lines):
        fail(409, "Purchase order with receipts cannot be cancelled")
    po.status = "cancelled"
    add_audit(db, actor_user_id=user.id, action="purchase_order.cancelled", entity_type="purchase_order", entity_id=po.id)
    enqueue_event(db, destination_system="accounting", event_type="procurement.purchase_order.cancelled", aggregate_type="purchase_order", aggregate_id=po.id, idempotency_key=f"po-cancelled:{po.id}", payload={"purchase_order_id": po.id, "purchase_order_number": po.purchase_order_number})
    db.commit()
    return purchase_order_detail(po.id, db, user)
