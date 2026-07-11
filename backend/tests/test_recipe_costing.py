from decimal import Decimal

from app.db.session import SessionLocal
from app.models.production import Recipe


def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_recipe(client, headers):
    category = client.post("/api/v1/categories", headers=headers, json={"name": "Recipe goods"}).json()
    unit = client.post("/api/v1/units", headers=headers, json={"code": "RCP", "name": "Recipe unit", "precision": 3}).json()
    location = client.post("/api/v1/locations", headers=headers, json={"code": "KITCHEN-R", "name": "Recipe Kitchen", "location_type": "kitchen"}).json()
    ingredient = client.post("/api/v1/items", headers=headers, json={"sku": "ING-001", "name": "Ingredient", "category_id": category["id"], "base_unit_id": unit["id"], "standard_cost": 20}).json()
    output = client.post("/api/v1/items", headers=headers, json={"sku": "OUT-001", "name": "Finished Recipe", "category_id": category["id"], "base_unit_id": unit["id"], "standard_cost": 0}).json()
    receipt = client.post("/api/v1/stock/receipts", headers=headers, json={"location_id": location["id"], "idempotency_key": "recipe-cost-seed", "lines": [{"item_id": ingredient["id"], "quantity": 100, "unit_cost": 20}]})
    assert receipt.status_code == 201
    recipe = client.post("/api/v1/recipes", headers=headers, json={"code": "RCP-001", "name": "Costed Recipe", "output_item_id": output["id"], "yield_quantity": 10, "lines": [{"ingredient_item_id": ingredient["id"], "quantity": 5, "waste_factor": 0.1, "optional": False}]}).json()
    return location, ingredient, output, recipe


def test_recipe_costing_detail_and_margin(client):
    headers = auth_headers(client)
    location, ingredient, _output, recipe = seed_recipe(client, headers)
    detail = client.get(f"/api/v1/recipes/{recipe['id']}/costing-detail?location_id={location['id']}", headers=headers)
    assert detail.status_code == 200
    payload = detail.json()
    assert Decimal(payload["summary"]["total_batch_cost"]) == Decimal("110")
    assert Decimal(payload["summary"]["cost_per_output_unit"]) == Decimal("11")
    assert Decimal(payload["summary"]["available_output_quantity"]) > Decimal("100")
    assert payload["lines"][0]["ingredient_item_id"] == ingredient["id"]
    assert Decimal(payload["lines"][0]["effective_quantity"]) == Decimal("5.5")

    margin = client.post(f"/api/v1/recipes/{recipe['id']}/margin-scenario", headers=headers, json={"location_id": location["id"], "selling_price": 25})
    assert margin.status_code == 200
    assert Decimal(margin.json()["gross_profit_per_unit"]) == Decimal("14")
    assert Decimal(margin.json()["food_cost_percent"]) == Decimal("44.00")


def test_recipe_costing_workspace(client):
    headers = auth_headers(client)
    location, _ingredient, _output, recipe = seed_recipe(client, headers)
    response = client.get(f"/api/v1/recipes/costing/workspace?location_id={location['id']}", headers=headers)
    assert response.status_code == 200
    row = next(row for row in response.json()["recipes"] if row["id"] == recipe["id"])
    assert Decimal(row["cost_per_output_unit"]) == Decimal("11")
    assert row["version"] == 1


def test_recipe_revision_and_retirement(client):
    headers = auth_headers(client)
    _location, ingredient, _output, recipe = seed_recipe(client, headers)
    revised = client.post(f"/api/v1/recipes/{recipe['id']}/revise", headers=headers, json={"name": "Costed Recipe Revised", "yield_quantity": 12, "notes": "Updated formula", "lines": [{"ingredient_item_id": ingredient["id"], "quantity": 6, "waste_factor": 0.05, "optional": False}]})
    assert revised.status_code == 201
    assert revised.json()["recipe"]["version"] == 2
    assert revised.json()["recipe"]["status"] == "draft"
    assert revised.json()["recipe"]["code"].endswith("-V2")

    retired = client.post(f"/api/v1/recipes/{recipe['id']}/retire", headers=headers)
    assert retired.status_code == 200
    assert retired.json()["status"] == "retired"


def test_missing_recipe_costing(client):
    headers = auth_headers(client)
    location = client.post("/api/v1/locations", headers=headers, json={"code": "RCP-MISS", "name": "Missing Recipe Location", "location_type": "kitchen"}).json()
    response = client.get(f"/api/v1/recipes/not-real/costing-detail?location_id={location['id']}", headers=headers)
    assert response.status_code == 404
