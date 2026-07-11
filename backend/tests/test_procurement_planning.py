from decimal import Decimal


def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_context(client, headers):
    category = client.post("/api/v1/categories", headers=headers, json={"name": "Planning goods"}).json()
    unit = client.post("/api/v1/units", headers=headers, json={"code": "PLN", "name": "Planning unit", "precision": 2}).json()
    location = client.post("/api/v1/locations", headers=headers, json={"code": "PLAN-A", "name": "Planning Area", "location_type": "storeroom"}).json()
    item = client.post(
        "/api/v1/items",
        headers=headers,
        json={"sku": "PLAN-001", "name": "Planning item", "category_id": category["id"], "base_unit_id": unit["id"], "minimum_stock": 10, "standard_cost": 5},
    ).json()
    return location, item


def test_procurement_planning_payload(client):
    headers = auth_headers(client)
    location, item = seed_context(client, headers)
    response = client.get(f"/api/v1/procurement/planning?location_id={location['id']}", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"summary", "rows"}
    assert payload["summary"]["suggestion_count"] >= 1
    row = next(row for row in payload["rows"] if row["item_id"] == item["id"])
    assert Decimal(row["available_quantity"]) == 0
    assert Decimal(row["suggested_quantity"]) >= 10
    assert row["priority"] == "critical"


def test_create_planned_requisition_and_workspace(client):
    headers = auth_headers(client)
    location, item = seed_context(client, headers)
    created = client.post(
        "/api/v1/procurement/planning/requisitions",
        headers=headers,
        json={
            "department": "Operations",
            "location_id": location["id"],
            "justification": "Replenish low stock",
            "lines": [{"item_id": item["id"], "quantity": 10, "estimated_unit_cost": 5}],
        },
    )
    assert created.status_code == 201
    assert created.json()["status"] == "submitted"

    workspace = client.get("/api/v1/procurement/requisitions/workspace", headers=headers)
    assert workspace.status_code == 200
    row = next(row for row in workspace.json() if row["id"] == created.json()["id"])
    assert Decimal(row["estimated_value"]) == Decimal("50")
    assert "location:" in row["lines"][0]["notes"]


def test_missing_planning_location(client):
    response = client.get("/api/v1/procurement/planning?location_id=not-real", headers=auth_headers(client))
    assert response.status_code == 404
