from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.inventory import Item, Location
from app.models.procurement import PurchaseOrder, PurchaseOrderLine, PurchaseRequisition, Supplier, SupplierQuotation
from app.models.user import User
from app.services.controls import add_audit, add_notification, enqueue_event, next_document_number
from app.services.operational_authorization import require_scoped_locations, visible_location_ids, require_requisition_location

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
    return sum((line.outstanding_quantity * Decimal(line.unit_price) for line in po.lines), Decimal("0"))


@router.get("/procurement/quotation-workspace")
def quotation_workspace(
    po_page: int | None = Query(default=None, ge=1),
    po_page_size: int = Query(default=25, ge=1, le=100),
    po_search: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("procurement.read")),
):
    allowed = visible_location_ids(db, user)
    po_scope = [PurchaseOrder.delivery_location_id.in_(allowed)] if allowed is not None else []
    po_stmt = select(PurchaseOrder).where(*po_scope)
    all_po_count = db.scalar(select(func.count(PurchaseOrder.id)).where(*po_scope)) or 0
    open_states = ("received", "closed", "cancelled")
    open_purchase_orders = db.scalar(
        select(func.count(PurchaseOrder.id)).where(
            *po_scope, PurchaseOrder.status.notin_(open_states)
        )
    ) or 0
    open_commitment_value = db.scalar(
        select(func.coalesce(func.sum(case(
            (PurchaseOrderLine.ordered_quantity > PurchaseOrderLine.fulfilled_quantity,
             (PurchaseOrderLine.ordered_quantity - PurchaseOrderLine.fulfilled_quantity) * PurchaseOrderLine.unit_price),
            else_=0,
        )), 0))
        .select_from(PurchaseOrderLine)
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id)
        .where(*po_scope, PurchaseOrder.status.notin_(open_states))
    ) or Decimal("0")
    # Used only for the quote-award links. Do not lose award status when
    # purchase orders are paged out of the visible table.
    award_rows = db.execute(
        select(PurchaseOrder.quotation_id, PurchaseOrder.id, PurchaseOrder.purchase_order_number)
        .where(*po_scope, PurchaseOrder.quotation_id.is_not(None))
    ).all()
    po_by_quote = {
        row.quotation_id: {"id": row.id, "number": row.purchase_order_number}
        for row in award_rows
    }
    if po_search and po_search.strip():
        term = f"%{po_search.strip()}%"
        supplier_ids = select(Supplier.id).where(
            or_(Supplier.name.ilike(term), Supplier.code.ilike(term))
        )
        po_stmt = po_stmt.where(or_(
            PurchaseOrder.purchase_order_number.ilike(term),
            PurchaseOrder.supplier_id.in_(supplier_ids),
        ))
    matching_pos = db.scalar(select(func.count()).select_from(
        po_stmt.with_only_columns(PurchaseOrder.id).order_by(None).subquery()
    )) or 0
    po_stmt = po_stmt.options(selectinload(PurchaseOrder.lines)).order_by(
        PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc()
    )
    if po_page is not None:
        po_stmt = po_stmt.offset((po_page - 1) * po_page_size).limit(po_page_size)
    purchase_orders = db.scalars(po_stmt).unique().all()
    requisition_stmt = (
        select(PurchaseRequisition)
        .where(PurchaseRequisition.status == "approved")
        .options(selectinload(PurchaseRequisition.lines))
        .order_by(PurchaseRequisition.created_at.desc())
    )
    quote_stmt = select(SupplierQuotation).options(selectinload(SupplierQuotation.lines)).order_by(SupplierQuotation.created_at.desc())
    if allowed is not None:
        # Quotations inherit their authoritative location from their parent PR.
        # Include unawarded scoped requisitions/quotes, not only those with POs.
        requisition_stmt = requisition_stmt.where(PurchaseRequisition.location_id.in_(allowed))
        quote_stmt = quote_stmt.join(
            PurchaseRequisition, SupplierQuotation.requisition_id == PurchaseRequisition.id
        ).where(PurchaseRequisition.location_id.in_(allowed))
    requisitions = db.scalars(requisition_stmt).unique().all()
    quotes = db.scalars(quote_stmt).unique().all()
    item_ids = {
        line.item_id for req in requisitions for line in req.lines
    } | {
        line.item_id for quote in quotes for line in quote.lines
    }
    items = {
        row.id: row for row in db.scalars(select(Item).where(Item.id.in_(item_ids))).all()
    } if item_ids else {}
    suppliers = {row.id: row for row in db.scalars(select(Supplier)).all()}
    locations = {row.id: row for row in db.scalars(select(Location)).all()}

    quotes_by_req: dict[str, list[SupplierQuotation]] = {}
    for quote in quotes:
        quotes_by_req.setdefault(quote.requisition_id, []).append(quote)

    requisition_rows = []
    for req in requisitions:
        req_quotes = quotes_by_req.get(req.id, [])
        totals = [quotation_total(quote) for quote in req_quotes]
        lowest = min(totals) if totals else None
        requisition_rows.append({
            "id": req.id,
            "requisition_number": req.requisition_number,
            "department": req.department,
            "location_id": req.location_id,
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
                    "purchase_order_id": po_by_quote[quote.id]["id"] if quote.id in po_by_quote else None,
                    "purchase_order_number": po_by_quote[quote.id]["number"] if quote.id in po_by_quote else None,
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
            "open_purchase_orders": open_purchase_orders,
            "open_commitment_value": str(open_commitment_value),
        },
        "requisitions": requisition_rows,
        "purchase_orders": po_rows,
        "po_pagination": {
            "page": po_page or 1, "page_size": po_page_size if po_page is not None else len(po_rows),
            "total": matching_pos if po_page is not None else all_po_count,
            "has_previous": po_page is not None and po_page > 1,
            "has_next": po_page is not None and po_page * po_page_size < matching_pos,
        },
    }


