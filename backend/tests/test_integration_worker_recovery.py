from datetime import timedelta

from app.api.routes.final_assurance import snapshot
from app.db.session import SessionLocal
from app.models.operations import IntegrationEvent
from app.services.integration_worker import claim_events, utcnow


def event(*, key: str, status: str = "processing", locked_at=None, locked_by: str = "crashed-worker") -> IntegrationEvent:
    return IntegrationEvent(
        direction="outbound",
        source_system="inventory",
        destination_system="operations",
        event_type="stock.low.alert",
        aggregate_type="stock_balance",
        aggregate_id=key,
        idempotency_key=key,
        payload={"title": "Recovery test"},
        status=status,
        attempts=0,
        max_attempts=8,
        available_at=utcnow() - timedelta(minutes=20),
        locked_at=locked_at,
        locked_by=locked_by,
    )


def test_claim_events_reclaims_stale_processing_without_stealing_fresh_work():
    with SessionLocal() as db:
        stale = event(key="stale-processing", locked_at=utcnow() - timedelta(minutes=11))
        fresh = event(key="fresh-processing", locked_at=utcnow() - timedelta(minutes=1))
        db.add_all([stale, fresh])
        db.commit()
        stale_id, fresh_id = stale.id, fresh.id

        claimed = claim_events(db, "replacement-worker", limit=25)
        assert [row.id for row in claimed] == [stale_id]

        stale = db.get(IntegrationEvent, stale_id)
        fresh = db.get(IntegrationEvent, fresh_id)
        assert stale.status == "processing"
        assert stale.locked_by == "replacement-worker"
        assert fresh.status == "processing"
        assert fresh.locked_by == "crashed-worker"


def test_final_assurance_flags_stale_processing_integrations():
    with SessionLocal() as db:
        db.add(event(key="assurance-stale-processing", locked_at=utcnow() - timedelta(minutes=11)))
        db.commit()

        data = snapshot(db)
        check = next(row for row in data["checks"] if row["key"] == "integration_failures")
        assert check["status"] == "failed"
        assert check["count"] == 1
        assert data["summary"]["stale_processing_integrations"] == 1
