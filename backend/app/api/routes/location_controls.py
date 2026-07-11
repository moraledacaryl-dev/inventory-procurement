from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.inventory import Item, Location, StockBalance, StockMovement
from app.models.inventory_operations import ItemLocationSetting, TransferOrder
from app.models.procurement import PurchaseOrder
from app.models.user import User
from app.services.controls import add_audit

router = APIRouter(tags=["location-controls"])


class LocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    location_type: str | None = Field(default=None, min_length=1, max_length=40)
    parent_id: str | None = None
    is_active: bool | None = None


def fail(status: int, message: str):
    raise HTTPException(status_code=status, detail=message)


@router.get("/locations/{location_id}/detail")
def location_detail(
    location_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("locations.read")),
):
    location = db.get(Location, location_id)
    if not location:
        fail(404, "Location not found")

    parent = db.get(Location, location.parent_id) if location.parent_id else None
    children = db.scalars(select(Location).where(Location.parent_id == location_id).order_by(Location.code)).all()
    balance_rows = db.execute(
        select(StockBalance, Item)
        .join(Item, Item.id == StockBalance.item_id)
        .where(StockBalance.location_id == location_id)
        .order_by(Item.sku)
    ).all()
    settings = db.scalars(
        select(ItemLocationSetting)
        .where(ItemLocationSetting.location_id == location_id)
        .order_by(ItemLocationSetting.item_id)
    ).all()

    item_map = {item.id: item for _balance, item in balance_rows}
    if settings:
        missing_ids = [row.item_id for row in settings if row.item_id not in item_map]
        if missing_ids:
            for item in db.scalars(select(Item).where(Item.id.in_(missing_ids))).all():
                item_map[item.id] = item

    total_quantity = sum((Decimal(balance.quantity) for balance, _item in balance_rows), Decimal("0"))
    total_value = sum((Decimal(balance.quantity) * Decimal(balance.average_cost) for balance, _item in balance_rows), Decimal("0"))
    nonzero_items = sum(1 for balance, _item in balance_rows if Decimal(balance.quantity) != 0)
    negative_items = sum(1 for balance, _item in balance_rows if Decimal(balance.quantity) < 0)
    low_stock_items = 0
    for balance, item in balance_rows:
        setting = next((row for row in settings if row.item_id == item.id and row.is_active), None)
        minimum = Decimal(setting.minimum_stock if setting else item.minimum_stock or 0)
        if Decimal(balance.quantity) < minimum:
            low_stock_items += 1

    inbound_transfers = db.scalars(
        select(TransferOrder)
        .where(TransferOrder.destination_location_id == location_id, TransferOrder.status.in_(["draft", "approved", "dispatched"]))
        .order_by(TransferOrder.created_at.desc())
    ).all()
    outbound_transfers = db.scalars(
        select(TransferOrder)
        .where(TransferOrder.source_location_id == location_id, TransferOrder.status.in_(["draft", "approved", "dispatched"]))
        .order_by(TransferOrder.created_at.desc())
    ).all()
    open_purchase_orders = db.scalars(
        select(PurchaseOrder)
        .where(PurchaseOrder.delivery_location_id == location_id, PurchaseOrder.status.not_in(["received", "closed", "cancelled"]))
        .order_by(PurchaseOrder.created_at.desc())
    ).all()

    recent_movements = db.execute(
        select(StockMovement, Item)
        .join(Item, Item.id == StockMovement.item_id)
        .where(StockMovement.location_id == location_id)
        .order_by(StockMovement.created_at.desc())
        .limit(25)
    ).all()

    return {
        "location": {
            "id": location.id,
            "code": location.code,
            "name": location.name,
            "location_type": location.location_type,
            "parent_id": location.parent_id,
            "is_active": location.is_active,
        },
        "parent": {"id": parent.id, "code": parent.code, "name": parent.name} if parent else None,
        "children": [
            {"id": row.id, "code": row.code, "name": row.name, "location_type": row.location_type, "is_active": row.is_active}
            for row in children
        ],
        "metrics": {
            "total_quantity": str(total_quantity),
            "inventory_value": str(total_value),
            "stocked_items": len(balance_rows),
            "nonzero_items": nonzero_items,
            "negative_items": negative_items,
            "low_stock_items": low_stock_items,
            "open_inbound_transfers": len(inbound_transfers),
            "open_outbound_transfers": len(outbound_transfers),
            "open_purchase_orders": len(open_purchase_orders),
        },
        "balances": [
            {
                "item_id": item.id,
                "sku": item.sku,
                "item_name": item.name,
                "quantity": str(balance.quantity),
                "average_cost": str(balance.average_cost),
                "inventory_value": str(Decimal(balance.quantity) * Decimal(balance.average_cost)),
                "updated_at": balance.updated_at.isoformat() if balance.updated_at else None,
            }
            for balance, item in balance_rows
        ],
        "policies": [
            {
                "id": row.id,
                "item_id": row.item_id,
                "sku": item_map[row.item_id].sku,
                "item_name": item_map[row.item_id].name,
                "minimum_stock": str(row.minimum_stock),
                "reorder_quantity": str(row.reorder_quantity),
                "maximum_stock": str(row.maximum_stock) if row.maximum_stock is not None else None,
                "cycle_count_days": row.cycle_count_days,
                "is_active": row.is_active,
            }
            for row in settings
            if row.item_id in item_map
        ],
        "recent_movements": [
            {
                "id": movement.id,
                "item_id": item.id,
                "sku": item.sku,
                "item_name": item.name,
                "quantity": str(movement.quantity),
                "unit_cost": str(movement.unit_cost),
                "reason": movement.reason,
                "created_at": movement.created_at.isoformat(),
            }
            for movement, item in recent_movements
        ],
        "controls": {
            "can_deactivate": nonzero_items == 0 and not children and not inbound_transfers and not outbound_transfers and not open_purchase_orders,
            "deactivation_blockers": [
                message
                for condition, message in [
                    (nonzero_items > 0, f"{nonzero_items} item balance(s) are non-zero"),
                    (bool(children), f"{len(children)} child location(s) still exist"),
                    (bool(inbound_transfers), f"{len(inbound_transfers)} inbound transfer(s) are open"),
                    (bool(outbound_transfers), f"{len(outbound_transfers)} outbound transfer(s) are open"),
                    (bool(open_purchase_orders), f"{len(open_purchase_orders)} purchase order(s) are open"),
                ]
                if condition
            ],
        },
    }


