def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_location_detail_payload(client):
    headers = auth_headers(client)
    locations = client.get("/api/v1/locations", headers=headers)
    assert locations.status_code == 200
    rows = locations.json()
    if not rows:
        return

    response = client.get(f"/api/v1/locations/{rows[0]['id']}", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["location"]["id"] == rows[0]["id"]
    assert set(payload["metrics"]) == {
        "item_count", "total_quantity", "inventory_value", "negative_balances",
        "low_stock_items", "policy_count", "inbound_transfers", "outbound_transfers",
        "lot_quantity",
    }
    assert isinstance(payload["children"], list)
    assert isinstance(payload["balances"], list)
    assert isinstance(payload["policies"], list)
    assert isinstance(payload["recent_movements"], list)


def test_location_update_rejects_self_parent(client):
    headers = auth_headers(client)
    locations = client.get("/api/v1/locations", headers=headers).json()
    if not locations:
        return
    location_id = locations[0]["id"]
    response = client.patch(
        f"/api/v1/locations/{location_id}",
        headers=headers,
        json={"parent_id": location_id},
    )
    assert response.status_code == 422


def test_missing_location_detail(client):
    response = client.get("/api/v1/locations/not-a-real-id", headers=auth_headers(client))
    assert response.status_code == 404
