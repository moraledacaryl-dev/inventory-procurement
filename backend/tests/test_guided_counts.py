def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_count_context(client, headers):
    category = client.post("/api/v1/categories", headers=headers, json={"name": "Count goods"}).json()
    unit = client.post("/api/v1/units", headers=headers, json={"code": "EA", "name": "Each", "precision": 2}).json()
    location = client.post("/api/v1/locations", headers=headers, json={"code": "COUNT-A", "name": "Count Area", "location_type": "storeroom"}).json()
    item = client.post(
        "/api/v1/items",
        headers=headers,
        json={"sku": "COUNT-001", "name": "Count item", "category_id": category["id"], "base_unit_id": unit["id"], "standard_cost": 10},
    ).json()
    receipt = client.post(
        "/api/v1/stock/receipts",
        headers=headers,
        json={"location_id": location["id"], "idempotency_key": "count-seed", "lines": [{"item_id": item["id"], "quantity": 5, "unit_cost": 10}]},
    )
    assert receipt.status_code == 201
    return location, item


def test_guided_count_save_and_submit(client):
    headers = auth_headers(client)
    location, item = seed_count_context(client, headers)
    created = client.post(
        "/api/v1/counts",
        headers=headers,
        json={"location_id": location["id"], "blind_count": True, "approval_threshold": 10},
    )
    assert created.status_code == 201
    count_id = created.json()["id"]

    detail = client.get(f"/api/v1/counts/{count_id}/detail", headers=headers)
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["blind_count"] is True
    assert payload["lines"][0]["system_quantity"] is None

    saved = client.put(
        f"/api/v1/counts/{count_id}/entries",
        headers=headers,
        json={"lines": [{"item_id": item["id"], "counted_quantity": 4, "note": "one missing"}]},
    )
    assert saved.status_code == 200
    assert saved.json()["progress"]["counted_lines"] == 1

    submitted = client.post(f"/api/v1/counts/{count_id}/submit", headers=headers)
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "posted"
    assert submitted.json()["posted_document_id"]


def test_guided_count_requires_completion(client):
    headers = auth_headers(client)
    location, _item = seed_count_context(client, headers)
    created = client.post("/api/v1/counts", headers=headers, json={"location_id": location["id"], "blind_count": False, "approval_threshold": 0}).json()
    response = client.post(f"/api/v1/counts/{created['id']}/submit", headers=headers)
    assert response.status_code == 422


def test_guided_count_recount_flow(client):
    headers = auth_headers(client)
    location, item = seed_count_context(client, headers)
    created = client.post("/api/v1/counts", headers=headers, json={"location_id": location["id"], "blind_count": False, "approval_threshold": 1}).json()
    count_id = created["id"]
    client.put(f"/api/v1/counts/{count_id}/entries", headers=headers, json={"lines": [{"item_id": item["id"], "counted_quantity": 1}]})
    submitted = client.post(f"/api/v1/counts/{count_id}/submit", headers=headers)
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending_approval"

    recount = client.post(
        f"/api/v1/counts/{count_id}/recount",
        headers=headers,
        json={"item_ids": [item["id"]], "reason": "verify large variance"},
    )
    assert recount.status_code == 200
    payload = recount.json()
    assert payload["status"] == "open"
    assert payload["lines"][0]["counted_quantity"] is None
    assert "Recount requested" in payload["lines"][0]["note"]


def test_guided_count_workspace_and_missing(client):
    headers = auth_headers(client)
    workspace = client.get("/api/v1/counts/workspace", headers=headers)
    assert workspace.status_code == 200
    assert isinstance(workspace.json(), list)
    missing = client.get("/api/v1/counts/not-real/detail", headers=headers)
    assert missing.status_code == 404