@router.patch("/locations/{location_id}")
def update_location(
    location_id: str,
    payload: LocationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("locations.*")),
):
    location = db.get(Location, location_id)
    if not location:
        fail(404, "Location not found")

    data = payload.model_dump(exclude_unset=True)
    if "parent_id" in data:
        if data["parent_id"] == location_id:
            fail(422, "A location cannot be its own parent")
        if data["parent_id"] and not db.get(Location, data["parent_id"]):
            fail(422, "Parent location not found")
        ancestor_id = data["parent_id"]
        while ancestor_id:
            if ancestor_id == location_id:
                fail(422, "Location hierarchy cannot contain a cycle")
            ancestor = db.get(Location, ancestor_id)
            ancestor_id = ancestor.parent_id if ancestor else None

    if data.get("is_active") is False and location.is_active:
        detail = location_detail(location_id, db, user)
        if not detail["controls"]["can_deactivate"]:
            fail(409, "Location cannot be deactivated: " + "; ".join(detail["controls"]["deactivation_blockers"]))

    if "name" in data:
        data["name"] = data["name"].strip()
    changes = {key: {"from": str(getattr(location, key)), "to": str(value)} for key, value in data.items() if getattr(location, key) != value}
    for key, value in data.items():
        setattr(location, key, value)

    try:
        add_audit(db, actor_user_id=user.id, action="location.updated", entity_type="location", entity_id=location.id, details={"changes": changes})
        db.commit()
        db.refresh(location)
        return location
    except IntegrityError:
        db.rollback()
        fail(409, "Location update could not be saved")
