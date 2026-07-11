from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.inventory import Item, Location, StockBalance, StockMovement
from app.models.procurement import PurchaseOrder, PurchaseOrderLine, Supplier
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

CLOSED_PO_STATUSES = {"received", "closed", "cancelled"}


def _period_bounds(days: int) -> tuple[datetime, datetime, datetime]:
    now = datetime.now(timezone.utc)
    current_start = now - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)
    return previous_start, current_start, now


def _percent_change(current: Decimal | int | float, previous: Decimal | int | float) -> float | None:
    current_value = float(current or 0)
    previous_value = float(previous or 0)
    if previous_value == 0:
        return None if current_value == 0 else 100.0
    return round((current_value - previous_value) / abs(previous_value) * 100, 1)


@router.get("/summary")
def dashboard_summary(
    location_id: str | None = None,
    days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.read")),
):
    previous_start, current_start, now = _period_bounds(days)

    item_rows = db.execute(
        select(Item.id, Item.sku, Item.name, Item.minimum_stock, Item.standard_cost, Item.is_active)
        .order_by(Item.sku)
    ).all()

    balance_stmt = select(
        StockBalance.item_id,
        func.coalesce(func.sum(StockBalance.quantity), 0).label("quantity"),
        func.coalesce(func.sum(StockBalance.quantity * StockBalance.average_cost), 0).label("value"),
    )
    if location_id:
        balance_stmt = balance_stmt.where(StockBalance.location_id == location_id)
    balance_rows = db.execute(balance_stmt.group_by(StockBalance.item_id)).all()
    balance_by_item = {row.item_id: row for row in balance_rows}

    active_items = [row for row in item_rows if row.is_active]
    inactive_count = len(item_rows) - len(active_items)
    inventory_value = Decimal("0")
    in_stock = low_stock = out_of_stock = 0
    low_items = []

    for item in active_items:
        balance = balance_by_item.get(item.id)
        quantity = Decimal(balance.quantity if balance else 0)
        value = Decimal(balance.value if balance else 0)
        if value == 0 and quantity != 0:
            value = quantity * Decimal(item.standard_cost or 0)
        inventory_value += value
        minimum = Decimal(item.minimum_stock or 0)
        if quantity <= 0:
            out_of_stock += 1
        elif quantity < minimum:
            low_stock += 1
        else:
            in_stock += 1
        if quantity < minimum:
            low_items.append({
                "id": item.id,
                "sku": item.sku,
                "name": item.name,
                "quantity": str(quantity),
                "minimum_stock": str(minimum),
                "shortfall": str(minimum - quantity),
            })

    po_stmt = select(PurchaseOrder)
    if location_id:
        po_stmt = po_stmt.where(PurchaseOrder.delivery_location_id == location_id)
    purchase_orders = db.scalars(po_stmt).all()
    pending_purchase_orders = [po for po in purchase_orders if po.status not in CLOSED_PO_STATUSES]
    overdue_purchase_orders = [
        po for po in pending_purchase_orders
        if po.expected_delivery_date and po.expected_delivery_date < date.today()
    ]

    supplier_count = db.scalar(select(func.count()).select_from(Supplier).where(Supplier.is_active.is_(True))) or 0

    movement_filters = []
    if location_id:
        movement_filters.append(StockMovement.location_id == location_id)
    current_movements = db.scalar(
        select(func.count()).select_from(StockMovement).where(
            *movement_filters,
            StockMovement.created_at >= current_start,
            StockMovement.created_at < now,
        )
    ) or 0
    previous_movements = db.scalar(
        select(func.count()).select_from(StockMovement).where(
            *movement_filters,
            StockMovement.created_at >= previous_start,
            StockMovement.created_at < current_start,
        )
    ) or 0

    current_po_count = db.scalar(
        select(func.count()).select_from(PurchaseOrder).where(
            *( [PurchaseOrder.delivery_location_id == location_id] if location_id else [] ),
            PurchaseOrder.created_at >= current_start,
            PurchaseOrder.created_at < now,
        )
    ) or 0
    previous_po_count = db.scalar(
        select(func.count()).select_from(PurchaseOrder).where(
            *( [PurchaseOrder.delivery_location_id == location_id] if location_id else [] ),
            PurchaseOrder.created_at >= previous_start,
            PurchaseOrder.created_at < current_start,
        )
    ) or 0

    recent_po_stmt = (
        select(PurchaseOrder, Supplier.name.label("supplier_name"))
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .order_by(PurchaseOrder.created_at.desc())
        .limit(5)
    )
    if location_id:
        recent_po_stmt = recent_po_stmt.where(PurchaseOrder.delivery_location_id == location_id)
    recent_po_rows = db.execute(recent_po_stmt).all()

    po_totals = {
        po.id: db.scalar(
            select(func.coalesce(func.sum(PurchaseOrderLine.ordered_quantity * PurchaseOrderLine.unit_price), 0))
            .where(PurchaseOrderLine.purchase_order_id == po.id)
        ) or Decimal("0")
        for po, _supplier_name in recent_po_rows
    }

    recent_movement_stmt = (
        select(StockMovement, Item.sku, Item.name, Location.name.label("location_name"))
        .join(Item, Item.id == StockMovement.item_id)
        .join(Location, Location.id == StockMovement.location_id)
        .order_by(StockMovement.created_at.desc())
        .limit(5)
    )
    if location_id:
        recent_movement_stmt = recent_movement_stmt.where(StockMovement.location_id == location_id)
    recent_movement_rows = db.execute(recent_movement_stmt).all()

    return {
        "as_of": now.isoformat(),
        "filters": {"location_id": location_id, "days": days},
        "metrics": {
            "total_products": len(item_rows),
            "active_products": len(active_items),
            "inactive_products": inactive_count,
            "inventory_value": str(inventory_value),
            "pending_purchase_orders": len(pending_purchase_orders),
            "overdue_purchase_orders": len(overdue_purchase_orders),
            "low_stock_items": low_stock,
            "out_of_stock_items": out_of_stock,
            "active_suppliers": supplier_count,
            "movement_count": current_movements,
        },
        "comparisons": {
            "movement_count_change_percent": _percent_change(current_movements, previous_movements),
            "purchase_order_count_change_percent": _percent_change(current_po_count, previous_po_count),
            "current_purchase_order_count": current_po_count,
            "previous_purchase_order_count": previous_po_count,
        },
        "stock_status": {
            "in_stock": in_stock,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "inactive": inactive_count,
        },
        "low_stock": sorted(low_items, key=lambda row: Decimal(row["shortfall"]), reverse=True)[:6],
        "recent_purchase_orders": [
            {
                "id": po.id,
                "purchase_order_number": po.purchase_order_number,
                "supplier_name": supplier_name,
                "status": po.status,
                "created_at": po.created_at.isoformat(),
                "expected_delivery_date": po.expected_delivery_date.isoformat() if po.expected_delivery_date else None,
                "total": str(po_totals[po.id]),
            }
            for po, supplier_name in recent_po_rows
        ],
        "recent_movements": [
            {
                "id": movement.id,
                "item_id": movement.item_id,
                "sku": sku,
                "item_name": item_name,
                "location_name": location_name,
                "quantity": str(movement.quantity),
                "reason": movement.reason,
                "created_at": movement.created_at.isoformat(),
            }
            for movement, sku, item_name, location_name in recent_movement_rows
        ],
    }


