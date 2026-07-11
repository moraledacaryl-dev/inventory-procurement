from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.inventory import Item, Location, StockBalance
from app.models.inventory_operations import ItemLocationSetting, StockReservation
from app.models.procurement import PurchaseOrder, PurchaseRequisition, PurchaseRequisitionLine, Supplier, SupplierItem
from app.models.user import User
from app.services.controls import add_audit, add_notification, enqueue_event, next_document_number

router = APIRouter(tags=["procurement-planning"])

class PlanningLine(BaseModel):
    item_id: str
    quantity: Decimal = Field(gt=0)
    estimated_unit_cost: Decimal = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=240)

class PlanningRequisitionCreate(BaseModel):
    department: str = Field(min_length=1, max_length=100)
    location_id: str
    needed_by: date | None = None
    justification: str = Field(min_length=1)
    lines: list[PlanningLine] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_items(self):
        ids = [line.item_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate item lines are not allowed")
        return self

def fail(status: int, message: str):
    raise HTTPException(status_code=status, detail=message)

def planned_rows(db: Session, location_id: str | None = None):
    if location_id and not db.get(Location, location_id):
        fail(404, "Location not found")
    locations = db.scalars(select(Location).where(Location.is_active.is_(True)).order_by(Location.code)).all()
    location_ids = [location_id] if location_id else [row.id for row in locations]
    location_map = {row.id: row for row in locations}
    items = {row.id: row for row in db.scalars(select(Item).where(Item.is_active.is_(True), Item.track_stock.is_(True))).all()}
    balances = {(row.item_id, row.location_id): Decimal(row.quantity) for row in db.scalars(select(StockBalance).where(StockBalance.location_id.in_(location_ids))).all()}
    settings = {(row.item_id, row.location_id): row for row in db.scalars(select(ItemLocationSetting).where(ItemLocationSetting.location_id.in_(location_ids), ItemLocationSetting.is_active.is_(True))).all()}
    reservations: dict[tuple[str, str], Decimal] = {}
    for row in db.scalars(select(StockReservation).where(StockReservation.location_id.in_(location_ids), StockReservation.status == "active")).all():
        key = (row.item_id, row.location_id)
        reservations[key] = reservations.get(key, Decimal("0")) + Decimal(row.quantity)
    on_order: dict[tuple[str, str], Decimal] = {}
    for po in db.scalars(select(PurchaseOrder).where(PurchaseOrder.delivery_location_id.in_(location_ids), PurchaseOrder.status.in_(["approved", "partially_received"])).options(selectinload(PurchaseOrder.lines))).unique().all():
        for line in po.lines:
            key = (line.item_id, po.delivery_location_id)
            on_order[key] = on_order.get(key, Decimal("0")) + max(Decimal("0"), Decimal(line.ordered_quantity) - Decimal(line.received_quantity))
    pending_pr: dict[tuple[str, str], Decimal] = {}
    for req in db.scalars(select(PurchaseRequisition).where(PurchaseRequisition.status.in_(["submitted", "approved"])).options(selectinload(PurchaseRequisition.lines))).unique().all():
        for line in req.lines:
            for loc_id in location_ids:
                if f"location:{loc_id}" in (line.notes or ""):
                    key = (line.item_id, loc_id)
                    pending_pr[key] = pending_pr.get(key, Decimal("0")) + Decimal(line.quantity)
                    break
    supplier_links = db.scalars(select(SupplierItem).order_by(SupplierItem.is_preferred.desc())).all()
    preferred: dict[str, SupplierItem] = {}
    for link in supplier_links:
        preferred.setdefault(link.item_id, link)
    suppliers = {row.id: row for row in db.scalars(select(Supplier).where(Supplier.is_active.is_(True))).all()}
    rows = []
    for loc_id in location_ids:
        location = location_map.get(loc_id) or db.get(Location, loc_id)
        for item in items.values():
            setting = settings.get((item.id, loc_id))
            minimum = Decimal(setting.minimum_stock if setting else item.minimum_stock or 0)
            reorder_quantity = Decimal(setting.reorder_quantity if setting else 0)
            maximum = Decimal(setting.maximum_stock) if setting and setting.maximum_stock is not None else None
            if minimum <= 0 and reorder_quantity <= 0:
                continue
            physical = balances.get((item.id, loc_id), Decimal("0"))
            reserved = reservations.get((item.id, loc_id), Decimal("0"))
            available = physical - reserved
            incoming = on_order.get((item.id, loc_id), Decimal("0"))
            pending = pending_pr.get((item.id, loc_id), Decimal("0"))
            projected = available + incoming + pending
            if projected >= minimum:
                continue
            target = maximum if maximum is not None and maximum > minimum else minimum + reorder_quantity
            suggested = max(Decimal("0"), target - projected)
            link = preferred.get(item.id)
            if setting and setting.preferred_supplier_id:
                link = next((candidate for candidate in supplier_links if candidate.item_id == item.id and candidate.supplier_id == setting.preferred_supplier_id), link)
            supplier = suppliers.get(link.supplier_id) if link else None
            if link and suggested < Decimal(link.minimum_order_quantity):
                suggested = Decimal(link.minimum_order_quantity)
            cost = Decimal(link.last_price if link and Decimal(link.last_price) > 0 else item.standard_cost or 0)
            rows.append({
                "item_id": item.id, "sku": item.sku, "item_name": item.name,
                "location_id": loc_id, "location_code": location.code if location else loc_id, "location_name": location.name if location else "Unknown location",
                "physical_quantity": str(physical), "reserved_quantity": str(reserved), "available_quantity": str(available),
                "minimum_stock": str(minimum), "maximum_stock": str(maximum) if maximum is not None else None, "reorder_quantity": str(reorder_quantity),
                "on_order_quantity": str(incoming), "pending_requisition_quantity": str(pending), "projected_quantity": str(projected),
                "suggested_quantity": str(suggested), "estimated_unit_cost": str(cost), "estimated_value": str(suggested * cost),
                "preferred_supplier_id": link.supplier_id if link else None, "preferred_supplier_name": supplier.name if supplier else None,
                "lead_time_days": link.lead_time_days if link else None, "minimum_order_quantity": str(link.minimum_order_quantity) if link else None,
                "needed_by": (date.today() + timedelta(days=link.lead_time_days if link else 0)).isoformat(),
                "priority": "critical" if available <= 0 else "warning",
            })
    rows.sort(key=lambda row: (0 if row["priority"] == "critical" else 1, row["location_code"], row["sku"]))
    return rows

@router.get("/procurement/planning")
def procurement_planning(location_id: str | None = None, db: Session = Depends(get_db), _: User = Depends(require_permission("procurement.read"))):
    rows = planned_rows(db, location_id)
    return {"summary": {"suggestion_count": len(rows), "critical_count": sum(1 for row in rows if row["priority"] == "critical"), "estimated_value": str(sum((Decimal(row["estimated_value"]) for row in rows), Decimal("0"))), "supplier_assigned_count": sum(1 for row in rows if row["preferred_supplier_id"])}, "rows": rows}

@router.post("/procurement/planning/requisitions", status_code=201)
def create_planned_requisition(payload: PlanningRequisitionCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("procurement.*"))):
    location = db.get(Location, payload.location_id)
    if not location or not location.is_active:
        fail(422, "Active location not found")
    for line in payload.lines:
        item = db.get(Item, line.item_id)
        if not item or not item.is_active or not item.track_stock:
            fail(422, "Invalid or inactive stock item")
    row = PurchaseRequisition(requisition_number=next_document_number(db, "PR"), department=payload.department.strip(), needed_by=payload.needed_by, justification=payload.justification.strip(), status="submitted", requested_by_user_id=user.id)
    row.lines = [PurchaseRequisitionLine(item_id=line.item_id, quantity=line.quantity, estimated_unit_cost=line.estimated_unit_cost, notes=((line.notes + "; ") if line.notes else "") + f"location:{payload.location_id}") for line in payload.lines]
    try:
        db.add(row); db.flush()
        add_audit(db, actor_user_id=user.id, action="requisition.planned", entity_type="purchase_requisition", entity_id=row.id, details={"location_id": payload.location_id, "line_count": len(row.lines)})
        add_notification(db, title="Purchase requisition submitted", message=f"{row.requisition_number} was submitted for {location.code} with {len(row.lines)} line(s).", severity="info")
        enqueue_event(db, destination_system="command-center", event_type="procurement.requisition.submitted", aggregate_type="purchase_requisition", aggregate_id=row.id, idempotency_key=f"requisition-submitted:{row.id}", payload={"requisition_id": row.id, "requisition_number": row.requisition_number, "location_id": payload.location_id})
        db.commit()
        return {"id": row.id, "requisition_number": row.requisition_number, "status": row.status, "line_count": len(row.lines)}
    except IntegrityError:
        db.rollback(); fail(409, "Requisition could not be created")

