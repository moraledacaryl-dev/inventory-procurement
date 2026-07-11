def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_dashboard_summary_and_history(client):
    headers = auth_headers(client)

    summary = client.get("/api/v1/dashboard/summary?days=30", headers=headers)
    assert summary.status_code == 200
    payload = summary.json()
    assert "as_of" in payload
    assert payload["filters"]["days"] == 30
    assert "inventory_value" in payload["metrics"]
    assert "pending_purchase_orders" in payload["metrics"]
    assert set(payload["stock_status"]) == {"in_stock", "low_stock", "out_of_stock", "inactive"}
    assert isinstance(payload["recent_purchase_orders"], list)
    assert isinstance(payload["recent_movements"], list)

    history = client.get("/api/v1/dashboard/valuation-history?days=7", headers=headers)
    assert history.status_code == 200
    history_payload = history.json()
    assert history_payload["days"] == 7
    assert len(history_payload["points"]) == 7
    assert "current_value" in history_payload


def test_dashboard_rejects_invalid_period(client):
    headers = auth_headers(client)
    response = client.get("/api/v1/dashboard/summary?days=2", headers=headers)
    assert response.status_code == 422