@router.get("/valuation-history")
def valuation_history(
    location_id: str | None = None,
    days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.read")),
):
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days - 1)).date()

    movement_stmt = select(
        func.date(StockMovement.created_at).label("movement_date"),
        func.coalesce(func.sum(StockMovement.quantity * StockMovement.unit_cost), 0).label("value_change"),
    ).where(StockMovement.created_at >= datetime.combine(start_date, time.min, tzinfo=timezone.utc))
    if location_id:
        movement_stmt = movement_stmt.where(StockMovement.location_id == location_id)
    movement_rows = db.execute(movement_stmt.group_by(func.date(StockMovement.created_at))).all()
    change_by_date = {row.movement_date: Decimal(row.value_change or 0) for row in movement_rows}

    balance_stmt = select(func.coalesce(func.sum(StockBalance.quantity * StockBalance.average_cost), 0))
    if location_id:
        balance_stmt = balance_stmt.where(StockBalance.location_id == location_id)
    current_value = Decimal(db.scalar(balance_stmt) or 0)

    total_period_change = sum(change_by_date.values(), Decimal("0"))
    running_value = current_value - total_period_change
    points = []
    for offset in range(days):
        point_date = start_date + timedelta(days=offset)
        running_value += change_by_date.get(point_date, Decimal("0"))
        points.append({"date": point_date.isoformat(), "value": str(running_value)})

    return {
        "as_of": now.isoformat(),
        "location_id": location_id,
        "days": days,
        "points": points,
        "current_value": str(current_value),
    }
