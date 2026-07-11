def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_supplier_360_payload_and_update(client):
    headers = auth_headers(client)
    created = client.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "code": "SUP-360",
            "name": "Supplier 360 Test",
            "contact_name": "Primary Contact",
            "email": "supplier360@example.com",
            "phone": "+63 900 000 0000",
            "payment_terms_days": 30,
        },
    )
    assert created.status_code == 201
    supplier = created.json()

    detail = client.get(f"/api/v1/suppliers/{supplier['id']}/detail", headers=headers)
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["supplier"]["id"] == supplier["id"]
    assert set(payload) == {"supplier", "metrics", "risk", "items", "purchase_orders", "receipts", "returns", "quotations"}
    assert payload["metrics"]["purchase_orders"] == 0
    assert payload["risk"]["level"] == "normal"
    assert isinstance(payload["risk"]["signals"], list)

    updated = client.patch(
        f"/api/v1/suppliers/{supplier['id']}",
        headers=headers,
        json={"name": "Supplier 360 Updated", "payment_terms_days": 45, "tax_id": "TIN-360"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Supplier 360 Updated"
    assert updated.json()["payment_terms_days"] == 45
    assert updated.json()["tax_id"] == "TIN-360"


def test_supplier_deactivation_without_open_orders(client):
    headers = auth_headers(client)
    supplier = client.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"code": "SUP-INACTIVE", "name": "Inactive Supplier"},
    ).json()
    response = client.patch(
        f"/api/v1/suppliers/{supplier['id']}",
        headers=headers,
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_missing_supplier_360(client):
    response = client.get("/api/v1/suppliers/not-a-real-id/detail", headers=auth_headers(client))
    assert response.status_code == 404
