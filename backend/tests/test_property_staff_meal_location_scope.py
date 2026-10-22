"""Location isolation for staff meals and reusable-property control.

All endpoints are exercised as real role-authenticated HTTP requests. A narrow
location scope must not leak the other kitchen's food costs or linen balances,
post a second receipt, reverse a foreign meal, or move property across sites.
"""

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


def create(client, route, headers, data):
    response = client.post(route, headers=headers, json=data)
    assert response.status_code == 201, (route, response.text)
    return response.json()


def fixture(client):
    owner = login(client)
    category = create(client, "/api/v1/categories", owner, {"name": "Scoped property + kitchen"})
    unit = create(client, "/api/v1/units", owner, {"code": "SML", "name": "Staff meal scope unit"})
    a, b = [
        create(client, "/api/v1/locations", owner, {"code": code, "name": code, "location_type": "kitchen"})["id"]
        for code in ("SCOPE-KITCHEN-A", "SCOPE-KITCHEN-B")
    ]
    ingredient = create(client, "/api/v1/items", owner, {
        "sku": "SCOPE-RICE", "name": "Staff meal rice",
        "category_id": category["id"], "base_unit_id": unit["id"], "standard_cost": "60",
    })["id"]
    for loc in (a, b):
        create(client, "/api/v1/stock/receipts", owner, {
            "location_id": loc,
            "lines": [{"item_id": ingredient, "quantity": "20", "unit_cost": "60"}],
        })
    with SessionLocal() as db:
        for email in ("staff-meal-A@example.com", "staff-meal-open@example.com"):
            db.add(User(email=email, full_name=email, role="inventory_manager",
                        password_hash=hash_password("password123")))
        db.commit()
        assigned = db.query(User).filter(User.email == "staff-meal-A@example.com").one().id
    scope = create(client, "/api/v1/access-scopes", owner, {
        "user_id": assigned, "location_id": a, "approval_limit": "0",
    })["id"]
    return {
        "owner": owner, "scoped": login(client, "staff-meal-A@example.com"),
        "unconfigured": login(client, "staff-meal-open@example.com"),
        "a": a, "b": b, "item": ingredient, "scope": scope,
    }


def meal_payload(data, loc, key):
    return {
        "meal_name": "Rice for staff", "meal_period": "Lunch",
        "location_id": loc, "servings": 2, "idempotency_key": key,
        "lines": [{"item_id": data["item"], "quantity": "2"}],
    }


def test_staff_meals_scoped_preview_post_list_detail_and_reversal(client):
    data = fixture(client)
    owner, scoped, open_user = data["owner"], data["scoped"], data["unconfigured"]
    a, b = data["a"], data["b"]
    meal_a = create(client, "/api/v1/staff-meals", owner, meal_payload(data, a, "scoped-staff-meal-A"))
    meal_b = create(client, "/api/v1/staff-meals", owner, meal_payload(data, b, "scoped-staff-meal-B"))

    for route in ("/api/v1/staff-meals",):
        assert {r["id"] for r in client.get(route, headers=scoped).json()} == {meal_a["id"]}
        assert {r["id"] for r in client.get(route, headers=open_user).json()} == {meal_a["id"], meal_b["id"]}
    assert client.get(f"/api/v1/staff-meals/{meal_a['id']}", headers=scoped).status_code == 200
    assert client.get(f"/api/v1/staff-meals/{meal_b['id']}", headers=scoped).status_code == 403
    assert client.post("/api/v1/staff-meals/preview", headers=scoped, json=meal_payload(
        data, b, "foreign-preview")).status_code == 403
    ok_preview = client.post("/api/v1/staff-meals/preview", headers=scoped, json=meal_payload(
        data, a, "local-preview"))
    assert ok_preview.status_code == 200, ok_preview.text

    # The idempotency key of an already posted foreign meal must not bypass
    # current access control or reveal the existing posting.
    assert client.post("/api/v1/staff-meals", headers=scoped, json=meal_payload(
        data, b, "scoped-staff-meal-B")).status_code == 403
    assert client.post("/api/v1/staff-meals", headers=scoped, json=meal_payload(
        data, b, "foreign-new-meal")).status_code == 403
    assert client.post(f"/api/v1/staff-meals/{meal_b['id']}/reverse",
                       headers=scoped).status_code == 403
    assert client.get(f"/api/v1/staff-meals/{meal_b['id']}", headers=owner).json()["status"] == "posted"
    assert client.post(f"/api/v1/staff-meals/{meal_a['id']}/reverse",
                       headers=scoped).status_code == 200
    assert client.get(f"/api/v1/staff-meals/{meal_a['id']}", headers=owner).json()["status"] == "reversed"
    assert client.get(f"/api/v1/staff-meals/{meal_b['id']}", headers=owner).json()["status"] == "posted"

    with SessionLocal() as db:
        db.get(OperationalAccessScope, data["scope"]).is_active = False
        db.commit()
    assert client.get("/api/v1/staff-meals", headers=scoped).json() == []
    assert client.get(f"/api/v1/staff-meals/{meal_a['id']}", headers=scoped).status_code == 403
    assert client.post("/api/v1/staff-meals/preview", headers=scoped, json=meal_payload(
        data, a, "revoked-preview")).status_code == 403
    assert client.post("/api/v1/staff-meals", headers=scoped, json=meal_payload(
        data, a, "revoked-post")).status_code == 403


