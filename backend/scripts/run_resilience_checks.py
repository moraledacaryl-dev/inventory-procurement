from __future__ import annotations

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select, update

from app.db.session import SessionLocal, engine
from app.models.inventory import Item, Location, StockBalance, StockDocument
from app.models.operations import DocumentSequence, IntegrationEvent, Notification
from app.models.user import User
from app.services.controls import next_document_number
from app.services.integration_worker import claim_events, process_event
from app.services.inventory import InventoryError, post_document


def assert_postgres() -> None:
    if engine.dialect.name != "postgresql":
        raise SystemExit(f"Resilience checks require PostgreSQL, got {engine.dialect.name}")


def scalar_ids() -> tuple[str, str, str]:
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        item = db.scalar(select(Item).where(Item.sku == "COFFEE-BEAN"))
        location = db.scalar(select(Location).where(Location.code == "MAIN"))
        if not owner or not item or not location:
            raise SystemExit("Acceptance seed data is incomplete")
        return owner.id, item.id, location.id


def balance(item_id: str, location_id: str) -> Decimal:
    with SessionLocal() as db:
        row = db.scalar(select(StockBalance).where(StockBalance.item_id == item_id, StockBalance.location_id == location_id))
        return Decimal(row.quantity if row else 0)


def concurrent_negative_stock(owner_id: str, item_id: str, location_id: str) -> dict:
    start = balance(item_id, location_id)
    if start < Decimal("20"):
        raise AssertionError(f"Expected at least 20 units before stock race, got {start}")
    barrier = threading.Barrier(2)

    def issue(index: int) -> str:
        with SessionLocal() as db:
            barrier.wait()
            try:
                doc = post_document(
                    db,
                    kind="resilience_issue",
                    actor_id=owner_id,
                    reference=f"RACE-ISSUE-{index}",
                    idempotency_key=f"resilience-issue-{uuid4()}",
                    entries=[{"item_id": item_id, "location_id": location_id, "quantity": Decimal("-15"), "unit_cost": Decimal("650"), "reason": "concurrency assurance"}],
                )
                return f"success:{doc.id}"
            except InventoryError as exc:
                return f"rejected:{exc}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(issue, range(2)))
    successes = [value for value in outcomes if value.startswith("success:")]
    rejections = [value for value in outcomes if value.startswith("rejected:")]
    final = balance(item_id, location_id)
    if len(successes) != 1 or len(rejections) != 1 or final != start - Decimal("15") or final < 0:
        raise AssertionError({"test": "negative_stock", "start": str(start), "final": str(final), "outcomes": outcomes})
    return {"start": str(start), "final": str(final), "outcomes": outcomes}


def concurrent_idempotency(owner_id: str, item_id: str, location_id: str) -> dict:
    start = balance(item_id, location_id)
    key = f"resilience-duplicate-{uuid4()}"
    barrier = threading.Barrier(2)

    def receipt(_: int) -> str:
        with SessionLocal() as db:
            barrier.wait()
            doc = post_document(
                db,
                kind="resilience_receipt",
                actor_id=owner_id,
                reference="RACE-DUPLICATE",
                idempotency_key=key,
                entries=[{"item_id": item_id, "location_id": location_id, "quantity": Decimal("2"), "unit_cost": Decimal("650"), "reason": "idempotency assurance"}],
            )
            return doc.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        document_ids = list(pool.map(receipt, range(2)))
    final = balance(item_id, location_id)
    with SessionLocal() as db:
        count = int(db.scalar(select(func.count()).select_from(StockDocument).where(StockDocument.idempotency_key == key)) or 0)
    if len(set(document_ids)) != 1 or count != 1 or final != start + Decimal("2"):
        raise AssertionError({"test": "idempotency", "start": str(start), "final": str(final), "document_ids": document_ids, "count": count})
    return {"start": str(start), "final": str(final), "document_id": document_ids[0]}


