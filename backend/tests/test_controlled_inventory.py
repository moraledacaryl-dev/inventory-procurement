def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_stock(client, headers):
    category = client.post("/api/v1/categories", headers=headers, json={"name": "Controlled goods"}).json()
    unit = client.post("/api/v1/units", headers=headers, json={"code": "PCS", "name": "Pieces", "precision": 2}).json()
    source = client.post("/api/v1/locations", headers=headers, json={"code": "SRC", "name": "Source", "location_type": "storeroom"}).json()
    destination = client.post("/api/v1/locations", headers=headers, json={"code": "DST", "name": "Destination", "location_type": "storeroom"}).json()
    item = client.post(
        "/api/v1/items",
        headers=headers,
        json={
            "sku": "CONTROL-001",
            "name": "Controlled item",
            "category_id": category["id"],
            "base_unit_id": unit["id"],
            "minimum_stock": 0,
            "standard_cost": 25,
        },
    ).json()
    receipt = client.post(
        "/api/v1/stock/receipts",
        headers=headers,
        json={
            "location_id": source["id"],
            "idempotency_key": "seed-controlled-stock",
            "lines": [{"item_id": item["id"], "quantity": 10, "unit_cost": 25}],
        },
    )
    assert receipt.status_code == 201
    return item, source, destination


def test_controlled_adjustment_and_waste(client):
    headers = auth_headers(client)
    item, source, _destination = seed_stock(client, headers)

    adjustment = client.post(
        "/api/v1/inventory-controls/adjustments",
        headers=headers,
        json={
            "location_id": source["id"],
            "reason_code": "correction",
            "idempotency_key": "adjustment-test-1",
            "lines": [{"item_id": item["id"], "quantity_delta": 2}],
        },
    )
    assert adjustment.status_code == 201
    assert adjustment.json()["reason_code"] == "correction"

    waste = client.post(
        "/api/v1/inventory-controls/waste",
        headers=headers,
        json={
            "item_id": item["id"],
            "location_id": source["id"],
            "quantity": 1,
            "reason_code": "spoilage",
            "idempotency_key": "waste-test-1",
        },
    )
    assert waste.status_code == 201
    assert waste.json()["quantity"] == "1"

    adjustment_rows = client.get("/api/v1/inventory-controls/adjustments", headers=headers)
    waste_rows = client.get("/api/v1/inventory-controls/waste", headers=headers)
    assert adjustment_rows.status_code == 200
    assert waste_rows.status_code == 200
    assert adjustment_rows.json()[0]["reason"] == "correction"
    assert waste_rows.json()[0]["reason_code"] == "spoilage"


def test_transfer_dispatch_transit_and_variance_receipt(client):
    headers = auth_headers(client)
    item, source, destination = seed_stock(client, headers)

    transfer = client.post(
        "/api/v1/transfer-orders",
        headers=headers,
        json={
            "source_location_id": source["id"],
            "destination_location_id": destination["id"],
            "notes": "Controlled transfer test",
            "lines": [{"item_id": item["id"], "quantity": 3}],
        },
    )
    assert transfer.status_code == 201
    transfer_id = transfer.json()["id"]

    dispatched = client.post(f"/api/v1/transfer-orders/{transfer_id}/dispatch", headers=headers)
    assert dispatched.status_code == 200
    dispatch_payload = dispatched.json()
    assert dispatch_payload["status"] == "dispatched"
    assert dispatch_payload["dispatch_document_id"]

    received = client.post(
        f"/api/v1/transfer-orders/{transfer_id}/receive",
        headers=headers,
        json={
            "idempotency_key": "transfer-receipt-test-1",
            "notes": "One unit damaged in transit",
            "lines": [
                {
                    "item_id": item["id"],
                    "received_quantity": 2,
                    "variance_reason": "damaged in transit",
                }
            ],
        },
    )
    assert received.status_code == 200
    payload = received.json()
    assert payload["status"] == "received_with_variance"
    assert payload["requested_quantity"] == "3.0000"
    assert payload["received_quantity"] == "2.0000"
    assert payload["variance_quantity"] == "1.0000"
    assert payload["receipt_document_id"]

    detail = client.get(f"/api/v1/transfer-orders/{transfer_id}/detail", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["lines"][0]["variance_quantity"] == "1.0000"

    balances = client.get(f"/api/v1/stock/balances?item_id={item['id']}", headers=headers).json()
    by_location = {row["location_id"]: row["quantity"] for row in balances}
    assert by_location[source["id"]] == "7.0000"
    assert by_location[destination["id"]] == "2.0000"
    transit = next(row for row in client.get("/api/v1/locations", headers=headers).json() if row["code"] == "IN-TRANSIT")
    assert by_location[transit["id"]] == "0.0000"


def test_transfer_variance_requires_reason(client):
    headers = auth_headers(client)
    item, source, destination = seed_stock(client, headers)
    transfer = client.post(
        "/api/v1/transfer-orders",
        headers=headers,
        json={
            "source_location_id": source["id"],
            "destination_location_id": destination["id"],
            "lines": [{"item_id": item["id"], "quantity": 2}],
        },
    ).json()
    client.post(f"/api/v1/transfer-orders/{transfer['id']}/dispatch", headers=headers)
    response = client.post(
        f"/api/v1/transfer-orders/{transfer['id']}/receive",
        headers=headers,
        json={"lines": [{"item_id": item["id"], "received_quantity": 1}]},
    )
    assert response.status_code == 422
