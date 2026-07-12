from decimal import Decimal


def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_batch(client, headers, suffix="A", optional=False):
    category = client.post("/api/v1/categories", headers=headers, json={"name": f"Production {suffix}"}).json()
    unit = client.post("/api/v1/units", headers=headers, json={"code": f"PR{suffix}", "name": f"Production unit {suffix}", "precision": 3}).json()
    location = client.post("/api/v1/locations", headers=headers, json={"code": f"KITCH-{suffix}", "name": f"Kitchen {suffix}", "location_type": "kitchen"}).json()
    ingredient = client.post("/api/v1/items", headers=headers, json={"sku": f"ING-{suffix}", "name": f"Ingredient {suffix}", "category_id": category["id"], "base_unit_id": unit["id"], "standard_cost": 10}).json()
    output = client.post("/api/v1/items", headers=headers, json={"sku": f"OUT-{suffix}", "name": f"Output {suffix}", "category_id": category["id"], "base_unit_id": unit["id"], "standard_cost": 0}).json()
    receipt = client.post("/api/v1/stock/receipts", headers=headers, json={"location_id": location["id"], "idempotency_key": f"production-seed-{suffix}", "lines": [{"item_id": ingredient["id"], "quantity": 100, "unit_cost": 10}]})
    assert receipt.status_code == 201
    recipe = client.post("/api/v1/recipes", headers=headers, json={"code": f"RCP-{suffix}", "name": f"Recipe {suffix}", "output_item_id": output["id"], "yield_quantity": 10, "lines": [{"ingredient_item_id": ingredient["id"], "quantity": 5, "waste_factor": 0, "optional": optional}]}).json()
    from app.db.session import SessionLocal
    from app.models.production import Recipe
    with SessionLocal() as db:
        row = db.get(Recipe, recipe["id"])
        row.status = "approved"
        db.commit()
    batch = client.post("/api/v1/production-batches", headers=headers, json={"recipe_id": recipe["id"], "location_id": location["id"], "planned_quantity": 20, "notes": "Dinner prep"})
    assert batch.status_code == 201
    return location, ingredient, output, batch.json()


def test_start_and_execute_batch_with_variance(client):
    headers = auth_headers(client)
    location, ingredient, output, batch = seed_batch(client, headers, "EX")
    detail = client.get(f"/api/v1/production-batches/{batch['id']}/execution-detail", headers=headers)
    assert detail.status_code == 200
    assert Decimal(detail.json()["materials"][0]["planned_quantity"]) == Decimal("10")
    assert client.post(f"/api/v1/production-batches/{batch['id']}/start", headers=headers).status_code == 200
    executed = client.post(
        f"/api/v1/production-batches/{batch['id']}/execute",
        headers=headers,
        json={"good_output_quantity": 18, "output_waste_quantity": 2, "materials": [{"item_id": ingredient["id"], "actual_quantity": 11}], "notes": "Recorded after service"},
    )
    assert executed.status_code == 200
    payload = executed.json()
    assert payload["execution"]["batch"]["status"] == "completed"
    assert Decimal(payload["variance"]["yield_variance"]) == Decimal("-2")
    assert Decimal(payload["variance"]["waste_cost"]) == Decimal("11")
    balances = client.get(f"/api/v1/stock/balances?location_id={location['id']}", headers=headers).json()
    assert Decimal(next(row for row in balances if row["item_id"] == ingredient["id"])["quantity"]) == Decimal("89")
    assert Decimal(next(row for row in balances if row["item_id"] == output["id"])["quantity"]) == Decimal("18")


def test_execution_requires_explicit_required_material(client):
    headers = auth_headers(client)
    _location, _ingredient, _output, batch = seed_batch(client, headers, "REQ")
    client.post(f"/api/v1/production-batches/{batch['id']}/start", headers=headers)
    response = client.post(f"/api/v1/production-batches/{batch['id']}/execute", headers=headers, json={"good_output_quantity": 20, "materials": []})
    assert response.status_code == 422


def test_optional_material_may_be_zero(client):
    headers = auth_headers(client)
    _location, ingredient, _output, batch = seed_batch(client, headers, "OPT", optional=True)
    client.post(f"/api/v1/production-batches/{batch['id']}/start", headers=headers)
    response = client.post(f"/api/v1/production-batches/{batch['id']}/execute", headers=headers, json={"good_output_quantity": 20, "materials": [{"item_id": ingredient["id"], "actual_quantity": 0}]})
    assert response.status_code == 200


def test_cancel_open_batch_requires_reason(client):
    headers = auth_headers(client)
    _location, _ingredient, _output, batch = seed_batch(client, headers, "CAN")
    assert client.post(f"/api/v1/production-batches/{batch['id']}/cancel", headers=headers, json={}).status_code == 422
    response = client.post(f"/api/v1/production-batches/{batch['id']}/cancel", headers=headers, json={"reason": "Schedule changed"})
    assert response.status_code == 200
    assert response.json()["batch"]["status"] == "cancelled"
