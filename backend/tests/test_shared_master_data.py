def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_shared_identity_resolution(client):
    headers = auth_headers(client)
    listing = client.get("/api/v1/shared-identities", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["count"] >= 1
    owner = next(row for row in listing.json()["identities"] if row["email"] == "owner@example.com")
    assert owner["canonical_user_id"]
    assert owner["employee_identity_key"] == owner["canonical_user_id"]

    resolved = client.get("/api/v1/shared-identities/resolve?email=OWNER%40EXAMPLE.COM", headers=headers)
    assert resolved.status_code == 200
    assert resolved.json()["canonical_user_id"] == owner["canonical_user_id"]


def test_master_data_workspace_and_publish(client):
    headers = auth_headers(client)
    category = client.post("/api/v1/categories", headers=headers, json={"name": "Shared master data"}).json()
    unit = client.post("/api/v1/units", headers=headers, json={"code": "SMD", "name": "Shared unit", "precision": 3}).json()
    client.post("/api/v1/locations", headers=headers, json={"code": "SHARED-LOC", "name": "Shared Location", "location_type": "storage"})
    item = client.post("/api/v1/items", headers=headers, json={"sku": "SHARED-ITEM", "name": "Shared Item", "category_id": category["id"], "base_unit_id": unit["id"], "standard_cost": 12}).json()
    client.post("/api/v1/suppliers", headers=headers, json={"code": "SHARED-SUP", "name": "Shared Supplier", "payment_terms_days": 30})

    workspace = client.get("/api/v1/master-data/workspace", headers=headers)
    assert workspace.status_code == 200
    payload = workspace.json()
    assert any(row["code"] == "SHARED-ITEM" for row in payload["items"])
    assert any(row["code"] == "SHARED-LOC" for row in payload["locations"])
    assert any(row["code"] == "SHARED-SUP" for row in payload["suppliers"])

    first = client.post("/api/v1/master-data/publish", headers=headers, json={"destinations": ["staff", "command-center", "accounting"]})
    assert first.status_code == 200
    assert {row["destination"] for row in first.json()["published"]} == {"staff", "command-center", "accounting"}
    first_revision = first.json()["snapshot_revision"]

    client.patch(f"/api/v1/items/{item['id']}", headers=headers, json={"name": "Shared Item Updated"})
    second = client.post("/api/v1/master-data/publish", headers=headers, json={"destinations": ["staff"]})
    assert second.status_code == 200
    assert second.json()["snapshot_revision"] != first_revision


def test_publish_rejects_unknown_destination(client):
    headers = auth_headers(client)
    response = client.post("/api/v1/master-data/publish", headers=headers, json={"destinations": ["unknown-system"]})
    assert response.status_code == 422
