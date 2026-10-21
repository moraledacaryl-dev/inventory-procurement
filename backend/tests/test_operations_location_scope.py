"""Location-scope regression suite for inventory operations and value reports."""

from datetime import date, timedelta
from decimal import Decimal

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.pass6 import OperationalAccessScope
from app.models.user import User


def login(client, email="owner@example.com"):
    result = client.post("/api/v1/auth/login", json={
        "email": email, "password": "password123",
    })
    assert result.status_code == 200, result.text
    return {"Authorization": f"Bearer {result.json()['access_token']}"}


def assert_created(response):
    assert response.status_code == 201, response.text
    return response.json()


def context(client):
    owner = login(client)
    category = assert_created(client.post("/api/v1/categories", headers=owner, json={
        "name": "Scope Ops",
    }))
    unit = assert_created(client.post("/api/v1/units", headers=owner, json={
        "code": "EA", "name": "Each",
    }))
    locations = [
        assert_created(client.post("/api/v1/locations", headers=owner, json={
            "code": code, "name": code,
        }))["id"]
        for code in ("SCOPE-OPS-A", "SCOPE-OPS-B")
    ]
    item = assert_created(client.post("/api/v1/items", headers=owner, json={
        "sku": "OPS-SCOPE", "name": "Scoped inventory",
        "category_id": category["id"], "base_unit_id": unit["id"],
        "standard_cost": "20",
    }))["id"]
    for location_id in locations:
        assert_created(client.post("/api/v1/stock/receipts", headers=owner, json={
            "location_id": location_id,
            "lines": [{"item_id": item, "quantity": "20", "unit_cost": "20"}],
        }))
    with SessionLocal() as db:
        for email in ("scope-ops@example.com", "ops-unassigned@example.com"):
            db.add(User(email=email, full_name=email, role="inventory_manager",
                        password_hash=hash_password("password123")))
        db.commit()
        scoped_id = db.query(User).filter(User.email == "scope-ops@example.com").one().id
    assigned = assert_created(client.post("/api/v1/access-scopes", headers=owner, json={
        "user_id": scoped_id, "location_id": locations[0],
        "approval_limit": "0",
    }))["id"]
    return owner, login(client, "scope-ops@example.com"), login(client, "ops-unassigned@example.com"), locations, item, scoped_id, assigned


def test_operations_reports_respect_location_scope_and_explicit_filters(client):
    owner, scoped, unassigned, (a, b), item, _, scope_id = context(client)
    future = (date.today() + timedelta(days=3)).isoformat()
    lots = {}
    for code, loc in (("LOT-A", a), ("LOT-B", b)):
        lots[code] = assert_created(client.post("/api/v1/lots", headers=owner, json={
            "item_id": item, "lot_number": code, "expiry_date": future,
        }))["id"]
        assert_created(client.post("/api/v1/lot-transactions", headers=owner, json={
            "lot_id": lots[code], "location_id": loc,
            "quantity": "4", "unit_cost": "20", "transaction_type": "receipt",
        }))
        assert_created(client.post("/api/v1/item-location-settings", headers=owner, json={
            "item_id": item, "location_id": loc,
            "minimum_stock": "5", "reorder_quantity": "8",
        }))
        assert_created(client.post("/api/v1/cycle-count-schedules", headers=owner, json={
            "item_id": item, "location_id": loc, "next_count_date": "2020-01-01",
        }))
        assert_created(client.post("/api/v1/lot-transactions", headers=owner, json={
            "lot_id": lots[code], "location_id": loc, "quantity": "1",
            "unit_cost": "20", "transaction_type": "waste",
        }))

    endpoints = (
        "/api/v1/item-location-settings",
        "/api/v1/lot-balances",
        "/api/v1/availability",
        "/api/v1/cycle-count-schedules",
        "/api/v1/reports/valuation",
        "/api/v1/reports/aging",
        "/api/v1/reports/expiry?days=30",
    )
    for url in endpoints:
        resp = client.get(url, headers=scoped)
        assert resp.status_code == 200, (url, resp.text)
        assert resp.json(), url
        assert {row["location_id"] for row in resp.json()} == {a}, url
        other = client.get(url + ("&" if "?" in url else "?") + f"location_id={b}",
                           headers=scoped)
        if "cycle-count-schedules" not in url:  # endpoint lacks a location filter
            assert other.status_code == 403, (url, other.text)
        full = client.get(url, headers=owner)
        assert {row["location_id"] for row in full.json()} == {a, b}
    assert {row["lot_number"] for row in client.get("/api/v1/lots", headers=scoped).json()} == {"LOT-A"}
    assert {row["lot_number"] for row in client.get("/api/v1/lots", headers=owner).json()} == {"LOT-A", "LOT-B"}
    assert {row["lot_number"] for row in client.get("/api/v1/lots", headers=unassigned).json()} == {"LOT-A", "LOT-B"}
    limited_waste = client.get("/api/v1/reports/waste", headers=scoped)
    assert limited_waste.status_code == 200, limited_waste.text
    assert Decimal(limited_waste.json()[0]["quantity"]) == Decimal("1")
    full_waste = client.get("/api/v1/reports/waste", headers=owner)
    assert Decimal(full_waste.json()[0]["quantity"]) == Decimal("2")

    # Disabling an assigned policy is fail-closed, not a fallback to full access.
    with SessionLocal() as db:
        db.get(OperationalAccessScope, scope_id).is_active = False
        db.commit()
    for url in endpoints + ("/api/v1/lots", "/api/v1/reports/waste"):
        resp = client.get(url, headers=scoped)
        assert resp.status_code == 200 and resp.json() == [], (url, resp.text)


