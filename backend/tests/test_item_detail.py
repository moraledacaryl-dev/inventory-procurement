from decimal import Decimal


def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_item_detail_and_update(client):
    headers = auth_headers(client)
    items = client.get("/api/v1/items", headers=headers)
    assert items.status_code == 200
    rows = items.json()
    if not rows:
        return

    item = rows[0]
    detail = client.get(f"/api/v1/items/{item['id']}", headers=headers)
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["item"]["id"] == item["id"]
    assert "category" in payload
    assert "base_unit" in payload
    assert set(payload["totals"]) == {"quantity", "inventory_value", "average_cost", "location_count", "movement_count"}
    assert isinstance(payload["balances"], list)
    assert isinstance(payload["recent_movements"], list)

    updated = client.patch(
        f"/api/v1/items/{item['id']}",
        headers=headers,
        json={"name": item["name"], "minimum_stock": str(item["minimum_stock"])},
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == item["id"]


def test_missing_item_detail(client):
    response = client.get("/api/v1/items/not-a-real-id", headers=auth_headers(client))
    assert response.status_code == 404
