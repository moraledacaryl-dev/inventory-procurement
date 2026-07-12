def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def get_by_code(rows, code):
    return next(row for row in rows if row["code"] == code)


def ensure_category_and_unit(client, headers):
    categories = client.get("/api/v1/categories", headers=headers).json()
    if categories:
        category = categories[0]
    else:
        created = client.post("/api/v1/categories", headers=headers, json={"name": "Test category", "sort_order": 10})
        assert created.status_code == 201
        category = created.json()
    units = client.get("/api/v1/units", headers=headers).json()
    if units:
        unit = units[0]
    else:
        created = client.post("/api/v1/units", headers=headers, json={"code": "EA", "name": "Each", "precision": 0})
        assert created.status_code == 201
        unit = created.json()
    return category, unit


def test_classification_bootstrap_exposes_editable_defaults(client):
    headers = auth_headers(client)
    response = client.get("/api/v1/classification/bootstrap", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert {row["code"] for row in payload["dimensions"]["workspace"]} >= {"fnb", "hotel", "assets-property", "shared-operations"}
    assert {row["code"] for row in payload["dimensions"]["record_class"]} >= {"consumable", "reusable-property", "fixed-asset", "service-expense"}
    ingredient = get_by_code(payload["dimensions"]["item_type"], "ingredient")
    assert ingredient["parent_id"]
    assert ingredient["workspace_id"]
    assert ingredient["behavior_key"] == "ingredient"


def test_item_type_derives_record_class_without_recipe_checkbox(client):
    headers = auth_headers(client)
    structure = client.get("/api/v1/classification/bootstrap", headers=headers).json()["dimensions"]
    fnb = get_by_code(structure["workspace"], "fnb")
    ingredient = get_by_code(structure["item_type"], "ingredient")
    category, unit = ensure_category_and_unit(client, headers)
    response = client.post(
        "/api/v1/items",
        headers=headers,
        json={
            "sku": "PASS1-INGREDIENT",
            "name": "Pass 1 ingredient",
            "category_id": category["id"],
            "base_unit_id": unit["id"],
            "primary_workspace_id": fnb["id"],
            "item_type_id": ingredient["id"],
            "minimum_stock": 0,
            "standard_cost": 0,
        },
    )
    assert response.status_code == 201
    item = response.json()
    assert item["primary_workspace_id"] == fnb["id"]
    assert item["item_type_id"] == ingredient["id"]
    assert item["record_class_id"] == ingredient["parent_id"]
    assert "recipe_eligible" not in item

    scoped = client.get(f"/api/v1/items?workspace_id={fnb['id']}", headers=headers)
    assert scoped.status_code == 200
    assert any(row["id"] == item["id"] for row in scoped.json())


def test_item_type_rejects_wrong_workspace(client):
    headers = auth_headers(client)
    structure = client.get("/api/v1/classification/bootstrap", headers=headers).json()["dimensions"]
    hotel = get_by_code(structure["workspace"], "hotel")
    ingredient = get_by_code(structure["item_type"], "ingredient")
    category, unit = ensure_category_and_unit(client, headers)
    response = client.post(
        "/api/v1/items",
        headers=headers,
        json={
            "sku": "PASS1-WRONG-SCOPE",
            "name": "Wrong scope",
            "category_id": category["id"],
            "base_unit_id": unit["id"],
            "primary_workspace_id": hotel["id"],
            "item_type_id": ingredient["id"],
        },
    )
    assert response.status_code == 422


def test_visible_system_names_are_editable_but_behavior_is_protected(client):
    headers = auth_headers(client)
    rows = client.get("/api/v1/classification/dimensions?dimension_type=workspace", headers=headers).json()
    fnb = get_by_code(rows, "fnb")
    renamed = client.patch(f"/api/v1/classification/dimensions/{fnb['id']}", headers=headers, json={"name": "Food & Beverage"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Food & Beverage"

    protected = client.patch(f"/api/v1/classification/dimensions/{fnb['id']}", headers=headers, json={"behavior_key": "hotel"})
    assert protected.status_code == 409
