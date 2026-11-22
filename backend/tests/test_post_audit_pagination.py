"""Regression coverage for bounded staff lists and full-scope financial totals."""
from decimal import Decimal

from app.db.session import SessionLocal
from app.models.procurement import PurchaseOrder


def owner(client):
    response = client.post("/api/v1/auth/login", json={
        "email": "owner@example.com", "password": "password123"
    })
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_catalogue(client, headers):
    category = client.post("/api/v1/categories", headers=headers, json={"name": "Page goods"}).json()
    unit = client.post("/api/v1/units", headers=headers, json={
        "code": "PAGE", "name": "Page units", "precision": 2
    }).json()
    location = client.post("/api/v1/locations", headers=headers, json={
        "code": "PAGE-STORE", "name": "Paginated Store", "location_type": "storeroom"
    }).json()
    items = []
    for number in range(1, 4):
        created = client.post("/api/v1/items", headers=headers, json={
            "sku": f"PAGE-{number:03d}", "name": f"Page Item {number}",
            "category_id": category["id"], "base_unit_id": unit["id"],
            "standard_cost": 10,
        })
        assert created.status_code == 201
        items.append(created.json())
    return location, items


def test_item_catalogue_pages_and_scope_metrics_are_stable(client):
    headers = owner(client)
    _location, items = seed_catalogue(client, headers)
    p1 = client.get("/api/v1/items/catalogue-workspace?page=1&page_size=1", headers=headers)
    assert p1.status_code == 200
    payload = p1.json()
    assert payload["summary"]["catalogue_items"] == 3
    assert payload["summary"]["active_items"] == 3
    assert payload["summary"]["tracked_items"] == 3
    assert payload["pagination"]["total"] == 3
    assert payload["pagination"]["has_next"] is True
    assert len(payload["items"]) == 1
    page_two = client.get("/api/v1/items/catalogue-workspace?page=2&page_size=1", headers=headers).json()
    assert page_two["items"][0]["id"] != payload["items"][0]["id"]
    search = client.get("/api/v1/items/catalogue-workspace?q=PAGE-003", headers=headers).json()
    assert search["pagination"]["total"] == 1
    assert search["items"][0]["id"] == items[2]["id"]
    assert search["summary"]["catalogue_items"] == 3
    # An older integration that needs all rows still gets the unchanged list.
    assert len(client.get("/api/v1/items", headers=headers).json()) == 3
    assert client.get("/api/v1/items/catalogue-workspace?page=0", headers=headers).status_code == 422


def test_count_session_pagination_and_search(client):
    headers = owner(client)
    location, items = seed_catalogue(client, headers)
    counts = []
    for _ in range(3):
        response = client.post("/api/v1/counts", headers=headers, json={
            "location_id": location["id"], "blind_count": True
        })
        assert response.status_code == 201
        counts.append(response.json())
    result = client.get("/api/v1/counts/workspace?page=1&page_size=2", headers=headers)
    assert result.status_code == 200
    page = result.json()
    assert page["pagination"]["total"] == 3
    assert page["pagination"]["has_next"] is True
    assert len(page["rows"]) == 2
    assert page["rows"][0]["progress"]["variance_lines"] is None
    next_page = client.get("/api/v1/counts/workspace?page=2&page_size=2", headers=headers).json()
    assert len(next_page["rows"]) == 1
    lookup = client.get(
        f"/api/v1/counts/workspace?page=1&page_size=10&q={counts[0]['count_number']}",
        headers=headers,
    ).json()
    assert lookup["pagination"]["total"] == 1
    assert lookup["rows"][0]["id"] == counts[0]["id"]
    assert isinstance(client.get("/api/v1/counts/workspace", headers=headers).json(), list)


def test_receiving_selector_limit_search_keeps_all_time_totals(client):
    headers = owner(client)
    location, items = seed_catalogue(client, headers)
    supplier = client.post("/api/v1/suppliers", headers=headers, json={
        "code": "PAGE-SUP", "name": "Bounded Supplies"
    }).json()
    orders = []
    for _ in range(3):
        response = client.post("/api/v1/purchase-orders", headers=headers, json={
            "supplier_id": supplier["id"],
            "delivery_location_id": location["id"],
            "lines": [{"item_id": items[0]["id"], "ordered_quantity": 3, "unit_price": 10}],
        })
        assert response.status_code == 201
        orders.append(response.json())
    with SessionLocal() as db:
        for order in orders:
            row = db.get(PurchaseOrder, order["id"])
            row.status = "approved"
        db.commit()
    result = client.get("/api/v1/receiving/workspace?po_limit=1", headers=headers)
    assert result.status_code == 200
    page = result.json()
    assert len(page["purchase_orders"]) == 1
    assert page["pagination"]["purchase_orders"]["total"] == 3
    assert page["pagination"]["purchase_orders"]["has_more"] is True
    assert page["summary"]["receivable_orders"] == 3
    query = client.get(
        f"/api/v1/receiving/workspace?po_limit=1&po_search={orders[0]['purchase_order_number']}",
        headers=headers,
    ).json()
    assert query["pagination"]["purchase_orders"]["total"] == 1
    assert query["purchase_orders"][0]["id"] == orders[0]["id"]
    assert query["summary"]["receivable_orders"] == 3
    assert len(client.get("/api/v1/receiving/workspace", headers=headers).json()["purchase_orders"]) == 3


def test_purchase_order_paging_does_not_truncate_commitments(client):
    headers = owner(client)
    location, items = seed_catalogue(client, headers)
    supplier = client.post("/api/v1/suppliers", headers=headers, json={
        "code": "PO-PAGE-SUP", "name": "Order Paging Supplier"
    }).json()
    orders = []
    for n in range(3):
        response = client.post("/api/v1/purchase-orders", headers=headers, json={
            "supplier_id": supplier["id"], "delivery_location_id": location["id"],
            "lines": [{"item_id": items[0]["id"], "ordered_quantity": 2, "unit_price": 10 + n}],
        })
        assert response.status_code == 201
        orders.append(response.json())
    result = client.get(
        "/api/v1/procurement/quotation-workspace?po_page=1&po_page_size=1",
        headers=headers,
    )
    assert result.status_code == 200
    body = result.json()
    assert body["po_pagination"]["total"] == 3
    assert body["po_pagination"]["has_next"] is True
    assert len(body["purchase_orders"]) == 1
    assert body["summary"]["open_purchase_orders"] == 3
    assert Decimal(body["summary"]["open_commitment_value"]) == Decimal("66")
    filtered = client.get(
        f"/api/v1/procurement/quotation-workspace?po_page=1&po_search={orders[0]['purchase_order_number']}",
        headers=headers,
    ).json()
    assert filtered["po_pagination"]["total"] == 1
    assert filtered["purchase_orders"][0]["id"] == orders[0]["id"]
    assert filtered["summary"]["open_purchase_orders"] == 3
    assert Decimal(filtered["summary"]["open_commitment_value"]) == Decimal("66")