def test_reservation_and_transfer_lifecycle_requires_both_authorized_locations(client):
    owner, scoped, _, (a, b), item, _, _ = context(client)

    valid = assert_created(client.post("/api/v1/reservations", headers=scoped, json={
        "item_id": item, "location_id": a, "quantity": "2",
        "reference_type": "test", "reference_id": "ok",
    }))
    denied = client.post("/api/v1/reservations", headers=scoped, json={
        "item_id": item, "location_id": b, "quantity": "2",
        "reference_type": "test", "reference_id": "blocked",
    })
    assert denied.status_code == 403, denied.text
    other = assert_created(client.post("/api/v1/reservations", headers=owner, json={
        "item_id": item, "location_id": b, "quantity": "2",
        "reference_type": "test", "reference_id": "owner",
    }))
    assert client.post(f"/api/v1/reservations/{other['id']}/release",
                       headers=scoped).status_code == 403
    assert client.post(f"/api/v1/reservations/{valid['id']}/release",
                       headers=scoped).status_code == 200

    outside_lot = assert_created(client.post("/api/v1/lots", headers=owner, json={
        "item_id": item, "lot_number": "B-LOCKED",
    }))["id"]
    for url, payload in (
        ("/api/v1/item-location-settings", {"item_id": item, "location_id": b}),
        ("/api/v1/cycle-count-schedules", {"item_id": item, "location_id": b,
                                          "next_count_date": "2020-01-01"}),
        ("/api/v1/lot-transactions", {"lot_id": outside_lot, "location_id": b,
                                     "quantity": "1", "transaction_type": "receipt"}),
    ):
        response = client.post(url, json=payload, headers=scoped)
        assert response.status_code == 403, (url, response.text)

    transfer = assert_created(client.post("/api/v1/transfer-orders", headers=owner, json={
        "source_location_id": a, "destination_location_id": b,
        "lines": [{"item_id": item, "quantity": "3"}],
    }))
    assert client.get("/api/v1/transfer-orders", headers=scoped).json() == []
    deny_create = client.post("/api/v1/transfer-orders", headers=scoped, json={
        "source_location_id": a, "destination_location_id": b,
        "lines": [{"item_id": item, "quantity": "1"}],
    })
    assert deny_create.status_code == 403, deny_create.text
    assert client.post(f"/api/v1/transfer-orders/{transfer['id']}/dispatch",
                       headers=scoped).status_code == 403
    assert client.get("/api/v1/transfer-orders", headers=owner).json()[0]["status"] == "draft"
    dispatched = client.post(f"/api/v1/transfer-orders/{transfer['id']}/dispatch",
                             headers=owner)
    assert dispatched.status_code == 200, dispatched.text
    assert client.post(f"/api/v1/transfer-orders/{transfer['id']}/receive",
                       headers=scoped).status_code == 403
    assert client.get("/api/v1/transfer-orders", headers=owner).json()[0]["status"] == "dispatched"


def test_cycle_schedule_scope_denies_unrelated_location_without_count_creation(client):
    owner, scoped, _, (a, b), item, _, _ = context(client)
    assert_created(client.post("/api/v1/cycle-count-schedules", headers=scoped, json={
        "item_id": item, "location_id": a, "next_count_date": "2020-01-01",
    }))
    denied = client.post("/api/v1/cycle-count-schedules", headers=scoped, json={
        "item_id": item, "location_id": b, "next_count_date": "2020-01-01",
    })
    assert denied.status_code == 403, denied.text
    rows = client.get("/api/v1/cycle-count-schedules", headers=owner).json()
    assert len(rows) == 1 and rows[0]["location_id"] == a
