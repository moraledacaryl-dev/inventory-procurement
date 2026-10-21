import httpx
import pytest

from app.db.session import SessionLocal
from app.models.operations import IntegrationEvent
from app.services.integration_worker import (
    _accounting_status_url,
    _verified_accounting_status,
    reconcile_accounting_reviews,
)


def make_event(key: str = "proof-evt-1"):
    return IntegrationEvent(
        direction="outbound", source_system="inventory", destination_system="accounting",
        event_type="inventory.stock_document.posted",
        aggregate_type="stock_document", aggregate_id="document-1",
        idempotency_key=key, payload={
            "document_id": "document-1",
            "accounting_intake": {"status": "ready_for_review", "review_id": "80"}
        }, status="completed",
    )


def proof(event_id: str, **updates):
    state = {
        "source_app": "inventory", "source_event_id": event_id,
        "review_id": 80, "review_status": "accepted",
        "financial_effect": "journal_only",
        "accepted_journal_entry_id": 123,
        "journal_status": "posted",
        "journal_is_reversed": False,
        "journal_line_count": 2,
        "journal_debit": "250.00", "journal_credit": "250.00",
        "ledger_posting_confirmed": True,
    }
    state.update(updates)
    return state


def test_accounting_status_url_handles_base_and_intake_endpoint():
    root = "https://accounting.example"
    direct = root + "/api/integration-review/service-intake"
    assert _accounting_status_url(root) == _accounting_status_url(direct)
    assert _accounting_status_url(root).endswith("/api/integration-review/service-status")


@pytest.mark.parametrize("changes", [
    {"review_status": "ready_for_review", "ledger_posting_confirmed": True},
    {"journal_status": "draft", "ledger_posting_confirmed": True},
    {"journal_is_reversed": True, "ledger_posting_confirmed": True},
    {"accepted_journal_entry_id": None, "ledger_posting_confirmed": True},
    {"journal_debit": "251.00", "ledger_posting_confirmed": True},
    {"journal_line_count": 1, "ledger_posting_confirmed": True},
    {"source_event_id": "another-event", "ledger_posting_confirmed": True},
    {"source_app": "pos", "ledger_posting_confirmed": True},
])
def test_unverifiable_or_unrelated_accounting_proof_fails_closed(changes):
    with pytest.raises(RuntimeError):
        _verified_accounting_status(proof("proof-evt-1", **changes), "proof-evt-1")


def test_accounting_review_sync_verifies_posted_balanced_journal_and_throttles(monkeypatch, client):
    monkeypatch.setenv("INTEGRATION_API_KEY", "test-shared-accounting-key")
    with SessionLocal() as db:
        event = make_event()
        db.add(event)
        db.commit()
        event_id = event.id
        calls = []

        def handler(request):
            calls.append(request)
            assert request.method == "GET"
            assert request.headers["X-Integration-Api-Key"] == "test-shared-accounting-key"
            assert request.url.params["source_event_id"] == event_id
            return httpx.Response(200, request=request, json=proof(event_id))

        with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
            result = reconcile_accounting_reviews(
                db, {"accounting": "https://accounting.example"}, transport,
            )
            assert result == {"checked": 1, "confirmed": 1, "errors": 0}
            assert len(calls) == 1
            assert reconcile_accounting_reviews(
                db, {"accounting": "https://accounting.example"}, transport,
            ) == {"checked": 0, "confirmed": 0, "errors": 0}
            assert len(calls) == 1

        db.refresh(event)
        assert event.status == "completed"
        verified = event.payload["accounting_reconciliation"]
        assert verified["ledger_posting_confirmed"] is True
        assert verified["journal_entry_id"] == "123"
        assert verified["journal_status"] == "posted"
        assert verified["checked_at"]

    token = client.post("/api/v1/auth/login", json={
        "email": "owner@example.com", "password": "password123"
    }).json()["access_token"]
    response = client.get("/api/v1/integrations/accounting/workspace", headers={
        "Authorization": f"Bearer {token}"
    })
    assert response.status_code == 200
    row = next(entry for entry in response.json()["events"] if entry["id"] == event_id)
    assert row["ledger_posting_confirmed"] is True
    assert row["accounting_journal_entry_id"] == "123"
    assert response.json()["summary"]["posted_journals_verified"] >= 1


def test_unavailable_or_rejected_accounting_proof_does_not_mark_gl_posted(monkeypatch):
    monkeypatch.setenv("INTEGRATION_API_KEY", "test-shared-accounting-key")
    with SessionLocal() as db:
        event = make_event("proof-missing")
        db.add(event)
        db.commit()

        with httpx.Client(transport=httpx.MockTransport(
            lambda req: httpx.Response(404, request=req, json={"detail": "not found"})
        )) as transport:
            outcome = reconcile_accounting_reviews(
                db, {"accounting": "https://accounting.example"}, transport,
            )
        assert outcome == {"checked": 1, "confirmed": 0, "errors": 1}
        db.refresh(event)
        assert event.status == "completed"
        assert event.payload["accounting_reconciliation"]["ledger_posting_confirmed"] is False
        assert event.payload["accounting_reconciliation"]["review_status"] == "verification_unavailable"


def test_accounting_rejected_status_and_accepted_without_journal_are_not_postings():
    for state in [
        proof("evt", review_status="rejected", accepted_journal_entry_id=None,
              journal_status=None, journal_debit=None, journal_credit=None,
              journal_line_count=0, ledger_posting_confirmed=False),
        proof("evt", review_status="accepted", accepted_journal_entry_id=None,
              journal_status=None, journal_debit=None, journal_credit=None,
              journal_line_count=0, ledger_posting_confirmed=False),
    ]:
        assert _verified_accounting_status(state, "evt")["ledger_posting_confirmed"] is False
