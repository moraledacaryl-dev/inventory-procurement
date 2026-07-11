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

    response = client.get(f"/api/v1/locations/{rows[0]['id']}/detail", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["location"]["id"] == rows[0]["id"]
    assert set(payload["metrics"]) == {
        "total_quantity", "inventory_value", "stocked_items", "nonzero_items",
        "negative_items", "low_stock_items", "open_inbound_transfers",
        "open_outbound_transfers", "open_purchase_orders",
    }
    assert isinstance(payload["children"], list)
    assert isinstance(payload["balances"], list)
    assert isinstance(payload["policies"], list)
    assert isinstance(payload["recent_movements"], list)
    assert "can_deactivate" in payload["controls"]
    assert isinstance(payload["controls"]["deactivation_blockers"], list)


def test_location_update_and_hierarchy_validation(client):
    headers = auth_headers(client)
    locations = client.get("/api/v1/locations", headers=headers).json()
    if not locations:
        return
    location = locations[0]

    updated = client.patch(
        f"/api/v1/locations/{location['id']}",
        headers=headers,
        json={"name": location["name"]},
    )
    assert updated.status_code == 200

    invalid_parent = client.patch(
        f"/api/v1/locations/{location['id']}",
        headers=headers,
        json={"parent_id": location["id"]},
    )
    assert invalid_parent.status_code == 422


def test_missing_location_detail(client):
    response = client.get("/api/v1/locations/not-a-real-id/detail", headers=auth_headers(client))
    assert response.status_code == 404
