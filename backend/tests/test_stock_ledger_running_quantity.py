"""Regression contract: running stock is historical, even when display rows are filtered.

The response summary remains intentionally scoped to the displayed result set.
No filtered, earlier, or unauthorized movement can silently reset a balance.
"""
from datetime import datetime
from decimal import Decimal

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.inventory import StockMovement
from app.models.pass6 import OperationalAccessScope
from app.models.user import User


def auth(client, email="owner@example.com"):
    response = client.post("/api/v1/auth/login", json={
        "email": email, "password": "password123",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create(client, path, headers, payload):
    response = client.post(path, json=payload, headers=headers)
    assert response.status_code == 201, (path, response.text)
    return response.json()


def seed_movement_history(client):
    owner = auth(client)
    category = create(client, "/api/v1/categories", owner, {"name": "Ledger history category"})
    unit = create(client, "/api/v1/units", owner, {
        "code": "LHG", "name": "Ledger history unit", "precision": 4,
    })
    item = create(client, "/api/v1/items", owner, {
        "sku": "LEDGER-HISTORY-ITEM", "name": "Ledger history stock",
        "category_id": category["id"], "base_unit_id": unit["id"],
        "standard_cost": "10",
    })
    a = create(client, "/api/v1/locations", owner, {
        "code": "LEDGER-A", "name": "Ledger A",
    })["id"]
    b = create(client, "/api/v1/locations", owner, {
        "code": "LEDGER-B", "name": "Ledger B",
    })["id"]
    operations = [
        ("/api/v1/stock/receipts", {"location_id": a, "lines": [
            {"item_id": item["id"], "quantity": "10", "unit_cost": "10"},
        ]}, "2026-01-01"),
        ("/api/v1/stock/receipts", {"location_id": b, "lines": [
            {"item_id": item["id"], "quantity": "4", "unit_cost": "7"},
        ]}, "2026-01-02"),
        ("/api/v1/stock/issues", {"location_id": a, "lines": [
            {"item_id": item["id"], "quantity": "3"},
        ]}, "2026-01-03"),
        ("/api/v1/stock/receipts", {"location_id": a, "lines": [
            {"item_id": item["id"], "quantity": "5", "unit_cost": "12"},
        ]}, "2026-01-04"),
        ("/api/v1/stock/transfers", {
            "source_location_id": a, "destination_location_id": b,
            "lines": [{"item_id": item["id"], "quantity": "2"}],
        }, "2026-01-05"),
    ]
    for path, data, day in operations:
        posted = create(client, path, owner, data)
        # Fix the test history in both SQLite and PostgreSQL. Creation-time
        # wall clocks are deliberately not the temporal ledger contract.
        with SessionLocal() as db:
            for line in posted["movements"]:
                db.get(StockMovement, line["id"]).created_at = datetime.fromisoformat(day + "T12:00:00")
            db.commit()
    return {"owner": owner, "item_id": item["id"], "a": a, "b": b}


def get_ledger(client, headers, **filters):
    response = client.get("/api/v1/stock/ledger", headers=headers, params=filters)
    assert response.status_code == 200, response.text
    return response.json()


def pairs(payload):
    return [(row["location_id"], Decimal(row["running_quantity"]))
            for row in payload["rows"]]


def test_running_quantities_remain_historical_across_filters_and_limit(client):
    s = seed_movement_history(client)
    a, b, owner = s["a"], s["b"], s["owner"]
    full = get_ledger(client, owner, item_id=s["item_id"])
    assert pairs(full) == [
        (a, Decimal("10")), (b, Decimal("4")), (a, Decimal("7")),
        (a, Decimal("12")), (a, Decimal("10")), (b, Decimal("6")),
    ]
    assert full["summary"]["movement_count"] == 6

    # The filtered display contains only an issue but must carry 10 from
    # the earlier receipt, rather than incorrectly starting at -3.
    issues = get_ledger(client, owner, item_id=s["item_id"],
                        location_id=a, document_type="issue")
    assert [Decimal(r["quantity"]) for r in issues["rows"]] == [Decimal("-3")]
    assert pairs(issues) == [(a, Decimal("7"))]
    assert Decimal(issues["summary"]["net_quantity"]) == Decimal("-3")

    only_transfer = get_ledger(client, owner, location_id=a, document_type="transfer")
    assert pairs(only_transfer) == [(a, Decimal("10"))]
    assert Decimal(only_transfer["summary"]["net_quantity"]) == Decimal("-2")

    # Filtering by date and then limiting to one row must not rewrite the
    # preceding history. Only the summary is limited to displayed rows.
    narrow = get_ledger(client, owner, item_id=s["item_id"], location_id=a,
                        date_from="2026-01-04T00:00:00", limit=1)
    assert [Decimal(r["quantity"]) for r in narrow["rows"]] == [Decimal("5")]
    assert pairs(narrow) == [(a, Decimal("12"))]
    assert narrow["summary"]["movement_count"] == 1
    assert Decimal(narrow["summary"]["net_quantity"]) == Decimal("5")

    through_issue = get_ledger(client, owner, location_id=a,
                               date_to="2026-01-03T23:59:59")
    assert pairs(through_issue) == [(a, Decimal("10")), (a, Decimal("7"))]


def test_running_quantities_partition_by_location_and_fail_closed_for_revoked_scope(client):
    s = seed_movement_history(client)
    a, b = s["a"], s["b"]
    with SessionLocal() as db:
        user = User(email="ledger-operator@example.com", full_name="Ledger operator",
                    password_hash=hash_password("password123"), role="inventory_manager")
        db.add(user)
        db.flush()
        scope = OperationalAccessScope(user_id=user.id, location_id=a, approval_limit=0)
        db.add(scope)
        db.commit()
        scope_id = scope.id

    scoped = auth(client, "ledger-operator@example.com")
    ledger = get_ledger(client, scoped, item_id=s["item_id"])
    assert {row["location_id"] for row in ledger["rows"]} == {a}
    assert pairs(ledger) == [
        (a, Decimal("10")), (a, Decimal("7")),
        (a, Decimal("12")), (a, Decimal("10")),
    ]
    assert ledger["summary"]["movement_count"] == 4
    assert client.get("/api/v1/stock/ledger", headers=scoped,
                      params={"location_id": b}).status_code == 403
    with SessionLocal() as db:
        db.get(OperationalAccessScope, scope_id).is_active = False
        db.commit()
    revoked = get_ledger(client, scoped)
    assert revoked["rows"] == []
    assert revoked["summary"]["movement_count"] == 0
    assert Decimal(revoked["summary"]["net_quantity"]) == 0
    assert Decimal(revoked["summary"]["net_value"]) == 0
