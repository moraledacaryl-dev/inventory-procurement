#!/usr/bin/env python3
"""Private, read-only Inventory Accounting outbox identity export.

No transport request, retry, ledger posting, payload, item name, supplier
information, stock quantity, account identifier or financial amount is exported.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.operations import IntegrationEvent


def export_inventory_outbox(db: Session) -> dict:
    # No LIMIT: source completeness must not be defeated by workspace pagination.
    rows = db.execute(
        select(IntegrationEvent.id, IntegrationEvent.destination_system,
               IntegrationEvent.status)
        .where(IntegrationEvent.direction == 'outbound')
        .where(IntegrationEvent.destination_system == 'accounting')
        .order_by(IntegrationEvent.created_at, IntegrationEvent.id)
    ).all()
    events = []
    for event_id, destination, status in rows:
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("Inventory outbox has no stable Accounting source event ID.")
        events.append({
            "id": event_id,
            "destination_system": destination,
            "status": status,
        })
    return {
        "source": "inventory",
        "export_type": "inventory_accounting_outbox_identities",
        "full_source_scan": True,
        # No cross-DB snapshot barrier or Accounting-side coordinated cutoff.
        "complete_for_window": False,
        "events": events,
        "caveat": (
            "Inventory producer event ID is the Accounting source_event_id (revision 1). "
            "Completed proves only intake delivery, not approval, journal posting, "
            "upstream completeness or settled cash/bank balances."
        ),
    }


def write_private(path: Path, result: dict) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None
            json.dump(result, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    finally:
        if fd is not None:
            os.close(fd)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path,
                        help="New absolute protected JSON path; never overwrites")
    args = parser.parse_args(argv)
    if not args.output.is_absolute():
        parser.error("--output must be an absolute path")
    from app.db.session import engine
    # Do not silently fall back to disposable SQLite or use a writable database
    # transaction on a production data source.
    if engine.dialect.name != "postgresql":
        parser.error("PostgreSQL production connection required for protected export")
    with engine.connect() as connection:
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")
        connection.exec_driver_sql("SET LOCAL statement_timeout = '30000ms'")
        try:
            with Session(bind=connection, autoflush=False) as db:
                data = export_inventory_outbox(db)
        finally:
            connection.rollback()
    write_private(args.output, data)
    print(f"INVENTORY ACCOUNTING SOURCE IDENTITY EXPORT: PASS | events={len(data['events'])}")
    print("ACCOUNTING RECEIPTS, POSTINGS AND CROSS-APP COMPLETENESS: NOT VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
