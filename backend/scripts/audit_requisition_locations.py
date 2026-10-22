"""Read-only migration acceptance report for authoritative requisition locations.

Run with the Inventory backend environment, after migration 0024:
    python scripts/audit_requisition_locations.py

No record is assigned/reassigned. Legacy notes and downstream PO locations
are *never* treated as verified ownership. Review unmatched records manually.
"""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.procurement import PurchaseOrder, PurchaseRequisition, SupplierQuotation
from app.models.inventory import Location


def report(db: Session) -> dict:
    reqs = db.execute(select(
        PurchaseRequisition.id, PurchaseRequisition.requisition_number,
        PurchaseRequisition.status, PurchaseRequisition.location_id,
    ).order_by(PurchaseRequisition.requisition_number)).all()
    quotes = db.execute(select(
        SupplierQuotation.id, SupplierQuotation.requisition_id,
    )).all()
    pos = db.execute(select(
        PurchaseOrder.id, PurchaseOrder.purchase_order_number,
        PurchaseOrder.requisition_id, PurchaseOrder.delivery_location_id,
    )).all()
    owned_by_id = {r.id: r.location_id for r in reqs}
    unassigned = [r for r in reqs if r.location_id is None]
    linked_quotes = sum(1 for q in quotes if q.requisition_id in owned_by_id
                        and owned_by_id[q.requisition_id] is None)
    conflicting_pos = [
        {
            "purchase_order_id": po.id,
            "purchase_order_number": po.purchase_order_number,
            "requisition_id": po.requisition_id,
            "requisition_location_id": owned_by_id.get(po.requisition_id),
            "delivery_location_id": po.delivery_location_id,
        }
        for po in pos
        if po.requisition_id in owned_by_id
        and owned_by_id[po.requisition_id] is not None
        and owned_by_id[po.requisition_id] != po.delivery_location_id
    ]
    orphaned_location_ids = sorted({
        r.location_id for r in reqs if r.location_id is not None
    } - set(db.scalars(select(Location.id)).all()))
    return {
        "read_only": True,
        "migration": "0024_requisition_location_owner",
        "requisition_total": len(reqs),
        "authoritatively_assigned": len(reqs) - len(unassigned),
        "unassigned_requires_review": len(unassigned),
        "unassigned_by_status": {
            status: sum(r.status == status for r in unassigned)
            for status in sorted({r.status for r in unassigned})
        },
        "quotations_linked_to_unassigned": linked_quotes,
        "unassigned_with_purchase_orders": sum(
            po.requisition_id in owned_by_id
            and owned_by_id[po.requisition_id] is None
            for po in pos
        ),
        "typed_location_po_conflicts": len(conflicting_pos),
        "conflicts_sample": conflicting_pos[:25],
        "invalid_location_ids": orphaned_location_ids,
        "unassigned_sample": [
            {"requisition_id": r.id, "requisition_number": r.requisition_number,
             "status": r.status} for r in unassigned[:25]
        ],
        "instruction": (
            "Historical requisitions are deliberately unassigned. "
            "Use original approved documentation to review and explicitly "
            "authorize each assignment; never backfill from free-text notes."
        ),
    }


def main() -> None:
    with SessionLocal() as db:
        # Executes SELECT only; never commit, flush, alter, or update.
        result = report(db)
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
