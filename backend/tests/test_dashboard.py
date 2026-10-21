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


def test_dashboard_book_valuation_matches_ledger_even_when_standard_cost_differs(client):
    from decimal import Decimal
    from app.db.session import SessionLocal
    from app.models.inventory import Item
    from tests.test_inventory import setup_master

    headers = auth_headers(client)
    item, location, other = setup_master(client, headers)
    receipt = client.post("/api/v1/stock/receipts", headers=headers, json={
        "location_id": location["id"],
        "lines": [{"item_id": item["id"], "quantity": "5", "unit_cost": "0"}],
    })
    assert receipt.status_code == 201
    with SessionLocal() as db:
        # Historical balances remain book assets even if the item is no longer
        # active. This state can exist after imports or legacy corrections.
        row = db.get(Item, item["id"])
        row.is_active = False
        db.commit()

    for query in ("", f"?location_id={location['id']}"):
        dashboard = client.get(f"/api/v1/dashboard/summary{query}", headers=headers)
        valuation = client.get(f"/api/v1/reports/valuation{query}", headers=headers)
        history = client.get(
            f"/api/v1/dashboard/valuation-history?days=7{'&'+query[1:] if query else ''}",
            headers=headers,
        )
        assert dashboard.status_code == valuation.status_code == history.status_code == 200
        book_value = sum(
            (Decimal(row["inventory_value"]) for row in valuation.json()),
            Decimal("0"),
        )
        assert book_value == 0
        assert Decimal(dashboard.json()["metrics"]["inventory_value"]) == book_value
        assert Decimal(history.json()["current_value"]) == book_value

    # Non-stock service SKUs must not inflate the out-of-stock stock count.
    category = client.post("/api/v1/categories", headers=headers, json={"name": "Services"}).json()
    unit = client.post("/api/v1/units", headers=headers, json={
        "code": "SV", "name": "Service",
    }).json()
    service = client.post("/api/v1/items", headers=headers, json={
        "sku": "NONSTOCK-001", "name": "Service", "category_id": category["id"],
        "base_unit_id": unit["id"], "track_stock": False, "minimum_stock": 9,
    })
    assert service.status_code == 201
    summary = client.get("/api/v1/dashboard/summary", headers=headers).json()
    assert summary["metrics"]["out_of_stock_items"] == 0
    assert summary["stock_status"]["out_of_stock"] == 0


def test_dashboard_location_minimum_override_and_inactive_override(client):
    from decimal import Decimal
    from tests.test_inventory import setup_master

    headers = auth_headers(client)
    item, location, other = setup_master(client, headers)
    receipt = client.post("/api/v1/stock/receipts", headers=headers, json={
        "location_id": location["id"],
        "lines": [{"item_id": item["id"], "quantity": "5", "unit_cost": "40"}],
    })
    assert receipt.status_code == 201
    setting = client.post("/api/v1/item-location-settings", headers=headers, json={
        "item_id": item["id"], "location_id": location["id"],
        "minimum_stock": "8", "reorder_quantity": "10",
    })
    assert setting.status_code == 201
    local = client.get(
        f"/api/v1/dashboard/summary?location_id={location['id']}",
        headers=headers,
    ).json()
    assert local["stock_status"]["low_stock"] == 1
    assert Decimal(local["low_stock"][0]["minimum_stock"]) == Decimal("8")
    assert Decimal(local["low_stock"][0]["shortfall"]) == Decimal("3")
    assert Decimal(local["metrics"]["inventory_value"]) == Decimal("200")

    global_summary = client.get("/api/v1/dashboard/summary", headers=headers).json()
    assert global_summary["stock_status"]["in_stock"] == 1
    assert global_summary["metrics"]["low_stock_items"] == 0
    assert Decimal(global_summary["metrics"]["inventory_value"]) == Decimal("200")
