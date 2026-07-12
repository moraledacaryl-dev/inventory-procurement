from app.db.session import SessionLocal
from app.models.production import Recipe


def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_mapping(client, headers):
    category = client.post("/api/v1/categories", headers=headers, json={"name": "POS goods"}).json()
    unit = client.post("/api/v1/units", headers=headers, json={"code": "POSU", "name": "POS unit", "precision": 3}).json()
    location = client.post("/api/v1/locations", headers=headers, json={"code": "POS-KITCH", "name": "POS Kitchen", "location_type": "kitchen"}).json()
    ingredient = client.post("/api/v1/items", headers=headers, json={"sku": "POS-ING", "name": "POS Ingredient", "category_id": category["id"], "base_unit_id": unit["id"], "standard_cost": 5}).json()
    output = client.post("/api/v1/items", headers=headers, json={"sku": "POS-OUT", "name": "POS Output", "category_id": category["id"], "base_unit_id": unit["id"], "standard_cost": 0}).json()
    receipt = client.post("/api/v1/stock/receipts", headers=headers, json={"location_id": location["id"], "idempotency_key": "pos-sync-seed", "lines": [{"item_id": ingredient["id"], "quantity": 100, "unit_cost": 5}]})
    assert receipt.status_code == 201
    recipe = client.post("/api/v1/recipes", headers=headers, json={"code": "POS-RCP", "name": "POS Recipe", "output_item_id": output["id"], "yield_quantity": 1, "lines": [{"ingredient_item_id": ingredient["id"], "quantity": 2, "waste_factor": 0, "optional": False}]}).json()
    with SessionLocal() as db:
        row = db.get(Recipe, recipe["id"])
        row.status = "approved"
        db.commit()
    mapping = client.post("/api/v1/pos-mappings", headers=headers, json={"pos_system": "hidden-oasis-pos", "external_product_id": "CAFE-001", "recipe_id": recipe["id"], "location_id": location["id"]})
    assert mapping.status_code == 201
    return location, ingredient, recipe, mapping.json()


def test_pos_workspace_and_mapping_lifecycle(client):
    headers = auth_headers(client)
    _location, _ingredient, recipe, mapping = seed_mapping(client, headers)
    workspace = client.get("/api/v1/integrations/pos/workspace", headers=headers)
    assert workspace.status_code == 200
    row = next(item for item in workspace.json()["mappings"] if item["id"] == mapping["id"])
    assert row["healthy"] is True
    assert row["recipe_status"] == "approved"

    deactivated = client.post(f"/api/v1/pos-mappings/{mapping['id']}/deactivate", headers=headers)
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    activated = client.post(f"/api/v1/pos-mappings/{mapping['id']}/activate", headers=headers)
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True

    with SessionLocal() as db:
        row = db.get(Recipe, recipe["id"])
        row.status = "retired"
        db.commit()
    client.post(f"/api/v1/pos-mappings/{mapping['id']}/deactivate", headers=headers)
    blocked = client.post(f"/api/v1/pos-mappings/{mapping['id']}/activate", headers=headers)
    assert blocked.status_code == 409


def test_pos_event_idempotency_and_reversal(client):
    headers = auth_headers(client)
    _location, _ingredient, _recipe, _mapping = seed_mapping(client, headers)
    event = {"external_event_id": "evt-001", "external_sale_id": "sale-001", "pos_system": "hidden-oasis-pos", "event_type": "sale_completed", "lines": [{"external_product_id": "CAFE-001", "quantity": 2}]}
    first = client.post("/api/v1/integrations/pos/events", headers=headers, json=event)
    assert first.status_code == 201
    duplicate = client.post("/api/v1/integrations/pos/events", headers=headers, json=event)
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == first.json()["id"]

    reversal = client.post("/api/v1/integrations/pos/events", headers=headers, json={**event, "external_event_id": "evt-002", "event_type": "sale_refunded"})
    assert reversal.status_code == 201
    assert reversal.json()["reversal_of_event_id"] == first.json()["id"]

    workspace = client.get("/api/v1/integrations/pos/workspace", headers=headers)
    assert workspace.status_code == 200
    assert workspace.json()["summary"]["processed_event_count"] >= 2
