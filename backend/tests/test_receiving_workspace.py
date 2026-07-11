from decimal import Decimal

from app.db.session import SessionLocal
from app.models.procurement import PurchaseOrder


def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_receiving(client, headers):
    category = client.post("/api/v1/categories", headers=headers, json={"name": "Receiving goods"}).json()
    unit = client.post("/api/v1/units", headers=headers, json={"code": "RCV", "name": "Receiving unit", "precision": 2}).json()
    location = client.post("/api/v1/locations", headers=headers, json={"code": "RECV-A", "name": "Receiving Area", "location_type": "storeroom"}).json()
    item = client.post("/api/v1/items", headers=headers, json={"sku": "RECV-001", "name": "Receiving item", "category_id": category["id"], "base_unit_id": unit["id"], "standard_cost": 20}).json()
    supplier = client.post("/api/v1/suppliers", headers=headers, json={"code": "RECV-SUP", "name": "Receiving Supplier"}).json()
    po = client.post("/api/v1/purchase-orders", headers=headers, json={"supplier_id": supplier["id"], "delivery_location_id": location["id"], "lines": [{"item_id": item["id"], "ordered_quantity": 5, "unit_price": 20}]}).json()
    with SessionLocal() as db:
        row = db.get(PurchaseOrder, po["id"])
        row.status = "approved"
        db.commit()
    return location, item, supplier, po


def test_receiving_workspace_and_controlled_receipt(client):
    headers = auth_headers(client)
    location, item, _supplier, po = seed_receiving(client, headers)
    line_id = po["lines"][0]["id"]
    response = client.post(
        f"/api/v1/receiving/purchase-orders/{po['id']}",
        headers=headers,
        json={
            "delivery_reference": "DR-1001",
            "idempotency_key": "receipt-workspace-1",
            "lines": [{
                "purchase_order_line_id": line_id,
                "received_quantity": 5,
                "accepted_quantity": 4,
                "rejected_quantity": 1,
                "discrepancy_reason": "damaged packaging",
                "lot_number": "LOT-RCV-1",
                "manufactured_date": "2026-07-01",
                "expiry_date": "2027-07-01",
            }],
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["has_discrepancy"] is True
    assert Decimal(payload["accepted_value"]) == Decimal("80")
    assert Decimal(payload["rejected_value"]) == Decimal("20")
    assert payload["delivery_location_id"] == location["id"]

    workspace = client.get("/api/v1/receiving/workspace", headers=headers)
    assert workspace.status_code == 200
    body = workspace.json()
    assert body["summary"]["receipts"] == 1
    assert body["summary"]["discrepant_receipts"] == 1
    assert body["purchase_orders"][0]["status"] == "received"

    lots = client.get("/api/v1/lots", headers=headers)
    assert lots.status_code == 200
    assert any(row["lot_number"] == "LOT-RCV-1" and row["item_id"] == item["id"] for row in lots.json())


def test_receipt_rejection_requires_reason(client):
    headers = auth_headers(client)
    _location, _item, _supplier, po = seed_receiving(client, headers)
    response = client.post(
        f"/api/v1/receiving/purchase-orders/{po['id']}",
        headers=headers,
        json={
            "delivery_reference": "DR-1002",
            "lines": [{"purchase_order_line_id": po["lines"][0]["id"], "received_quantity": 2, "accepted_quantity": 1, "rejected_quantity": 1}],
        },
    )
    assert response.status_code == 422


def test_controlled_supplier_return(client):
    headers = auth_headers(client)
    _location, _item, _supplier, po = seed_receiving(client, headers)
    line_id = po["lines"][0]["id"]
    receipt = client.post(
        f"/api/v1/receiving/purchase-orders/{po['id']}",
        headers=headers,
        json={"delivery_reference": "DR-RETURN", "lines": [{"purchase_order_line_id": line_id, "received_quantity": 5, "accepted_quantity": 5, "rejected_quantity": 0}]},
    )
    assert receipt.status_code == 201

    returned = client.post(
        f"/api/v1/receiving/purchase-orders/{po['id']}/returns",
        headers=headers,
        json={"reason": "quality failure", "supplier_reference": "RMA-001", "idempotency_key": "return-workspace-1", "lines": [{"purchase_order_line_id": line_id, "quantity": 2}]},
    )
    assert returned.status_code == 201
    assert returned.json()["purchase_order_id"] == po["id"]
    assert returned.json()["stock_document_id"]

    workspace = client.get("/api/v1/receiving/workspace", headers=headers).json()
    assert workspace["summary"]["returns"] == 1
    line = workspace["purchase_orders"][0]["lines"][0]
    assert Decimal(line["returned_quantity"]) == Decimal("2")
    assert Decimal(line["returnable_quantity"]) == Decimal("3")


def test_missing_receiving_purchase_order(client):
    response = client.post("/api/v1/receiving/purchase-orders/not-real", headers=auth_headers(client), json={"delivery_reference": "DR-X", "lines": [{"purchase_order_line_id": "missing", "received_quantity": 1, "accepted_quantity": 1, "rejected_quantity": 0}]})
    assert response.status_code == 404
