"""Group A: immutable outbound financial contracts and safe concurrency recovery.

All HTTP requests use mock transports. Production Accounting/POS is not contacted.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Event
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select

from app.db.session import SessionLocal, engine
from app.models.operations import IntegrationEvent
from app.services.integration_worker import (
    _accounting_payload, accounting_envelope, claim_events, process_event, utcnow,
)


def event(kind, payload):
    return SimpleNamespace(
        id="accounting-group-a-event", event_type=kind, aggregate_type="goods_receipt",
        aggregate_id="receipt-1", idempotency_key="group-a:receipt-1",
        payload=payload, attempts=0,
    )


def test_accounting_retry_does_not_mutate_financial_envelope_with_local_delivery_metadata():
    source = event("procurement.goods_received", {
        "goods_receipt_number": "GR-1", "purchase_order_id": "PO-1",
        "supplier_id": "SUP-1", "lines": [
            {"accepted_quantity": "3.5", "unit_cost": "12.50"},
        ],
    })
    initial = accounting_envelope(source)
    source.payload["accounting_intake"] = {
        "status": "accepted", "review_id": "R-1", "received_at": "2026-10-01T00:00:00Z",
    }
    source.payload["accounting_reconciliation"] = {
        "review_status": "accepted", "ledger_posting_confirmed": True,
    }
    source.payload["accounting_receipt"] = {"accepted": True}
    source.attempts = 3
    retried = accounting_envelope(source)
    assert initial == retried
    assert retried["amount"] == 43.75
    assert not any(k.startswith("accounting_") for k in retried["payload"]["data"])

    with SessionLocal() as db:
        row = IntegrationEvent(
            id=source.id,
            direction="outbound", source_system="inventory",
            destination_system="accounting", event_type=source.event_type,
            aggregate_type=source.aggregate_type, aggregate_id=source.aggregate_id,
            idempotency_key=source.idempotency_key, payload=source.payload,
        )
        assert accounting_envelope(row, _accounting_payload(db, row)) == initial


@pytest.mark.parametrize("quantity,cost", [
    ("NaN", "12"), ("Infinity", "12"), ("-1", "12"),
    ("3", "-0.01"), ("abc", "12"), (None, "12"), ("2", None),
])
def test_goods_receipt_accounting_contract_rejects_invalid_monetary_evidence(quantity, cost):
    with pytest.raises(ValueError, match="Accounting"):
        accounting_envelope(event("procurement.goods_received", {
            "lines": [{"accepted_quantity": quantity, "unit_cost": cost}],
        }))


@pytest.mark.parametrize("payload", [
    {"lines": []}, {"lines": None},
    {"lines": [{"accepted_quantity": "1"}]},
    {"lines": "not-a-list"},
])
def test_goods_receipt_requires_real_accepted_lines(payload):
    with pytest.raises(ValueError, match="Accounting"):
        accounting_envelope(event("procurement.goods_received", payload))


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-1", "bogus", None])
def test_purchase_return_invalid_total_fails_closed(amount):
    with pytest.raises(ValueError, match="Accounting"):
        accounting_envelope(event("procurement.purchase_return.posted", {
            "purchase_return_id": "RET-1", "total": amount,
        }))


def test_financial_validation_failure_schedules_retry_without_transmission():
    with SessionLocal() as db:
        row = IntegrationEvent(
            direction="outbound", source_system="inventory",
            destination_system="accounting", event_type="procurement.goods_received",
            aggregate_type="goods_receipt", aggregate_id="bad-amount",
            idempotency_key="bad-amount-intake", payload={
                "lines": [{"accepted_quantity": "NaN", "unit_cost": "12"}],
            },
            status="processing", locked_by="validation-worker",
        )
        db.add(row)
        db.commit()
        event_id = row.id
        transmissions = []
        transport = httpx.MockTransport(lambda req: (
            transmissions.append(req),
            httpx.Response(200, json={"id": 1, "status": "ready_for_review"}, request=req),
        )[1])
        with httpx.Client(transport=transport) as mock:
            result = process_event(
                db, event_id, "validation-worker",
                endpoints={"accounting": "https://accounting.test"}, client=mock,
            )
        assert result.status == "failed"
        assert result.attempts == 1
        assert not transmissions
        assert "Accounting" in result.last_error


def test_active_delivery_holds_postgres_claim_lock_until_outcome_commit():
    if engine.dialect.name != "postgresql":
        pytest.skip("SKIP LOCKED claim fencing requires PostgreSQL")

    with SessionLocal() as db:
        row = IntegrationEvent(
            direction="outbound", source_system="inventory",
            destination_system="accounting",
            event_type="inventory.stock_document.posted",
            aggregate_type="stock_document", aggregate_id="long-http",
            idempotency_key="long-http-claim-lock", payload={"lines": []},
            status="processing", locked_by="original-worker",
            locked_at=utcnow()-timedelta(minutes=11),
            available_at=utcnow()-timedelta(minutes=20),
        )
        db.add(row)
        db.commit()
        event_id = row.id

    outbound_started = Event()
    release_response = Event()
    requests = []

    def post_callback(request):
        requests.append(request)
        outbound_started.set()
        assert release_response.wait(timeout=15)
        return httpx.Response(
            200, json={"id": 49, "status": "ready_for_review"}, request=request,
        )

    def original_worker():
        with SessionLocal() as db:
            with httpx.Client(transport=httpx.MockTransport(post_callback)) as client:
                result = process_event(
                    db, event_id, "original-worker",
                    endpoints={"accounting": "https://accounting.test"}, client=client,
                )
                return result.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(original_worker)
        try:
            assert outbound_started.wait(timeout=15)
            with SessionLocal() as db:
                # The row looks stale but is still being transmitted. Another
                # worker must not steal it and later erase the first outcome.
                stolen = claim_events(db, "replacement-worker", limit=3)
                assert stolen == []
        finally:
            release_response.set()
        assert first.result(timeout=20) == "completed"

    with SessionLocal() as db:
        final = db.get(IntegrationEvent, event_id)
        assert final.status == "completed"
        assert final.locked_by is None
        assert final.attempts == 1
        assert final.payload["accounting_intake"]["review_id"] == "49"
        assert len(requests) == 1
