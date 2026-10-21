"""Regression tests: assigned locations must protect direct API read access."""

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.pass6 import OperationalAccessScope
from app.models.user import User


def session_headers(client, email="owner@example.com"):
    login = client.post("/api/v1/auth/login", json={
        "email": email, "password": "password123",
    })
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def seed(client):
    owner = session_headers(client)
    category = client.post("/api/v1/categories", headers=owner,
                           json={"name": "Scoped reports"}).json()
    unit = client.post("/api/v1/units", headers=owner,
                       json={"code": "EA", "name": "Each"}).json()
    locations = []
    for code in ("SCOPED-A", "SCOPED-B"):
        response = client.post("/api/v1/locations", headers=owner,
                               json={"code": code, "name": code})
        assert response.status_code == 201, response.text
        locations.append(response.json()["id"])
    item = client.post("/api/v1/items", headers=owner, json={
        "sku": "SCOPE-READ", "name": "Read policy item",
        "category_id": category["id"], "base_unit_id": unit["id"],
        "standard_cost": "30",
    }).json()["id"]
    for loc in locations:
        receipt = client.post("/api/v1/stock/receipts", headers=owner, json={
            "location_id": loc,
            "lines": [{"item_id": item, "quantity": "10", "unit_cost": "30"}],
        })
        assert receipt.status_code == 201, receipt.text
    users = [
        ("read-manager@example.com", "inventory_manager"),
        ("read-counter@example.com", "counter"),
        ("read-unscoped@example.com", "inventory_manager"),
    ]
    with SessionLocal() as db:
        for email, role in users:
            db.add(User(email=email, full_name=email, role=role,
                        password_hash=hash_password("password123")))
        db.commit()
        ids = {row.email: row.id for row in db.query(User).all()}
    for email in ("read-manager@example.com", "read-counter@example.com"):
        response = client.post("/api/v1/access-scopes", headers=owner, json={
            "user_id": ids[email], "location_id": locations[0],
            "approval_limit": "0",
        })
        assert response.status_code == 201, response.text
    return owner, session_headers(client, users[0][0]), session_headers(client, users[1][0]), session_headers(client, users[2][0]), locations, item, ids


def test_location_and_stock_read_queries_do_not_leak_other_locations(client):
    owner, scoped, _counter, unscoped, (a, b), item, ids = seed(client)
    assert {r["id"] for r in client.get("/api/v1/locations", headers=scoped).json()} == {a}
    assert len(client.get("/api/v1/locations", headers=owner).json()) == 2
    assert len(client.get("/api/v1/locations", headers=unscoped).json()) == 2

    assert client.get(f"/api/v1/locations/{a}", headers=scoped).status_code == 200
    assert client.get(f"/api/v1/locations/{b}", headers=scoped).status_code == 403
    assert client.patch(f"/api/v1/locations/{b}", headers=scoped,
                        json={"name": "Unauthorized rename"}).status_code == 403
    assert client.get(f"/api/v1/locations/{b}", headers=owner).json()["location"]["name"] == "SCOPED-B"

    for resource in ("balances", "movements"):
        endpoint = f"/api/v1/stock/{resource}"
        scoped_rows = client.get(endpoint, headers=scoped)
        assert scoped_rows.status_code == 200, scoped_rows.text
        assert scoped_rows.json()
        assert {row["location_id"] for row in scoped_rows.json()} == {a}
        assert client.get(f"{endpoint}?location_id={b}", headers=scoped).status_code == 403
        assert client.get(f"{endpoint}?location_id={a}", headers=scoped).status_code == 200
        assert {row["location_id"] for row in client.get(endpoint, headers=owner).json()} == {a, b}

    # Even after an account's only scope is disabled, none of its other
    # locations become visible through a fallback to legacy unrestricted reads.
    with SessionLocal() as db:
        scope = db.query(OperationalAccessScope).filter(
            OperationalAccessScope.user_id == ids["read-manager@example.com"]
        ).one()
        scope.is_active = False
        db.commit()
    assert client.get("/api/v1/locations", headers=scoped).json() == []
    assert client.get("/api/v1/stock/balances", headers=scoped).json() == []
    assert client.get(f"/api/v1/locations/{a}", headers=scoped).status_code == 403


def test_guided_and_legacy_count_lifecycle_is_location_scoped(client):
    owner, _manager, counter, _unscoped, (a, b), item, _ids = seed(client)
    ids = []
    for location in (a, b):
        created = client.post("/api/v1/counts", headers=owner,
                              json={"location_id": location})
        assert created.status_code == 201, created.text
        ids.append(created.json()["id"])
    assert {x["location_id"] for x in client.get("/api/v1/counts", headers=counter).json()} == {a}
    assert {x["location_id"] for x in client.get("/api/v1/counts/workspace", headers=counter).json()} == {a}
    assert client.get(f"/api/v1/counts/{ids[1]}/detail", headers=counter).status_code == 403
    assert client.get(f"/api/v1/counts/{ids[1]}/worksheet", headers=counter).status_code == 403
    assert client.post("/api/v1/counts", headers=counter,
                       json={"location_id": b}).status_code == 403
    assert client.get(f"/api/v1/counts/{ids[0]}/detail", headers=counter).status_code == 200
    assert client.put(f"/api/v1/counts/{ids[1]}/entries", headers=counter, json={
        "lines": [{"item_id": item, "counted_quantity": "9"}]
    }).status_code == 403
    assert client.post(f"/api/v1/counts/{ids[1]}/submit", headers=counter).status_code == 403
    assert client.post(f"/api/v1/counts/{ids[1]}/post", headers=counter, json={
        "lines": [{"item_id": item, "counted_quantity": "9"}]
    }).status_code == 403
    assert client.get(f"/api/v1/counts/{ids[1]}/detail", headers=owner).json()["status"] == "open"


def test_adjustment_waste_and_transfer_queues_hide_unauthorized_locations(client):
    owner, scoped, _counter, _unscoped, (a, b), item, _ids = seed(client)
    for loc in (a, b):
        adjusted = client.post("/api/v1/inventory-controls/adjustments", headers=owner, json={
            "location_id": loc, "reason_code": "correction",
            "lines": [{"item_id": item, "quantity_delta": "1", "unit_cost": "30"}],
        })
        assert adjusted.status_code == 201, adjusted.text
        wasted = client.post("/api/v1/inventory-controls/waste", headers=owner, json={
            "item_id": item, "location_id": loc,
            "quantity": "1", "reason_code": "damage",
        })
        assert wasted.status_code == 201, wasted.text
    for kind in ("adjustments", "waste"):
        response = client.get(f"/api/v1/inventory-controls/{kind}", headers=scoped)
        assert response.status_code == 200, response.text
        assert response.json()
        assert {row["location_id"] for row in response.json()} == {a}

    created = client.post("/api/v1/transfer-orders", headers=owner, json={
        "source_location_id": a, "destination_location_id": b,
        "lines": [{"item_id": item, "quantity": "2"}],
    })
    assert created.status_code == 201, created.text
    transfer_id = created.json()["id"]
    assert client.get("/api/v1/transfer-orders/workspace", headers=scoped).json() == []
    assert client.get(f"/api/v1/transfer-orders/{transfer_id}/detail",
                      headers=scoped).status_code == 403
    assert client.post(f"/api/v1/transfer-orders/{transfer_id}/cancel",
                       headers=scoped).status_code == 403
    assert client.get(f"/api/v1/transfer-orders/{transfer_id}/detail",
                      headers=owner).json()["status"] == "draft"