@router.get("/procurement/requisitions/workspace")
def requisition_workspace(db: Session = Depends(get_db), _: User = Depends(require_permission("procurement.read"))):
    rows = db.scalars(select(PurchaseRequisition).options(selectinload(PurchaseRequisition.lines)).order_by(PurchaseRequisition.created_at.desc())).unique().all()
    items = {row.id: row for row in db.scalars(select(Item)).all()}
    result = []
    for req in rows:
        total = sum((Decimal(line.quantity) * Decimal(line.estimated_unit_cost) for line in req.lines), Decimal("0"))
        result.append({"id": req.id, "requisition_number": req.requisition_number, "department": req.department, "needed_by": req.needed_by.isoformat() if req.needed_by else None, "justification": req.justification, "status": req.status, "requested_by_user_id": req.requested_by_user_id, "approved_by_user_id": req.approved_by_user_id, "approved_at": req.approved_at.isoformat() if req.approved_at else None, "created_at": req.created_at.isoformat(), "estimated_value": str(total), "lines": [{"id": line.id, "item_id": line.item_id, "sku": items[line.item_id].sku if line.item_id in items else line.item_id, "item_name": items[line.item_id].name if line.item_id in items else "Unknown item", "quantity": str(line.quantity), "estimated_unit_cost": str(line.estimated_unit_cost), "notes": line.notes} for line in req.lines]})
    return result