def concurrent_document_numbers() -> dict:
    prefix = f"RS{uuid4().hex[:8].upper()}"[:20]
    workers = 8
    barrier = threading.Barrier(workers)

    def allocate(_: int) -> str:
        with SessionLocal() as db:
            barrier.wait()
            value = next_document_number(db, prefix)
            db.commit()
            return value

    with ThreadPoolExecutor(max_workers=workers) as pool:
        values = list(pool.map(allocate, range(workers)))
    if len(set(values)) != workers:
        raise AssertionError({"test": "document_numbers", "values": values})
    with SessionLocal() as db:
        sequence = db.get(DocumentSequence, prefix)
        if sequence is None or sequence.next_value != workers + 1:
            raise AssertionError({"test": "document_sequence_state", "next_value": None if sequence is None else sequence.next_value})
    return {"prefix": prefix, "values": sorted(values)}


def concurrent_worker_claims() -> dict:
    marker = uuid4().hex
    event_ids: list[str] = []
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        db.execute(
            update(IntegrationEvent)
            .where(IntegrationEvent.direction == "outbound", IntegrationEvent.status.in_(["pending", "failed"]))
            .values(status="completed", processed_at=now, locked_at=None, locked_by=None)
        )
        for index in range(12):
            event = IntegrationEvent(
                direction="outbound",
                source_system="inventory",
                destination_system="resilience-target",
                event_type="resilience.claim",
                aggregate_type="test",
                aggregate_id=f"{marker}-{index}",
                idempotency_key=f"resilience-claim-{marker}-{index}",
                payload={"index": index},
            )
            db.add(event)
            db.flush()
            event_ids.append(event.id)
        db.commit()
    barrier = threading.Barrier(2)

    def claim(worker: str) -> list[str]:
        with SessionLocal() as db:
            barrier.wait()
            return [event.id for event in claim_events(db, worker, 12)]

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(claim, ["worker-a", "worker-b"]))
    claimed = first + second
    if set(first) & set(second) or set(claimed) != set(event_ids):
        raise AssertionError({"test": "worker_claims", "first": first, "second": second, "expected": event_ids})
    return {"worker_a": len(first), "worker_b": len(second), "total": len(claimed)}


def retry_and_dead_letter() -> dict:
    marker = uuid4().hex
    with SessionLocal() as db:
        event = IntegrationEvent(
            direction="outbound",
            source_system="inventory",
            destination_system="missing-target",
            event_type="resilience.retry",
            aggregate_type="test",
            aggregate_id=marker,
            idempotency_key=f"resilience-retry-{marker}",
            payload={"marker": marker},
            max_attempts=2,
        )
        db.add(event)
        db.commit()
        event_id = event.id

    with SessionLocal() as db:
        claimed = claim_events(db, "retry-worker", 1)
        if not claimed or claimed[0].id != event_id:
            raise AssertionError("Retry event was not claimed")
        first = process_event(db, event_id, "retry-worker", endpoints={})
        if first.status != "failed" or first.attempts != 1:
            raise AssertionError({"test": "retry_first", "status": first.status, "attempts": first.attempts})
        first.available_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    with SessionLocal() as db:
        claimed = claim_events(db, "retry-worker", 1)
        if not claimed or claimed[0].id != event_id:
            raise AssertionError("Retry event was not reclaimed")
        second = process_event(db, event_id, "retry-worker", endpoints={})
        if second.status != "dead_letter" or second.attempts != 2:
            raise AssertionError({"test": "retry_dead_letter", "status": second.status, "attempts": second.attempts})
        notification_count = int(db.scalar(select(func.count()).select_from(Notification).where(Notification.title == "Integration event requires attention")) or 0)
        if notification_count < 1:
            raise AssertionError("Dead-letter notification was not created")
    return {"event_id": event_id, "status": "dead_letter", "attempts": 2}


def main() -> None:
    assert_postgres()
    owner_id, item_id, location_id = scalar_ids()
    results = {
        "negative_stock": concurrent_negative_stock(owner_id, item_id, location_id),
        "idempotency": concurrent_idempotency(owner_id, item_id, location_id),
        "document_numbers": concurrent_document_numbers(),
        "worker_claims": concurrent_worker_claims(),
        "retry_dead_letter": retry_and_dead_letter(),
    }
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
