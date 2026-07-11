from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.inventory import Item, Location, StockBalance, StockMovement
from app.models.inventory_operations import ItemLocationSetting, LotBalance, TransferOrder
from app.models.user import User
from app.services.controls import add_audit

router = APIRouter(tags=["location-controls"])


class LocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    location_type: str | None = Field(default=None, max_length=40)
    parent_id: str | None = None
    is_active: bool | None = None


def fail(status: int, message: str):
    raise HTTPException(status, message)


def descendants(db: Session, location_id: str) -> set[str]:
    result: set[str] = set()
    frontier = [location_id]
    while frontier:
        children = db.scalars(select(Location.id).where(Location.parent_id.in_(frontier))).all()
        unseen = [child for child in children if child not in result]
        result.update(unseen)
        frontier = unseen
    return result


@router.get("/locations/{location_id}")
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
    balances = db.execute(
        select(StockBalance, Item)
        .join(Item, Item.id == StockBalance.item_id)
        .where(StockBalance.location_id == location_id)
        .order_by(Item.sku)
    ).all()
    settings = db.execute(
        select(ItemLocationSetting, Item)
        .join(Item, Item.id == ItemLocationSetting.item_id)
        .where(ItemLocationSetting.location_id == location_id)
        .order_by(Item.sku)
    ).all()
    movements = db.execute(
        select(StockMovement, Item)
        .join(Item, Item.id == StockMovement.item_id)
        .where(StockMovement.location_id == location_id)
        .order_by(StockMovement.created_at.desc())
        .limit(25)
    ).all()

    total_quantity = sum((Decimal(balance.quantity) for balance, _item in balances), Decimal("0"))
    inventory_value = sum((Decimal(balance.quantity) * Decimal(balance.average_cost) for balance, _item in balances), Decimal("0"))
    negative_balances = sum(1 for balance, _item in balances if Decimal(balance.quantity) < 0)
    low_stock = 0
    for balance, item in balances:
        setting = next((row for row, setting_item in settings if setting_item.id == item.id and row.is_active), None)
        minimum = Decimal(setting.minimum_stock) if setting else Decimal(item.minimum_stock or 0)
        if Decimal(balance.quantity) < minimum:
            low_stock += 1

    inbound_transfers = db.scalar(select(func.count()).select_from(TransferOrder).where(
        TransferOrder.destination_location_id == location_id,
        TransferOrder.status == "dispatched",
    )) or 0
    outbound_transfers = db.scalar(select(func.count()).select_from(TransferOrder).where(
        TransferOrder.source_location_id == location_id,
        TransferOrder.status.in_(["draft", "approved", "dispatched"]),
    )) or 0
    lot_quantity = db.scalar(select(func.coalesce(func.sum(LotBalance.quantity), 0)).where(LotBalance.location_id == location_id)) or 0

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
            {"id": child.id, "code": child.code, "name": child.name, "location_type": child.location_type, "is_active": child.is_active}
            for child in children
        ],
        "metrics": {
            "item_count": len(balances),
            "total_quantity": str(total_quantity),
            "inventory_value": str(inventory_value),
            "negative_balances": negative_balances,
            "low_stock_items": low_stock,
            "policy_count": len(settings),
            "inbound_transfers": inbound_transfers,
            "outbound_transfers": outbound_transfers,
            "lot_quantity": str(lot_quantity),
        },
        "balances": [
            {
                "item_id": item.id,
                "sku": item.sku,
                "item_name": item.name,
                "quantity": str(balance.quantity),
                "average_cost": str(balance.average_cost),
                "inventory_value": str(Decimal(balance.quantity) * Decimal(balance.average_cost)),
                "allow_negative_stock": item.allow_negative_stock,
                "updated_at": balance.updated_at.isoformat(),
            }
            for balance, item in balances
        ],
        "policies": [
            {
                "id": setting.id,
                "item_id": item.id,
                "sku": item.sku,
                "item_name": item.name,
                "minimum_stock": str(setting.minimum_stock),
                "reorder_quantity": str(setting.reorder_quantity),
                "maximum_stock": str(setting.maximum_stock) if setting.maximum_stock is not None else None,
                "cycle_count_days": setting.cycle_count_days,
                "is_active": setting.is_active,
            }
            for setting, item in settings
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
            for movement, item in movements
        ],
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

    if "parent_id" in data and data["parent_id"]:
        if data["parent_id"] == location_id:
            fail(422, "Location cannot be its own parent")
        if not db.get(Location, data["parent_id"]):
            fail(422, "Parent location not found")
        if data["parent_id"] in descendants(db, location_id):
            fail(422, "Location hierarchy cannot contain a cycle")

    if data.get("is_active") is False:
        nonzero = db.scalar(select(func.count()).select_from(StockBalance).where(
            StockBalance.location_id == location_id,
            StockBalance.quantity != 0,
        )) or 0
        active_children = db.scalar(select(func.count()).select_from(Location).where(
            Location.parent_id == location_id,
            Location.is_active.is_(True),
        )) or 0
        open_transfers = db.scalar(select(func.count()).select_from(TransferOrder).where(
            ((TransferOrder.source_location_id == location_id) | (TransferOrder.destination_location_id == location_id)),
            TransferOrder.status.in_(["draft", "approved", "dispatched"]),
        )) or 0
        if nonzero:
            fail(409, "Location with non-zero stock cannot be deactivated")
        if active_children:
            fail(409, "Deactivate child locations first")
        if open_transfers:
            fail(409, "Location with open transfers cannot be deactivated")

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
