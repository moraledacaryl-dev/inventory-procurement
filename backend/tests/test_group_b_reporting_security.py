"""Group B: production API scope/financial reporting regressions.

No live data is used; endpoint tests rely on isolated seeded fixtures.
"""
from decimal import Decimal

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.operations import IntegrationEvent
from app.models.pass6 import OperationalAccessScope
from app.models.user import User


def auth(client, email="owner@example.com"):
    response = client.post("/api/v1/auth/login", json={
        "email": email, "password": "password123",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create(client, path, headers, data):
    response = client.post(path, headers=headers, json=data)
    assert response.status_code == 201, (path, response.text)
    return response.json()


def seed(client):
    owner = auth(client)
    category = create(client, "/api/v1/categories", owner, {"name": "Group B audit category"})
    unit = create(client, "/api/v1/units", owner, {
        "code": "GB", "name": "Group B audit unit",
    })
    a, b = [
        create(client, "/api/v1/locations", owner, {
            "code": code, "name": code,
        })["id"] for code in ["GROUPB-A", "GROUPB-B"]
    ]
    items = []
    for name, location, qty, cost in (
        ("GROUPB-ITEM-A", a, "10", "5"),
        ("GROUPB-ITEM-B", b, "20", "7"),
    ):
        item = create(client, "/api/v1/items", owner, {
            "sku": name, "name": name,
            "category_id": category["id"], "base_unit_id": unit["id"],
            "minimum_stock": "2",
            "default_location_id": location,
            "standard_cost": cost,
        })
        items.append(item["id"])
        create(client, "/api/v1/stock/receipts", owner, {
            "location_id": location,
            "lines": [{"item_id": item["id"], "quantity": qty, "unit_cost": cost}],
        })
    with SessionLocal() as db:
        accounts = []
        scopes = []
        for email, role in (
            ("groupb-manager@example.com", "inventory_manager"),
            ("groupb-viewer@example.com", "viewer"),
        ):
            user = User(
                email=email, full_name=email,
                password_hash=hash_password("password123"), role=role,
            )
            db.add(user)
            db.flush()
            scope = OperationalAccessScope(
                user_id=user.id, location_id=a, approval_limit=Decimal("0"),
            )
            db.add(scope)
            db.flush()
            accounts.append(email)
            scopes.append(scope.id)
        db.commit()
    return {
        "owner": owner, "a": a, "b": b, "items": items,
        "manager": auth(client, accounts[0]), "viewer": auth(client, accounts[1]),
        "scope_ids": scopes,
    }


def test_scoped_dashboard_never_leaks_other_site_value_or_details(client):
    data = seed(client)
    owner = client.get("/api/v1/dashboard/summary", headers=data["owner"])
    manager = client.get("/api/v1/dashboard/summary", headers=data["manager"])
    assert owner.status_code == manager.status_code == 200
    assert Decimal(owner.json()["metrics"]["inventory_value"]) == Decimal("190")
    assert Decimal(manager.json()["metrics"]["inventory_value"]) == Decimal("50")
    assert manager.json()["metrics"]["total_products"] == 1
    assert manager.json()["metrics"]["movement_count"] == 1
    assert manager.json()["stock_status"]["in_stock"] == 1
    assert len(manager.json()["recent_movements"]) == 1
    assert manager.json()["recent_movements"][0]["item_id"] == data["items"][0]
    assert data["items"][1] not in str(manager.json())
    assert client.get(
        "/api/v1/dashboard/summary",
        params={"location_id": data["b"]}, headers=data["manager"],
    ).status_code == 403
    explicit = client.get(
        "/api/v1/dashboard/summary",
        params={"location_id": data["a"]}, headers=data["manager"],
    )
    assert explicit.status_code == 200
    assert Decimal(explicit.json()["metrics"]["inventory_value"]) == Decimal("50")


def test_valuation_history_is_scoped_before_aggregation(client):
    data = seed(client)
    owner = client.get("/api/v1/dashboard/valuation-history?days=7", headers=data["owner"])
    manager = client.get("/api/v1/dashboard/valuation-history?days=7", headers=data["manager"])
    assert owner.status_code == manager.status_code == 200
    assert Decimal(owner.json()["current_value"]) == Decimal("190")
    assert Decimal(manager.json()["current_value"]) == Decimal("50")
    assert Decimal(manager.json()["points"][-1]["value"]) == Decimal("50")
    assert client.get(
        "/api/v1/dashboard/valuation-history",
        headers=data["manager"], params={"location_id": data["b"]},
    ).status_code == 403
    with SessionLocal() as db:
        db.get(OperationalAccessScope, data["scope_ids"][0]).is_active = False
        db.commit()
    revoked = client.get("/api/v1/dashboard/valuation-history", headers=data["manager"])
    assert revoked.status_code == 200
    assert Decimal(revoked.json()["current_value"]) == 0
    assert all(Decimal(row["value"]) == 0 for row in revoked.json()["points"])
    revoked_summary = client.get("/api/v1/dashboard/summary", headers=data["manager"])
    assert revoked_summary.status_code == 200
    assert revoked_summary.json()["metrics"]["total_products"] == 0
    assert Decimal(revoked_summary.json()["metrics"]["inventory_value"]) == 0
    assert revoked_summary.json()["recent_movements"] == []


def test_location_scoped_users_cannot_read_or_record_global_assurance(client):
    data = seed(client)
    for path in (
        "/api/v1/reports/final-assurance",
        "/api/v1/reports/final-assurance.csv",
    ):
        assert client.get(path, headers=data["owner"]).status_code == 200
        assert client.get(path, headers=data["manager"]).status_code == 403
    assert client.post(
        "/api/v1/reports/final-assurance/record",
        headers=data["manager"],
    ).status_code == 403


def test_dashboard_exceptions_do_not_expose_global_or_other_site_events(client):
    data = seed(client)
    with SessionLocal() as db:
        db.add(IntegrationEvent(
            direction="outbound", source_system="inventory",
            destination_system="accounting",
            event_type="inventory.stock_document.posted",
            aggregate_type="stock_document", aggregate_id="private-exception-b",
            idempotency_key="group-b-other-site-integration",
            status="dead_letter", payload={"message": "private failure"},
        ))
        db.commit()
    owner = client.get("/api/v1/dashboard/exceptions", headers=data["owner"])
    restricted = client.get("/api/v1/dashboard/exceptions", headers=data["viewer"])
    assert owner.status_code == restricted.status_code == 200
    assert any(row["key"] == "failed_integrations" for row in owner.json()["exceptions"])
    assert all(
        row["category"] not in {"integration", "backup"}
        for row in restricted.json()["exceptions"]
    )
    assert "private-exception-b" not in str(restricted.json())
    assert client.get(
        "/api/v1/dashboard/exceptions",
        params={"location_id": data["b"]}, headers=data["viewer"],
    ).status_code == 403


def test_percentage_growth_from_zero_is_not_falsely_reported_as_100():
    from app.api.routes.dashboard import _percent_change
    assert _percent_change(15, 0) is None
    assert _percent_change(0, 0) is None
    assert _percent_change(15, 10) == 50.0
    assert _percent_change(5, 10) == -50.0