def reusable_fixture(client, owner, data):
    dimension_rows = client.get("/api/v1/classification/bootstrap", headers=owner).json()["dimensions"]
    def find(typ, code):
        return next(row["id"] for row in dimension_rows[typ] if row["code"] == code)
    hotel = find("workspace", "hotel")
    linen = find("item_type", "linen")
    available = find("condition_status", "available")
    receipt_reason = find("movement_reason", "receipt")
    item = create(client, "/api/v1/items", owner, {
        "sku": "SCOPE-TOWEL", "name": "Scoped towel",
        "category_id": client.get("/api/v1/categories", headers=owner).json()[0]["id"],
        "base_unit_id": client.get("/api/v1/units", headers=owner).json()[0]["id"],
        "primary_workspace_id": hotel, "item_type_id": linen,
    })["id"]
    return item, available, receipt_reason


def property_payload(item, loc, condition, reason):
    return {"item_id": item, "quantity": "10",
            "destination_location_id": loc,
            "destination_condition_id": condition,
            "movement_reason_id": reason}


def test_property_stock_circulation_and_par_settings_protect_both_endpoints(client):
    data = fixture(client)
    owner, scoped, open_user = data["owner"], data["scoped"], data["unconfigured"]
    a, b = data["a"], data["b"]
    item, condition, reason = reusable_fixture(client, owner, data)
    r_a = create(client, "/api/v1/property/movements", owner, property_payload(item, a, condition, reason))
    r_b = create(client, "/api/v1/property/movements", owner, property_payload(item, b, condition, reason))
    assert {x["destination_location_id"] for x in client.get(
        "/api/v1/property/movements", headers=scoped).json()} == {a}
    assert {x["destination_location_id"] for x in client.get(
        "/api/v1/property/movements", headers=open_user).json()} == {a, b}
    assert {x["location_id"] for x in client.get("/api/v1/property/balances", headers=scoped).json()} == {a}
    assert client.get(f"/api/v1/property/balances?location_id={b}", headers=scoped).status_code == 403

    transfer = {
        "item_id": item, "quantity": "2",
        "source_location_id": a, "source_condition_id": condition,
        "destination_location_id": b, "destination_condition_id": condition,
    }
    assert client.post("/api/v1/property/movements", headers=scoped,
                       json=transfer).status_code == 403
    assert client.post("/api/v1/property/movements", headers=scoped,
                       json=property_payload(item, b, condition, reason)).status_code == 403
    original = {x["location_id"]: Decimal(x["quantity"]) for x in client.get(
        "/api/v1/property/balances", headers=owner).json()}
    assert original == {a: Decimal("10"), b: Decimal("10")}

    # Owner can circulate cross-location linen, but its private destination
    # must not appear in the scoped user's movement history.
    move = create(client, "/api/v1/property/movements", owner, transfer)
    scoped_moves = client.get("/api/v1/property/movements", headers=scoped).json()
    assert {row["id"] for row in scoped_moves} == {r_a["id"]}
    assert move["id"] not in {row["id"] for row in scoped_moves}
    assert {x["location_id"]: Decimal(x["quantity"]) for x in client.get(
        "/api/v1/property/balances", headers=owner).json()} == {
        a: Decimal("8"), b: Decimal("12"),
    }

    profile_a = create(client, "/api/v1/hotel/par-profiles", owner, {
        "code": "SCOPE-PAR-A", "name": "Kitchen A linens",
        "location_id": a, "lines": [{"item_id": item, "par_quantity": "2"}],
    })
    create(client, "/api/v1/hotel/par-profiles", owner, {
        "code": "SCOPE-PAR-B", "name": "Kitchen B linens",
        "location_id": b, "lines": [{"item_id": item, "par_quantity": "3"}],
    })
    create(client, "/api/v1/hotel/par-profiles", owner, {
        "code": "SCOPE-PAR-GLOBAL", "name": "Hotel global par",
        "lines": [{"item_id": item, "par_quantity": "1"}],
    })
    assert {entry["profile"]["code"] for entry in client.get(
        "/api/v1/hotel/par-profiles", headers=scoped).json()} == {"SCOPE-PAR-A"}
    assert len(client.get("/api/v1/hotel/par-profiles", headers=owner).json()) == 3
    assert client.post("/api/v1/hotel/par-profiles", headers=scoped, json={
        "code": "FOREIGN-PAR", "name": "Should be denied", "location_id": b,
        "lines": [{"item_id": item, "par_quantity": "1"}],
    }).status_code == 403
    assert client.post("/api/v1/hotel/par-profiles", headers=scoped, json={
        "code": "GLOBAL-PAR-2", "name": "Should be denied",
        "lines": [{"item_id": item, "par_quantity": "1"}],
    }).status_code == 403
    local = create(client, "/api/v1/hotel/par-profiles", scoped, {
        "code": "LOCAL-PAR-2", "name": "Allowed A", "location_id": a,
        "lines": [{"item_id": item, "par_quantity": "1"}],
    })
    assert local["profile"]["location_id"] == a

    with SessionLocal() as db:
        db.get(OperationalAccessScope, data["scope"]).is_active = False
        db.commit()
    assert client.get("/api/v1/property/balances", headers=scoped).json() == []
    assert client.get("/api/v1/property/movements", headers=scoped).json() == []
    assert client.get("/api/v1/hotel/par-profiles", headers=scoped).json() == []
    assert client.post("/api/v1/property/movements", headers=scoped,
                       json=property_payload(item, a, condition, reason)).status_code == 403
