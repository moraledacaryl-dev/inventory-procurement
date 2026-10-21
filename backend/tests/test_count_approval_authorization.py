"""End-to-end authorization checks for both legacy and guided physical counts."""

from decimal import Decimal

import pytest

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.inventory import StockDocument, StockMovement
from app.models.user import User


def headers_for(client, email):
    response = client.post("/api/v1/auth/login", json={
        "email": email, "password": "password123"
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def inventory_context(client):
    owner = headers_for(client, "owner@example.com")
    category = client.post("/api/v1/categories", headers=owner,
                           json={"name": "Count control"}).json()
    unit = client.post("/api/v1/units", headers=owner,
                       json={"code": "EA", "name": "Each"}).json()
    location = client.post("/api/v1/locations", headers=owner,
                           json={"code": "CNTSEC", "name": "Count controls"}).json()
    item = client.post("/api/v1/items", headers=owner, json={
        "sku": "CNTSEC-1", "name": "Count control item",
        "category_id": category["id"], "base_unit_id": unit["id"],
        "standard_cost": "15",
    }).json()
    receipt = client.post("/api/v1/stock/receipts", headers=owner, json={
        "location_id": location["id"],
        "lines": [{"item_id": item["id"], "quantity": "5", "unit_cost": "15"}],
    })
    assert receipt.status_code == 201, receipt.text
    with SessionLocal() as db:
        for email, role in (
            ("counter-one@example.com", "counter"),
            ("counter-two@example.com", "counter"),
            ("count-manager@example.com", "inventory_manager"),
            ("count-viewer@example.com", "viewer"),
        ):
            db.add(User(email=email, full_name=email, role=role,
                        password_hash=hash_password("password123")))
        db.commit()
    return owner, item, location


def balance_for(client, headers, item_id, location_id):
    response = client.get(
        f"/api/v1/stock/balances?item_id={item_id}&location_id={location_id}",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return Decimal(response.json()[0]["quantity"])


@pytest.mark.parametrize("workflow", ["legacy", "guided"])
@pytest.mark.parametrize("threshold", ["0", "1000"])
def test_counter_variances_cannot_auto_post_or_approve(client, workflow, threshold):
    owner, item, location = inventory_context(client)
    counter = headers_for(client, "counter-one@example.com")
    another_counter = headers_for(client, "counter-two@example.com")
    manager = headers_for(client, "count-manager@example.com")
    viewer = headers_for(client, "count-viewer@example.com")
    created = client.post("/api/v1/counts", headers=counter, json={
        "location_id": location["id"],
        "blind_count": True,
        "approval_threshold": threshold,
    })
    assert created.status_code == 201, created.text
    count_id = created.json()["id"]

    if workflow == "guided":
        saved = client.put(f"/api/v1/counts/{count_id}/entries", headers=counter,
                           json={"lines": [{"item_id": item["id"], "counted_quantity": "4"}]})
        assert saved.status_code == 200, saved.text
        submitted = client.post(f"/api/v1/counts/{count_id}/submit", headers=counter)
        approval_url = f"/api/v1/counts/{count_id}/approve-guided"
    else:
        submitted = client.post(f"/api/v1/counts/{count_id}/post", headers=counter,
                                json={"lines": [{"item_id": item["id"], "counted_quantity": "4"}]})
        approval_url = f"/api/v1/counts/{count_id}/approve"

    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "pending_approval"
    assert submitted.json()["posted_document_id"] is None
    assert balance_for(client, owner, item["id"], location["id"]) == Decimal("5")

    # Test an independent Counter, not just the creator, so the rejection
    # cannot be attributed to the same-actor conflict check.
    for unauthorized in (counter, another_counter, viewer):
        denied = client.post(approval_url, headers=unauthorized)
        assert denied.status_code == 403, denied.text
        assert balance_for(client, owner, item["id"], location["id"]) == Decimal("5")

    with SessionLocal() as db:
        count_docs_before = db.query(StockDocument).filter(
            StockDocument.document_type == "count_adjustment").count()
    assert count_docs_before == 0

    approved = client.post(approval_url, headers=manager)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "posted"
    assert approved.json()["posted_document_id"]
    assert balance_for(client, owner, item["id"], location["id"]) == Decimal("4")
    with SessionLocal() as db:
        assert db.query(StockDocument).filter(
            StockDocument.document_type == "count_adjustment").count() == 1
        assert db.query(StockMovement).filter(
            StockMovement.document_id == approved.json()["posted_document_id"]).count() == 1


@pytest.mark.parametrize("workflow", ["legacy", "guided"])
def test_counter_can_close_variance_free_count_without_stock_mutation(client, workflow):
    owner, item, location = inventory_context(client)
    counter = headers_for(client, "counter-one@example.com")
    created = client.post("/api/v1/counts", headers=counter, json={
        "location_id": location["id"], "approval_threshold": "0",
    })
    assert created.status_code == 201
    count_id = created.json()["id"]

    if workflow == "guided":
        saved = client.put(f"/api/v1/counts/{count_id}/entries", headers=counter,
                           json={"lines": [{"item_id": item["id"], "counted_quantity": "5"}]})
        assert saved.status_code == 200
        submitted = client.post(f"/api/v1/counts/{count_id}/submit", headers=counter)
    else:
        submitted = client.post(f"/api/v1/counts/{count_id}/post", headers=counter,
                                json={"lines": [{"item_id": item["id"], "counted_quantity": "5"}]})

    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "posted"
    assert submitted.json()["posted_document_id"] is None
    assert balance_for(client, owner, item["id"], location["id"]) == Decimal("5")
