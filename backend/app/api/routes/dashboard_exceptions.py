from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.inventory import CountLine, CountSession, Item, Location, StockBalance
from app.models.inventory_operations import InventoryLot, LotBalance, TransferOrder
from app.models.operations import BackupRecord, IntegrationEvent
from app.models.procurement import PurchaseOrder, Supplier
from app.models.production import ProductionBatch, Recipe, RecipeLine
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

ROLE_FOCUS = {
    "owner": {
        "title": "Management control centre",
        "summary": "Prioritize financial exposure, overdue work, control exceptions, and system reliability.",
        "categories": ["procurement", "inventory", "counts", "production", "integration", "backup"],
        "quick_actions": [
            {"label": "Review overdue POs", "href": "/purchasing?status=overdue"},
            {"label": "Review count variances", "href": "/counts?status=review"},
            {"label": "Open integration control", "href": "/integrations?status=exception"},
            {"label": "Open reports", "href": "/reports"},
        ],
    },
    "inventory_manager": {
        "title": "Inventory control workspace",
        "summary": "Resolve stock, count, transfer, expiry, and production-availability exceptions.",
        "categories": ["inventory", "counts", "production", "procurement"],
        "quick_actions": [
            {"label": "Review low stock", "href": "/purchasing?view=low-stock"},
            {"label": "Review count variances", "href": "/counts?status=review"},
            {"label": "Receive transfers", "href": "/inventory-operations?view=transfers"},
            {"label": "Review expiry", "href": "/reports?report=expiry"},
        ],
    },
    "procurement_officer": {
        "title": "Procurement action workspace",
        "summary": "Prioritize overdue orders, supplier follow-up, and stock replenishment.",
        "categories": ["procurement", "inventory"],
        "quick_actions": [
            {"label": "Review overdue POs", "href": "/purchasing?status=overdue"},
            {"label": "Review low stock", "href": "/purchasing?view=low-stock"},
            {"label": "Create requisition", "href": "/purchasing?create=requisition"},
            {"label": "Supplier directory", "href": "/suppliers"},
        ],
    },
    "receiver": {
        "title": "Receiving action workspace",
        "summary": "Focus on expected deliveries, overdue purchase orders, and dispatched transfers.",
        "categories": ["procurement", "inventory"],
        "quick_actions": [
            {"label": "Receive purchase order", "href": "/receiving"},
            {"label": "Receive transfer", "href": "/inventory-operations?view=transfers"},
            {"label": "View open POs", "href": "/purchasing?status=open"},
        ],
    },
    "counter": {
        "title": "Stock count workspace",
        "summary": "Complete assigned counts and resolve recount requirements.",
        "categories": ["counts", "inventory"],
        "quick_actions": [
            {"label": "Open counts", "href": "/counts"},
            {"label": "Review stock", "href": "/stock"},
        ],
    },
    "viewer": {
        "title": "Read-only operations overview",
        "summary": "Monitor current operational conditions without transaction access.",
        "categories": ["procurement", "inventory", "counts", "production", "integration", "backup"],
        "quick_actions": [{"label": "Open reports", "href": "/reports"}],
    },
}


def _exception(
    *,
    key: str,
    category: str,
    severity: str,
    title: str,
    message: str,
    count: int,
    href: str,
    oldest_at: datetime | date | None = None,
) -> dict:
    return {
        "key": key,
        "category": category,
        "severity": severity,
        "title": title,
        "message": message,
        "count": count,
        "href": href,
        "oldest_at": oldest_at.isoformat() if oldest_at else None,
    }


