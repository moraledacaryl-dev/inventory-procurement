from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.inventory import Item, Location
from app.models.procurement import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseReturn,
    Supplier,
    SupplierItem,
    SupplierQuotation,
)
from app.models.user import User
from app.services.controls import add_audit

router = APIRouter(tags=["supplier-360"])


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    contact_name: str | None = Field(default=None, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=80)
    address: str | None = None
    payment_terms_days: int | None = Field(default=None, ge=0, le=3650)
    tax_id: str | None = Field(default=None, max_length=80)
    is_active: bool | None = None


def fail(status: int, message: str):
    raise HTTPException(status_code=status, detail=message)


def decimal_sum(values):
    return sum((Decimal(value) for value in values), Decimal("0"))


@router.get("/suppliers/{supplier_id}/detail")
def supplier_detail(
    supplier_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("suppliers.read")),
):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        fail(404, "Supplier not found")

    links = db.scalars(select(SupplierItem).where(SupplierItem.supplier_id == supplier_id).order_by(SupplierItem.is_preferred.desc())).all()
    item_ids = {link.item_id for link in links}
    items = {row.id: row for row in db.scalars(select(Item).where(Item.id.in_(item_ids))).all()} if item_ids else {}

    purchase_orders = db.scalars(
        select(PurchaseOrder)
        .where(PurchaseOrder.supplier_id == supplier_id)
        .options(selectinload(PurchaseOrder.lines))
        .order_by(PurchaseOrder.created_at.desc())
    ).unique().all()
    po_ids = {row.id for row in purchase_orders}
    receipts = db.scalars(
        select(GoodsReceipt)
        .where(GoodsReceipt.purchase_order_id.in_(po_ids))
        .options(selectinload(GoodsReceipt.lines))
        .order_by(GoodsReceipt.received_at.desc())
    ).unique().all() if po_ids else []
    returns = db.scalars(
        select(PurchaseReturn)
        .where(PurchaseReturn.purchase_order_id.in_(po_ids))
        .order_by(PurchaseReturn.created_at.desc())
    ).all() if po_ids else []
    quotations = db.scalars(
        select(SupplierQuotation)
        .where(SupplierQuotation.supplier_id == supplier_id)
        .options(selectinload(SupplierQuotation.lines))
        .order_by(SupplierQuotation.created_at.desc())
    ).unique().all()

    locations = {row.id: row for row in db.scalars(select(Location)).all()}
    receipts_by_po: dict[str, list[GoodsReceipt]] = {}
    for receipt in receipts:
        receipts_by_po.setdefault(receipt.purchase_order_id, []).append(receipt)

    ordered_value = Decimal("0")
    received_value = Decimal("0")
    accepted_value = Decimal("0")
    rejected_value = Decimal("0")
    open_commitment = Decimal("0")
    on_time = 0
    measured_deliveries = 0
    delivery_variances: list[Decimal] = []

    po_rows = []
    for po in purchase_orders:
        total = decimal_sum(Decimal(line.ordered_quantity) * Decimal(line.unit_price) for line in po.lines)
        received_total = decimal_sum(Decimal(line.received_quantity) * Decimal(line.unit_price) for line in po.lines)
        outstanding = decimal_sum(max(Decimal("0"), Decimal(line.ordered_quantity) - Decimal(line.received_quantity)) * Decimal(line.unit_price) for line in po.lines)
        ordered_value += total
        received_value += received_total
        if po.status not in {"received", "closed", "cancelled"}:
            open_commitment += outstanding

        po_receipts = receipts_by_po.get(po.id, [])
        first_receipt = min((receipt.received_at.date() for receipt in po_receipts), default=None)
        delivery_variance = None
        if first_receipt and po.expected_delivery_date:
            delivery_variance = (first_receipt - po.expected_delivery_date).days
            delivery_variances.append(Decimal(delivery_variance))
            measured_deliveries += 1
            if delivery_variance <= 0:
                on_time += 1

        po_rows.append({
            "id": po.id,
            "purchase_order_number": po.purchase_order_number,
            "status": po.status,
            "created_at": po.created_at.isoformat(),
            "expected_delivery_date": po.expected_delivery_date.isoformat() if po.expected_delivery_date else None,
            "first_receipt_date": first_receipt.isoformat() if first_receipt else None,
            "delivery_variance_days": delivery_variance,
            "delivery_location_id": po.delivery_location_id,
            "delivery_location_name": locations[po.delivery_location_id].name if po.delivery_location_id in locations else po.delivery_location_id,
            "ordered_value": str(total),
            "received_value": str(received_total),
            "outstanding_value": str(outstanding),
            "line_count": len(po.lines),
        })

    receipt_rows = []
    for receipt in receipts:
        receipt_received = decimal_sum(Decimal(line.received_quantity) * Decimal(line.unit_cost) for line in receipt.lines)
        receipt_accepted = decimal_sum(Decimal(line.accepted_quantity) * Decimal(line.unit_cost) for line in receipt.lines)
        receipt_rejected = decimal_sum(Decimal(line.rejected_quantity) * Decimal(line.unit_cost) for line in receipt.lines)
        accepted_value += receipt_accepted
        rejected_value += receipt_rejected
        receipt_rows.append({
            "id": receipt.id,
            "goods_receipt_number": receipt.goods_receipt_number,
            "purchase_order_id": receipt.purchase_order_id,
            "stock_document_id": receipt.stock_document_id,
            "delivery_reference": receipt.delivery_reference,
            "received_at": receipt.received_at.isoformat(),
            "received_value": str(receipt_received),
            "accepted_value": str(receipt_accepted),
            "rejected_value": str(receipt_rejected),
            "line_count": len(receipt.lines),
        })

    acceptance_rate = (accepted_value / (accepted_value + rejected_value) * 100).quantize(Decimal("0.01")) if accepted_value + rejected_value else Decimal("0")
    on_time_rate = (Decimal(on_time) / Decimal(measured_deliveries) * 100).quantize(Decimal("0.01")) if measured_deliveries else Decimal("0")
    average_variance = (sum(delivery_variances, Decimal("0")) / Decimal(len(delivery_variances))).quantize(Decimal("0.01")) if delivery_variances else Decimal("0")
    overdue_open = sum(1 for po in purchase_orders if po.expected_delivery_date and po.expected_delivery_date < date.today() and po.status not in {"received", "closed", "cancelled"})

    return {
        "supplier": {
            "id": supplier.id,
            "code": supplier.code,
            "name": supplier.name,
            "contact_name": supplier.contact_name,
            "email": supplier.email,
            "phone": supplier.phone,
            "address": supplier.address,
            "payment_terms_days": supplier.payment_terms_days,
            "tax_id": supplier.tax_id,
            "is_active": supplier.is_active,
            "created_at": supplier.created_at.isoformat(),
        },
        "metrics": {
            "linked_items": len(links),
            "preferred_items": sum(1 for link in links if link.is_preferred),
            "purchase_orders": len(purchase_orders),
            "open_purchase_orders": sum(1 for po in purchase_orders if po.status not in {"received", "closed", "cancelled"}),
            "overdue_purchase_orders": overdue_open,
            "ordered_value": str(ordered_value),
            "received_value": str(received_value),
            "open_commitment_value": str(open_commitment),
            "accepted_value": str(accepted_value),
            "rejected_value": str(rejected_value),
            "acceptance_rate": str(acceptance_rate),
            "on_time_rate": str(on_time_rate),
            "average_delivery_variance_days": str(average_variance),
            "returns": len(returns),
            "quotations": len(quotations),
        },
        "risk": {
            "level": "critical" if overdue_open >= 3 or acceptance_rate < 80 and accepted_value + rejected_value > 0 else "warning" if overdue_open or acceptance_rate < 95 and accepted_value + rejected_value > 0 else "normal",
            "signals": [
                signal
                for condition, signal in [
                    (overdue_open > 0, f"{overdue_open} overdue purchase order(s)"),
                    (accepted_value + rejected_value > 0 and acceptance_rate < 95, f"Acceptance rate is {acceptance_rate}%"),
                    (measured_deliveries > 0 and on_time_rate < 90, f"On-time rate is {on_time_rate}%"),
                    (len(returns) > 0, f"{len(returns)} purchase return(s) recorded"),
                ]
                if condition
            ],
        },
        "items": [
            {
                "id": link.id,
                "item_id": link.item_id,
                "sku": items[link.item_id].sku if link.item_id in items else link.item_id,
                "item_name": items[link.item_id].name if link.item_id in items else "Unknown item",
                "supplier_sku": link.supplier_sku,
                "last_price": str(link.last_price),
                "lead_time_days": link.lead_time_days,
                "minimum_order_quantity": str(link.minimum_order_quantity),
                "is_preferred": link.is_preferred,
            }
            for link in links
        ],
        "purchase_orders": po_rows,
        "receipts": receipt_rows,
        "returns": [
            {
                "id": row.id,
                "return_number": row.return_number,
                "purchase_order_id": row.purchase_order_id,
                "stock_document_id": row.stock_document_id,
                "reason": row.reason,
                "created_at": row.created_at.isoformat(),
            }
            for row in returns
        ],
        "quotations": [
            {
                "id": row.id,
                "quotation_number": row.quotation_number,
                "requisition_id": row.requisition_id,
                "status": row.status,
                "valid_until": row.valid_until.isoformat() if row.valid_until else None,
                "delivery_days": row.delivery_days,
                "payment_terms_days": row.payment_terms_days,
                "total": str(decimal_sum(Decimal(line.quantity) * Decimal(line.unit_price) for line in row.lines)),
                "created_at": row.created_at.isoformat(),
            }
            for row in quotations
        ],
    }


@router.patch("/suppliers/{supplier_id}")
def update_supplier(
    supplier_id: str,
    payload: SupplierUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("suppliers.*")),
):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        fail(404, "Supplier not found")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
    for field in ("contact_name", "phone", "address", "tax_id"):
        if field in data and isinstance(data[field], str):
            data[field] = data[field].strip() or None
    if data.get("is_active") is False and supplier.is_active:
        open_orders = db.scalar(select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.supplier_id == supplier_id, PurchaseOrder.status.not_in(["received", "closed", "cancelled"]))) or 0
        if open_orders:
            fail(409, f"Supplier cannot be deactivated while {open_orders} purchase order(s) remain open")
    changes = {key: {"from": str(getattr(supplier, key)), "to": str(value)} for key, value in data.items() if getattr(supplier, key) != value}
    for key, value in data.items():
        setattr(supplier, key, value)
    try:
        add_audit(db, actor_user_id=user.id, action="supplier.updated", entity_type="supplier", entity_id=supplier.id, details={"changes": changes})
        db.commit()
        db.refresh(supplier)
        return supplier
    except IntegrityError:
        db.rollback()
        fail(409, "Supplier update could not be saved")
