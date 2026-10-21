import httpx
import pytest

from app.services.integration_worker import _validate_accounting_response


def response(payload):
    return httpx.Response(200, json=payload, request=httpx.Request("POST", "https://accounting.example/api/integration-review/service-intake"))


def test_accounting_ready_for_review_is_delivered():
    payload = {"id": 42, "status": "ready_for_review", "validation": {"valid": True, "errors": []}}
    assert _validate_accounting_response(response(payload)) == payload


@pytest.mark.parametrize("status", ["accepted", "rejected"])
def test_existing_accounting_review_terminal_status_is_delivered(status):
    payload = {"id": 42, "status": status, "validation": {"valid": True, "errors": []}}
    assert _validate_accounting_response(response(payload)) == payload


def test_accounting_validation_failed_is_not_delivered():
    with pytest.raises(RuntimeError, match="validation_failed.*target_type"):
        _validate_accounting_response(
            response(
                {
                    "id": 42,
                    "status": "validation_failed",
                    "validation": {
                        "valid": False,
                        "errors": ["Reference and folio effects require proposed_links.target_type and target_id."],
                    },
                }
            )
        )


def test_accounting_missing_or_unknown_status_fails_closed():
    with pytest.raises(RuntimeError, match="unexpected status: missing"):
        _validate_accounting_response(response({"id": 42}))
    with pytest.raises(RuntimeError, match="unexpected status: queued"):
        _validate_accounting_response(response({"id": 42, "status": "queued"}))


@pytest.mark.parametrize("intake_status", ["ready_for_review", "accepted", "rejected"])
def test_worker_persists_accounting_intake_result_without_claiming_gl_posting(
    client, intake_status
):
    from app.db.session import SessionLocal
    from app.models.operations import IntegrationEvent
    from app.services.integration_worker import process_event

    event_id = None
    with SessionLocal() as db:
        event = IntegrationEvent(
            direction="outbound", source_system="inventory", destination_system="accounting",
            event_type="inventory.stock_document.posted",
            aggregate_type="stock_document", aggregate_id="stock-987",
            idempotency_key=f"accounting-intake-{intake_status}",
            payload={"document_id": "stock-987", "lines": [
                {"item_id": "item-987", "quantity": "2", "unit_cost": "15"}
            ]},
            status="processing", locked_by="review-test-worker",
        )
        db.add(event)
        db.commit()
        event_id = event.id

        transport = httpx.MockTransport(lambda request: httpx.Response(
            200, json={"status": intake_status, "id": 987}, request=request
        ))
        with httpx.Client(transport=transport) as transport_client:
            result = process_event(
                db, event_id, "review-test-worker",
                endpoints={"accounting": "https://accounting.example"},
                client=transport_client,
            )
        assert result.status == "completed"
        assert result.payload["accounting_intake"]["status"] == intake_status
        assert result.payload["accounting_intake"]["review_id"] == "987"

    login = client.post("/api/v1/auth/login", json={
        "email": "owner@example.com", "password": "password123",
    })
    assert login.status_code == 200
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    workspace = client.get("/api/v1/integrations/accounting/workspace", headers=auth)
    assert workspace.status_code == 200
    row = next(x for x in workspace.json()["events"] if x["id"] == event_id)
    assert row["status"] == "completed"  # Delivery succeeded
    assert row["accounting_intake_status"] == intake_status
    assert row["accounting_review_id"] == "987"
    assert row["ledger_posting_confirmed"] is False


def test_existing_completed_accounting_event_without_intake_ack_is_unverified(client):
    from app.db.session import SessionLocal
    from app.models.operations import IntegrationEvent

    with SessionLocal() as db:
        event = IntegrationEvent(
            direction="outbound", source_system="inventory", destination_system="accounting",
            event_type="inventory.stock_document.posted",
            aggregate_type="stock_document", aggregate_id="legacy-123",
            idempotency_key="legacy-accounting-unknown",
            payload={"lines": [{"quantity": "2", "unit_cost": "12"}]},
            status="completed",
        )
        db.add(event)
        db.commit()
        event_id = event.id
    login = client.post("/api/v1/auth/login", json={
        "email": "owner@example.com", "password": "password123",
    })
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    result = client.get("/api/v1/integrations/accounting/workspace", headers=auth)
    assert result.status_code == 200
    row = next(x for x in result.json()["events"] if x["id"] == event_id)
    assert row["accounting_intake_status"] == "unverified_delivery"
    assert row["ledger_posting_confirmed"] is False
    assert result.json()["summary"]["unverified_delivery"] >= 1
