def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_item_configuration_payload(client):
    headers = auth_headers(client)
    items = client.get("/api/v1/items", headers=headers)
    assert items.status_code == 200
    rows = items.json()
    if not rows:
        return

    response = client.get(f"/api/v1/items/{rows[0]['id']}/configuration", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"barcodes", "conversions", "supplier_items", "location_settings"}
    assert all(isinstance(payload[key], list) for key in payload)


def test_missing_item_configuration(client):
    response = client.get("/api/v1/items/not-a-real-id/configuration", headers=auth_headers(client))
    assert response.status_code == 404
