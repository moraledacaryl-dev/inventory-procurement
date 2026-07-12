from app.db.session import SessionLocal
from app.models.operations import IntegrationEvent


def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_accounting_event(client, headers, key="acct-test-1", event_type="inventory.stock_document.posted"):
    response = client.post("/api/v1/integration-events", headers=headers, json={
        "direction": "outbound",
        "source_system": "inventory",
        "destination_system": "accounting",
        "event_type": event_type,
        "aggregate_type": "stock_document",
        "aggregate_id": "doc-001",
        "idempotency_key": key,
        "payload": {"lines": [{"item_id": "item-1", "quantity": "2", "unit_cost": "15"}]},
    })
    assert response.status_code == 201
    return response.json()


def test_accounting_workspace_and_mapping(client):
    headers = auth_headers(client)
    event = create_accounting_event(client, headers)
    workspace = client.get("/api/v1/integrations/accounting/workspace", headers=headers)
    assert workspace.status_code == 200
    row = next(item for item in workspace.json()["events"] if item["id"] == event["id"])
    assert row["mapped"] is True
    assert row["debit_account"] == "Inventory Asset"
    assert row["credit_account"] == "Inventory Clearing"
    assert row["amount"] == 30
    assert workspace.json()["summary"]["pending"] >= 1


def test_accounting_receipt_accept_and_reject(client):
    headers = auth_headers(client)
    accepted = create_accounting_event(client, headers, "acct-accept")
    response = client.post("/api/v1/integrations/accounting/receipts", headers=headers, json={"idempotency_key": "acct-accept", "accepted": True, "external_reference": "JE-1001"})
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    rejected = create_accounting_event(client, headers, "acct-reject")
    response = client.post("/api/v1/integrations/accounting/receipts", headers=headers, json={"idempotency_key": "acct-reject", "accepted": False, "message": "Missing account mapping"})
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["last_error"] == "Missing account mapping"

    requeued = client.post(f"/api/v1/integrations/accounting/events/{rejected['id']}/requeue", headers=headers)
    assert requeued.status_code == 200
    assert requeued.json()["status"] == "pending"
    assert requeued.json()["attempts"] == 0


def test_accounting_workspace_flags_unmapped_event(client):
    headers = auth_headers(client)
    event = create_accounting_event(client, headers, "acct-unmapped", "inventory.unknown.event")
    workspace = client.get("/api/v1/integrations/accounting/workspace", headers=headers)
    row = next(item for item in workspace.json()["events"] if item["id"] == event["id"])
    assert row["mapped"] is False
    assert row["debit_account"] == "Unmapped"
