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


def test_valuation_history_uses_exact_book_delta_when_negative_stock_turns_positive(client):
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.inventory import Item, StockBalance, StockMovement
    from app.models.user import User
    from app.services.inventory import post_document
    from tests.test_inventory import setup_master

    headers = auth_headers(client)
    item, location, _ = setup_master(client, headers)
    with SessionLocal() as db:
        db.get(Item, item["id"]).allow_negative_stock = True
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        db.commit()
        receipt = post_document(db, kind="receipt", actor_id=owner.id, entries=[{
            "item_id": item["id"], "location_id": location["id"], "quantity": "2", "unit_cost": "40"
        }])
        issued = post_document(db, kind="issue", actor_id=owner.id, entries=[{
            "item_id": item["id"], "location_id": location["id"], "quantity": "-5"
        }])
        yesterday = datetime.now(timezone.utc) - timedelta(days=2)
        for document in (receipt, issued):
            movement = db.scalar(select(StockMovement).where(StockMovement.document_id == document.id))
            movement.created_at = yesterday
        db.commit()
        replacement = post_document(db, kind="receipt", actor_id=owner.id, entries=[{
            "item_id": item["id"], "location_id": location["id"], "quantity": "5", "unit_cost": "100"
        }])
        replacement_move = db.scalar(select(StockMovement).where(StockMovement.document_id == replacement.id))
        balance = db.scalar(select(StockBalance).where(
            StockBalance.item_id == item["id"], StockBalance.location_id == location["id"]
        ))
        assert balance.quantity == Decimal("2")
        assert balance.average_cost == Decimal("100")
        assert replacement_move.quantity * replacement_move.unit_cost == Decimal("500")
        assert replacement_move.book_value_delta == Decimal("320")
        assert balance.quantity * balance.average_cost == Decimal("200")

    response = client.get(
        f"/api/v1/dashboard/valuation-history?days=7&location_id={location['id']}",
        headers=headers,
    )
    assert response.status_code == 200
    history = response.json()
    assert Decimal(history["points"][-3]["value"]) == Decimal("-120")
    assert Decimal(history["points"][-1]["value"]) == Decimal("200")
    assert Decimal(history["current_value"]) == Decimal("200")
    assert history["legacy_movement_count"] == 0
    assert history["historical_values_estimated"] is False
    assert all(point["estimated"] is False for point in history["points"])
    ledger = client.get(f"/api/v1/stock/ledger?item_id={item['id']}&location_id={location['id']}", headers=headers)
    assert ledger.status_code == 200
    summary = ledger.json()["summary"]
    assert Decimal(summary["net_value"]) == Decimal("380")
    assert Decimal(summary["book_value_change"]) == Decimal("200")
    assert summary["legacy_unverified_value_lines"] == 0
    assert Decimal(ledger.json()["rows"][-1]["valuation_difference"]) == Decimal("-180")


def test_valuation_history_marks_legacy_deltas_as_estimates(client):
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.inventory import Item, StockMovement
    from app.models.user import User
    from app.services.inventory import post_document
    from tests.test_inventory import setup_master

    headers = auth_headers(client)
    item, location, _ = setup_master(client, headers)
    with SessionLocal() as db:
        db.get(Item, item["id"]).allow_negative_stock = True
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        db.commit()
        first = post_document(db, kind="receipt", actor_id=owner.id, entries=[{
            "item_id": item["id"], "location_id": location["id"], "quantity": "2", "unit_cost": "40"
        }])
        spent = post_document(db, kind="issue", actor_id=owner.id, entries=[{
            "item_id": item["id"], "location_id": location["id"], "quantity": "-5"
        }])
        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
        for doc in (first, spent):
            move = db.scalar(select(StockMovement).where(StockMovement.document_id == doc.id))
            move.created_at = two_days_ago
        db.commit()
        replenished = post_document(db, kind="receipt", actor_id=owner.id, entries=[{
            "item_id": item["id"], "location_id": location["id"], "quantity": "5", "unit_cost": "100"
        }])
        move = db.scalar(select(StockMovement).where(StockMovement.document_id == replenished.id))
        # A pre-migration row has no persisted valuation delta. Its history
        # must never be displayed as if the reverse calculation were exact.
        move.book_value_delta = None
        db.commit()

    response = client.get(
        f"/api/v1/dashboard/valuation-history?days=7&location_id={location['id']}",
        headers=headers,
    )
    assert response.status_code == 200
    history = response.json()
    assert history["legacy_movement_count"] == 1
    assert history["historical_values_estimated"] is True
    assert history["points"][-3]["estimated"] is True
    assert history["points"][-1]["estimated"] is False
    assert Decimal(history["current_value"]) == Decimal("200")
    assert Decimal(history["points"][-1]["value"]) == Decimal("200")
    ledger = client.get(f"/api/v1/stock/ledger?item_id={item['id']}&location_id={location['id']}", headers=headers)
    assert ledger.status_code == 200
    assert ledger.json()["summary"]["book_value_change"] is None
    assert ledger.json()["summary"]["legacy_unverified_value_lines"] == 1