@router.get("/exceptions")
def dashboard_exceptions(
    location_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.read")),
):
    now = datetime.now(timezone.utc)
    today = date.today()
    exceptions: list[dict] = []

    po_stmt = (
        select(PurchaseOrder, Supplier.name.label("supplier_name"))
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .where(
            PurchaseOrder.expected_delivery_date.is_not(None),
            PurchaseOrder.expected_delivery_date < today,
            PurchaseOrder.status.not_in(["received", "closed", "cancelled"]),
        )
        .order_by(PurchaseOrder.expected_delivery_date)
    )
    if location_id:
        po_stmt = po_stmt.where(PurchaseOrder.delivery_location_id == location_id)
    overdue_pos = db.execute(po_stmt).all()
    if overdue_pos:
        oldest_po, supplier_name = overdue_pos[0]
        exceptions.append(_exception(
            key="overdue_purchase_orders",
            category="procurement",
            severity="critical" if len(overdue_pos) >= 5 else "warning",
            title="Overdue purchase orders",
            message=f"{len(overdue_pos)} open order(s) are past their expected delivery date. Oldest: {oldest_po.purchase_order_number} from {supplier_name}.",
            count=len(overdue_pos),
            href="/purchasing?status=overdue",
            oldest_at=oldest_po.expected_delivery_date,
        ))

    count_stmt = (
        select(CountSession)
        .options(selectinload(CountSession.lines))
        .where(CountSession.status.not_in(["posted", "cancelled"]))
        .order_by(CountSession.created_at)
    )
    if location_id:
        count_stmt = count_stmt.where(CountSession.location_id == location_id)
    sessions = db.scalars(count_stmt).unique().all()
    variance_sessions = []
    variance_lines = 0
    for session in sessions:
        line_count = sum(
            1 for line in session.lines
            if line.counted_quantity is not None and Decimal(line.counted_quantity) != Decimal(line.system_quantity)
        )
        if line_count:
            variance_sessions.append(session)
            variance_lines += line_count
    if variance_sessions:
        exceptions.append(_exception(
            key="count_variances",
            category="counts",
            severity="warning",
            title="Count variances awaiting resolution",
            message=f"{variance_lines} variance line(s) across {len(variance_sessions)} count session(s) require review, recount, or approval.",
            count=len(variance_sessions),
            href="/counts?status=review",
            oldest_at=min(session.created_at for session in variance_sessions),
        ))

    transfer_stmt = select(TransferOrder).where(TransferOrder.status == "dispatched").order_by(TransferOrder.dispatched_at)
    if location_id:
        transfer_stmt = transfer_stmt.where(TransferOrder.destination_location_id == location_id)
    transfers = db.scalars(transfer_stmt).all()
    if transfers:
        exceptions.append(_exception(
            key="dispatched_transfers",
            category="inventory",
            severity="warning",
            title="Transfers awaiting receipt",
            message=f"{len(transfers)} dispatched transfer(s) have not been acknowledged at the destination.",
            count=len(transfers),
            href="/inventory-operations?view=transfers&status=dispatched",
            oldest_at=transfers[0].dispatched_at,
        ))

    expiry_cutoff = today + timedelta(days=30)
    expiry_stmt = (
        select(LotBalance, InventoryLot, Item)
        .join(InventoryLot, InventoryLot.id == LotBalance.lot_id)
        .join(Item, Item.id == InventoryLot.item_id)
        .where(
            LotBalance.quantity > 0,
            InventoryLot.expiry_date.is_not(None),
            InventoryLot.expiry_date <= expiry_cutoff,
        )
        .order_by(InventoryLot.expiry_date)
    )
    if location_id:
        expiry_stmt = expiry_stmt.where(LotBalance.location_id == location_id)
    expiring = db.execute(expiry_stmt).all()
    if expiring:
        expired_count = sum(1 for _balance, lot, _item in expiring if lot.expiry_date < today)
        first_balance, first_lot, first_item = expiring[0]
        exceptions.append(_exception(
            key="expiring_inventory",
            category="inventory",
            severity="critical" if expired_count else "warning",
            title="Expired or near-expiry inventory",
            message=f"{len(expiring)} lot balance(s) expire within 30 days; {expired_count} are already expired. Earliest: {first_item.sku} lot {first_lot.lot_number}.",
            count=len(expiring),
            href="/reports?report=expiry&days=30",
            oldest_at=first_lot.expiry_date,
        ))

    failed_events = db.scalars(
        select(IntegrationEvent)
        .where(IntegrationEvent.status.in_(["failed", "dead_letter"]))
        .order_by(IntegrationEvent.created_at)
    ).all()
    if failed_events:
        dead_letters = sum(1 for event in failed_events if event.status == "dead_letter")
        exceptions.append(_exception(
            key="failed_integrations",
            category="integration",
            severity="critical" if dead_letters else "warning",
            title="Integration events require intervention",
            message=f"{len(failed_events)} failed event(s), including {dead_letters} dead-letter event(s), require investigation or safe retry.",
            count=len(failed_events),
            href="/integrations?status=exception",
            oldest_at=failed_events[0].created_at,
        ))

    accounting_events = db.scalars(
        select(IntegrationEvent)
        .where(
            func.lower(IntegrationEvent.destination_system).like("%account%"),
            IntegrationEvent.status.in_(["failed", "dead_letter"]),
        )
        .order_by(IntegrationEvent.created_at)
    ).all()
    if accounting_events:
        exceptions.append(_exception(
            key="accounting_posting_failures",
            category="integration",
            severity="critical",
            title="Accounting postings failed",
            message=f"{len(accounting_events)} inventory event(s) have not reached Accounting successfully.",
            count=len(accounting_events),
            href="/integrations?destination=accounting&status=exception",
            oldest_at=accounting_events[0].created_at,
        ))

    batch_stmt = select(ProductionBatch).where(ProductionBatch.status == "planned").order_by(ProductionBatch.created_at)
    if location_id:
        batch_stmt = batch_stmt.where(ProductionBatch.location_id == location_id)
    batches = db.scalars(batch_stmt).all()
    shortage_batches = []
    for batch in batches:
        recipe = db.scalar(select(Recipe).where(Recipe.id == batch.recipe_id).options(selectinload(Recipe.lines)))
        if not recipe or Decimal(recipe.yield_quantity or 0) <= 0:
            shortage_batches.append(batch)
            continue
        multiplier = Decimal(batch.planned_quantity) / Decimal(recipe.yield_quantity)
        short = False
        for line in recipe.lines:
            required = Decimal(line.quantity) * (Decimal("1") + Decimal(line.waste_factor or 0)) * multiplier
            balance = db.scalar(select(StockBalance).where(
                StockBalance.item_id == line.ingredient_item_id,
                StockBalance.location_id == batch.location_id,
            ))
            available = Decimal(balance.quantity) if balance else Decimal("0")
            if not line.optional and available < required:
                short = True
                break
        if short:
            shortage_batches.append(batch)
    if shortage_batches:
        exceptions.append(_exception(
            key="production_shortages",
            category="production",
            severity="warning",
            title="Planned production has shortages",
            message=f"{len(shortage_batches)} planned batch(es) do not currently have enough required ingredients at their production location.",
            count=len(shortage_batches),
            href="/production?status=shortage",
            oldest_at=shortage_batches[0].created_at,
        ))

    latest_backup = db.scalar(select(BackupRecord).order_by(BackupRecord.created_at.desc()).limit(1))
    backup_stale = not latest_backup or latest_backup.created_at < now - timedelta(hours=26)
    backup_failed = latest_backup and latest_backup.status != "completed"
    if backup_stale or backup_failed:
        message = "No successful backup record exists." if not latest_backup else (
            f"Latest backup status is {latest_backup.status}." if backup_failed
            else f"Latest backup is older than 26 hours: {latest_backup.filename}."
        )
        exceptions.append(_exception(
            key="backup_health",
            category="backup",
            severity="critical",
            title="Backup protection requires attention",
            message=message,
            count=1,
            href="/readiness?check=backup",
            oldest_at=latest_backup.created_at if latest_backup else None,
        ))

    focus = ROLE_FOCUS.get(user.role, ROLE_FOCUS["viewer"])
    visible = [item for item in exceptions if item["category"] in focus["categories"]]
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    visible.sort(key=lambda item: (severity_rank.get(item["severity"], 9), item["oldest_at"] or ""))

    return {
        "as_of": now.isoformat(),
        "role": user.role,
        "workspace": focus,
        "summary": {
            "total": len(visible),
            "critical": sum(1 for item in visible if item["severity"] == "critical"),
            "warning": sum(1 for item in visible if item["severity"] == "warning"),
        },
        "exceptions": visible,
    }
