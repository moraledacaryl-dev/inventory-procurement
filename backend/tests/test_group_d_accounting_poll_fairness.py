"""Group D: completed financial deliveries beyond the old 600-row cap are polled fairly."""
from datetime import timedelta

import httpx

from app.db.session import SessionLocal
from app.models.operations import IntegrationEvent
from app.services.integration_worker import reconcile_accounting_reviews, utcnow


def test_old_unverified_accounting_event_is_never_starved_by_recent_600(monkeypatch):
    monkeypatch.setenv("INTEGRATION_API_KEY", "isolated-proof-key")
    now = utcnow()
    with SessionLocal() as db:
        oldest = IntegrationEvent(
            direction="outbound", source_system="inventory",
            destination_system="accounting",
            event_type="inventory.stock_document.posted",
            aggregate_type="stock_document", aggregate_id="old-unverified",
            idempotency_key="group-d-old-proof",
            payload={"accounting_intake": {"status": "ready_for_review"}},
            status="completed", created_at=now - timedelta(days=2),
        )
        db.add(oldest)
        db.flush()
        old_id = oldest.id
        newer = [
            IntegrationEvent(
                direction="outbound", source_system="inventory",
                destination_system="accounting",
                event_type="inventory.stock_document.posted",
                aggregate_type="stock_document", aggregate_id=f"new-{index}",
                idempotency_key=f"group-d-new-proof-{index}",
                payload={
                    "accounting_reconciliation": {
                        "checked_at": now.isoformat(), "ledger_posting_confirmed": False,
                    },
                },
                status="completed",
                created_at=now - timedelta(hours=1) + timedelta(seconds=index),
            )
            for index in range(625)
        ]
        db.add_all(newer)
        db.commit()

        seen = []

        def handler(request):
            event_id = request.url.params["source_event_id"]
            seen.append(event_id)
            return httpx.Response(200, request=request, json={
                "source_app": "inventory",
                "source_event_id": event_id,
                "review_status": "ready_for_review",
                "ledger_posting_confirmed": False,
            })

        with httpx.Client(transport=httpx.MockTransport(handler)) as mock:
            result = reconcile_accounting_reviews(
                db, {"accounting": "https://accounting.example"}, mock, limit=4,
            )
        assert result == {"checked": 1, "confirmed": 0, "errors": 0}
        assert seen == [old_id]
        db.refresh(oldest)
        assert oldest.payload["accounting_reconciliation"]["review_status"] == "ready_for_review"
        assert oldest.payload["accounting_reconciliation"]["ledger_posting_confirmed"] is False
