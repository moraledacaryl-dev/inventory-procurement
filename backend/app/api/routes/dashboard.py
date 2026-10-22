from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.inventory import Item, Location, StockBalance, StockMovement
from app.models.inventory_operations import ItemLocationSetting
from app.models.procurement import PurchaseOrder, PurchaseOrderLine, Supplier
from app.models.user import User
from app.services.operational_authorization import require_scoped_locations, visible_location_ids

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
        # Growth from a zero denominator is undefined, not a 100% increase.
        return None
    return round((current_value - previous_value) / abs(previous_value) * 100, 1)


@router.get("/summary")
def dashboard_summary(
    location_id: str | None = None,
    days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.read")),
):
    allowed = visible_location_ids(db, user)
    if location_id:
        require_scoped_locations(db, user, {location_id})
    scoped_locations = {location_id} if location_id else allowed
    previous_start, current_start, now = _period_bounds(days)

    items_stmt = select(
        Item.id, Item.sku, Item.name, Item.minimum_stock, Item.is_active, Item.track_stock
    )
    if scoped_locations is not None:
        # A location-scoped operator only sees linked catalogue counts.
        items_stmt = items_stmt.where(or_(
            Item.default_location_id.in_(scoped_locations),
            Item.id.in_(select(StockBalance.item_id).where(
                StockBalance.location_id.in_(scoped_locations)
            )),
            Item.id.in_(select(ItemLocationSetting.item_id).where(
                ItemLocationSetting.location_id.in_(scoped_locations)
            )),
        ))
    item_rows = db.execute(items_stmt.order_by(Item.sku)).all()

    balance_stmt = select(
        StockBalance.item_id,
        func.coalesce(func.sum(StockBalance.quantity), 0).label("quantity"),
        func.coalesce(func.sum(StockBalance.quantity * StockBalance.average_cost), 0).label("value"),
    )
    if scoped_locations is not None:
        balance_stmt = balance_stmt.where(
            StockBalance.location_id.in_(scoped_locations)
        )
    balance_rows = db.execute(balance_stmt.group_by(StockBalance.item_id)).all()
    balance_by_item = {row.item_id: row for row in balance_rows}

    active_items = [row for row in item_rows if row.is_active]
    tracked_items = [row for row in active_items if row.track_stock]
    inactive_count = len(item_rows) - len(active_items)
    # The stock balance ledger is the source of truth for book valuation.
    # Do not substitute standard cost or omit inactive items: both would make
    # Dashboard disagree with /reports/valuation and historical book value.
    inventory_value = sum((Decimal(row.value) for row in balance_rows), Decimal("0"))
    location_minimums = {}
    if location_id:
        overrides = db.scalars(select(ItemLocationSetting).where(
            ItemLocationSetting.location_id == location_id,
            ItemLocationSetting.is_active.is_(True),
        )).all()
        location_minimums = {row.item_id: Decimal(row.minimum_stock) for row in overrides}
    in_stock = low_stock = out_of_stock = 0
    low_items = []

    for item in tracked_items:
        balance = balance_by_item.get(item.id)
        quantity = Decimal(balance.quantity if balance else 0)
        minimum = location_minimums.get(item.id, Decimal(item.minimum_stock or 0))
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

    # Compute PO status counts in SQL. Loading every historical purchase
    # order to count open/overdue work grows unbounded over the years.
    open_po = PurchaseOrder.status.not_in(CLOSED_PO_STATUSES)
    po_counts_stmt = select(
        func.coalesce(func.sum(case((open_po, 1), else_=0)), 0),
        func.coalesce(func.sum(case((
            and_(open_po, PurchaseOrder.expected_delivery_date < date.today()), 1
        ), else_=0)), 0),
    )
    if scoped_locations is not None:
        po_counts_stmt = po_counts_stmt.where(
            PurchaseOrder.delivery_location_id.in_(scoped_locations)
        )
    pending_po_count, overdue_po_count = db.execute(po_counts_stmt).one()

    if scoped_locations is not None:
        supplier_count = db.scalar(select(func.count(func.distinct(Supplier.id))).join(
            PurchaseOrder, PurchaseOrder.supplier_id == Supplier.id
        ).where(
            Supplier.is_active.is_(True),
            PurchaseOrder.delivery_location_id.in_(scoped_locations),
        )) or 0
    else:
        supplier_count = db.scalar(select(func.count()).select_from(Supplier).where(
            Supplier.is_active.is_(True)
        )) or 0

    movement_filters = []
    if scoped_locations is not None:
        movement_filters.append(StockMovement.location_id.in_(scoped_locations))
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

    po_count_filters = (
        [PurchaseOrder.delivery_location_id.in_(scoped_locations)]
        if scoped_locations is not None else []
    )
    current_po_count = db.scalar(
        select(func.count()).select_from(PurchaseOrder).where(
            *po_count_filters,
            PurchaseOrder.created_at >= current_start,
            PurchaseOrder.created_at < now,
        )
    ) or 0
    previous_po_count = db.scalar(
        select(func.count()).select_from(PurchaseOrder).where(
            *po_count_filters,
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
    if scoped_locations is not None:
        recent_po_stmt = recent_po_stmt.where(
            PurchaseOrder.delivery_location_id.in_(scoped_locations)
        )
    recent_po_rows = db.execute(recent_po_stmt).all()

    # One grouped query rather than an additional query per displayed PO.
    recent_po_ids = [po.id for po, _supplier_name in recent_po_rows]
    po_totals = dict(db.execute(
        select(
            PurchaseOrderLine.purchase_order_id,
            func.sum(PurchaseOrderLine.ordered_quantity * PurchaseOrderLine.unit_price),
        )
        .where(PurchaseOrderLine.purchase_order_id.in_(recent_po_ids))
        .group_by(PurchaseOrderLine.purchase_order_id)
    ).all()) if recent_po_ids else {}

    recent_movement_stmt = (
        select(StockMovement, Item.sku, Item.name, Location.name.label("location_name"))
        .join(Item, Item.id == StockMovement.item_id)
        .join(Location, Location.id == StockMovement.location_id)
        .order_by(StockMovement.created_at.desc())
        .limit(5)
    )
    if scoped_locations is not None:
        recent_movement_stmt = recent_movement_stmt.where(
            StockMovement.location_id.in_(scoped_locations)
        )
    recent_movement_rows = db.execute(recent_movement_stmt).all()

    return {
        "as_of": now.isoformat(),
        "filters": {"location_id": location_id, "days": days},
        "metrics": {
            "total_products": len(item_rows),
            "active_products": len(active_items),
            "inactive_products": inactive_count,
            "inventory_value": str(inventory_value),
            "pending_purchase_orders": int(pending_po_count),
            "overdue_purchase_orders": int(overdue_po_count),
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
                "total": str(po_totals.get(po.id, Decimal("0"))),
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
    user: User = Depends(require_permission("inventory.read")),
):
    allowed = visible_location_ids(db, user)
    if location_id:
        require_scoped_locations(db, user, {location_id})
    scoped_locations = {location_id} if location_id else allowed
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days - 1)).date()

    movement_stmt = select(
        func.date(StockMovement.created_at).label("movement_date"),
        func.coalesce(func.sum(
            func.coalesce(StockMovement.book_value_delta, StockMovement.quantity * StockMovement.unit_cost)
        ), 0).label("value_change"),
        func.sum(case((StockMovement.book_value_delta.is_(None), 1), else_=0)).label("legacy_count"),
    ).where(StockMovement.created_at >= datetime.combine(start_date, time.min, tzinfo=timezone.utc))
    if scoped_locations is not None:
        movement_stmt = movement_stmt.where(
            StockMovement.location_id.in_(scoped_locations)
        )
    movement_rows = db.execute(movement_stmt.group_by(func.date(StockMovement.created_at))).all()
    # Legacy rows have no book-value delta. Their signed movement cost is only
    # an estimate where short stock was replenished at a different cost.
    # Do not backfill or silently present historical estimates as exact.
    change_by_date = {str(row.movement_date): Decimal(row.value_change or 0) for row in movement_rows}
    legacy_by_date = {str(row.movement_date): int(row.legacy_count or 0) for row in movement_rows}
    remaining_legacy = sum(legacy_by_date.values())

    balance_stmt = select(func.coalesce(func.sum(StockBalance.quantity * StockBalance.average_cost), 0))
    if scoped_locations is not None:
        balance_stmt = balance_stmt.where(
            StockBalance.location_id.in_(scoped_locations)
        )
    current_value = Decimal(db.scalar(balance_stmt) or 0)

    total_period_change = sum(change_by_date.values(), Decimal("0"))
    running_value = current_value - total_period_change
    points = []
    for offset in range(days):
        point_date = start_date + timedelta(days=offset)
        day = point_date.isoformat()
        running_value += change_by_date.get(day, Decimal("0"))
        # Anchored to today's actual balance: only legacy movements *after*
        # a day's close make that day's historical value uncertain.
        remaining_legacy -= legacy_by_date.get(day, 0)
        points.append({"date": day, "value": str(running_value), "estimated": remaining_legacy > 0})

    return {
        "as_of": now.isoformat(),
        "location_id": location_id,
        "days": days,
        "points": points,
        "current_value": str(current_value),
        "legacy_movement_count": sum(legacy_by_date.values()),
        "historical_values_estimated": any(point["estimated"] for point in points),
    }
