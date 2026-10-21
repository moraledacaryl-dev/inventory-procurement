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


def test_valuation_history_includes_dated_receipts_and_issues(client):
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.inventory import StockMovement
    from tests.test_inventory import setup_master

    headers = auth_headers(client)
    item, location, other_location = setup_master(client, headers)
    for target, quantity in [(location, "10"), (other_location, "3")]:
        result = client.post("/api/v1/stock/receipts", headers=headers, json={
            "location_id": target["id"],
            "lines": [{"item_id": item["id"], "quantity": quantity, "unit_cost": "40"}],
        })
        assert result.status_code == 201
    with SessionLocal() as db:
        for movement in db.scalars(select(StockMovement)):
            movement.created_at = datetime.now(timezone.utc) - timedelta(days=2)
        db.commit()
    result = client.post("/api/v1/stock/issues", headers=headers, json={
        "location_id": location["id"],
        "lines": [{"item_id": item["id"], "quantity": "2"}],
    })
    assert result.status_code == 201
    for query, received, current in [("", 520, 440), (f"&location_id={location['id']}", 400, 320)]:
        result = client.get(f"/api/v1/dashboard/valuation-history?days=7{query}", headers=headers)
        assert result.status_code == 200
        history = result.json()
        assert Decimal(history["points"][0]["value"]) == 0
        assert Decimal(history["points"][-3]["value"]) == received
        assert Decimal(history["points"][-1]["value"]) == current
        assert Decimal(history["current_value"]) == current
