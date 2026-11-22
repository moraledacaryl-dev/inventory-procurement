"""Phase 1 regression: direct stock posting must respect reserved stock."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.db.session import SessionLocal
from app.models.inventory_operations import StockReservation
from tests.test_inventory_operations import auth, setup


def test_direct_issue_and_transfer_cannot_consume_reserved_stock(client):
    headers = auth(client)
    item, _, _, source, destination, _ = setup(client, headers)
    item_id = item["id"]
    source_id = source["id"]
    destination_id = destination["id"]

    received = client.post("/api/v1/stock/receipts", headers=headers, json={
        "location_id": source_id,
        "lines": [{"item_id": item_id, "quantity": "10", "unit_cost": "80"}],
    })
    assert received.status_code == 201, received.text
    reserve = client.post("/api/v1/reservations", headers=headers, json={
        "item_id": item_id, "location_id": source_id, "quantity": "4",
        "reference_type": "event", "reference_id": "EVENT-1",
    })
    assert reserve.status_code == 201, reserve.text
    blocked_issue = client.post("/api/v1/stock/issues", headers=headers, json={
        "location_id": source_id,
        "lines": [{"item_id": item_id, "quantity": "7"}],
    })
    assert blocked_issue.status_code == 409, blocked_issue.text
    assert "reserved" in blocked_issue.text.lower()
    blocked_transfer = client.post("/api/v1/stock/transfers", headers=headers, json={
        "source_location_id": source_id, "destination_location_id": destination_id,
        "lines": [{"item_id": item_id, "quantity": "7"}],
    })
    assert blocked_transfer.status_code == 409, blocked_transfer.text

    valid_issue = client.post("/api/v1/stock/issues", headers=headers, json={
        "location_id": source_id, "lines": [{"item_id": item_id, "quantity": "6"}],
    })
    assert valid_issue.status_code == 201, valid_issue.text
    balance = client.get(
        f"/api/v1/availability?item_id={item_id}&location_id={source_id}",
        headers=headers,
    ).json()[0]
    assert Decimal(balance["physical_quantity"]) == Decimal("4")
    assert Decimal(balance["reserved_quantity"]) == Decimal("4")
    assert Decimal(balance["available_quantity"]) == Decimal("0")
    released = client.post(
        f"/api/v1/reservations/{reserve.json()['id']}/release", headers=headers
    )
    assert released.status_code == 200, released.text
    allowed = client.post("/api/v1/stock/transfers", headers=headers, json={
        "source_location_id": source_id, "destination_location_id": destination_id,
        "lines": [{"item_id": item_id, "quantity": "4"}],
    })
    assert allowed.status_code == 201, allowed.text


def test_expired_reservations_do_not_block_direct_issues(client):
    headers = auth(client)
    item, _, _, source, _, _ = setup(client, headers)
    item_id = item["id"]
    source_id = source["id"]
    receipt = client.post("/api/v1/stock/receipts", headers=headers, json={
        "location_id": source_id,
        "lines": [{"item_id": item_id, "quantity": "5", "unit_cost": "80"}],
    })
    assert receipt.status_code == 201, receipt.text
    reserve = client.post("/api/v1/reservations", headers=headers, json={
        "item_id": item_id, "location_id": source_id, "quantity": "4",
        "reference_type": "event", "reference_id": "EXPIRED-EVENT",
    })
    assert reserve.status_code == 201, reserve.text
    with SessionLocal() as db:
        row = db.get(StockReservation, reserve.json()["id"])
        row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
    issue = client.post("/api/v1/stock/issues", headers=headers, json={
        "location_id": source_id, "lines": [{"item_id": item_id, "quantity": "5"}],
    })
    assert issue.status_code == 201, issue.text
