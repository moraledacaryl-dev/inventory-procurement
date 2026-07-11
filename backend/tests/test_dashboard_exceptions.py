def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_role_dashboard_exception_payload(client):
    response = client.get("/api/v1/dashboard/exceptions", headers=auth_headers(client))
    assert response.status_code == 200
    payload = response.json()
    assert payload["role"] == "owner"
    assert payload["workspace"]["title"] == "Management control centre"
    assert isinstance(payload["workspace"]["quick_actions"], list)
    assert set(payload["summary"]) == {"total", "critical", "warning"}
    assert isinstance(payload["exceptions"], list)
    assert all(item["severity"] in {"critical", "warning", "info"} for item in payload["exceptions"])
    assert all(item["href"].startswith("/") for item in payload["exceptions"])


def test_role_dashboard_location_filter(client):
    headers = auth_headers(client)
    locations = client.get("/api/v1/locations", headers=headers)
    assert locations.status_code == 200
    rows = locations.json()
    if rows:
        response = client.get(f"/api/v1/dashboard/exceptions?location_id={rows[0]['id']}", headers=headers)
        assert response.status_code == 200
        assert response.json()["role"] == "owner"