@router.post("/requisitions/{requisition_id}/award-quotation", status_code=201)
def award_quotation(requisition_id: str, payload: QuoteAwardCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("procurement.*"))):
    location = db.get(Location, payload.delivery_location_id)
    if not location or not location.is_active:
        fail(422, "Active delivery location not found")
    # Deny a foreign destination before querying the financial requisition/quote.
    require_scoped_locations(db, user, {payload.delivery_location_id})
    requisition = load_requisition(db, requisition_id)
    quotation = load_quote(db, payload.quotation_id)
    if not requisition or requisition.status != "approved":
        fail(409, "Quotation award requires an approved requisition")
    if not quotation or quotation.requisition_id != requisition_id:
        fail(422, "Quotation does not belong to this requisition")
    require_requisition_location(db, user, requisition.location_id)
    if requisition.location_id and requisition.location_id != payload.delivery_location_id:
        fail(409, "Delivery location differs from requisition ownership")
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
def purchase_order_detail(po_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission("procurement.read"))):
    po = load_po(db, po_id)
    if not po:
        fail(404, "Purchase order not found")
    require_scoped_locations(db, user, {po.delivery_location_id})
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
            "received_lines": sum(1 for line in po.lines if Decimal(line.fulfilled_quantity) >= Decimal(line.ordered_quantity)),
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
                "outstanding_quantity": str(line.outstanding_quantity),
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
    require_scoped_locations(db, user, {po.delivery_location_id})
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
    require_scoped_locations(db, user, {po.delivery_location_id})
    if po.status not in {"draft", "approved"}:
        fail(409, "Purchase order cannot be cancelled in its current status")
    if any(Decimal(line.received_quantity) > 0 for line in po.lines):
        fail(409, "Purchase order with receipts cannot be cancelled")
    po.status = "cancelled"
    add_audit(db, actor_user_id=user.id, action="purchase_order.cancelled", entity_type="purchase_order", entity_id=po.id)
    enqueue_event(db, destination_system="accounting", event_type="procurement.purchase_order.cancelled", aggregate_type="purchase_order", aggregate_id=po.id, idempotency_key=f"po-cancelled:{po.id}", payload={"purchase_order_id": po.id, "purchase_order_number": po.purchase_order_number})
    db.commit()
    return purchase_order_detail(po.id, db, user)
