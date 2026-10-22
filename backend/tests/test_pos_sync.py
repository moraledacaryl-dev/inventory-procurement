from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.operations import IntegrationEvent
from app.models.production import Recipe


POS_TOKEN = "test-hidden-oasis-pos-token"


def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def pos_headers():
    settings.pos_integration_token = POS_TOKEN
    return {"X-Integration-Token": POS_TOKEN}


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


def test_pos_event_requires_machine_credential(client):
    headers = auth_headers(client)
    seed_mapping(client, headers)
    settings.pos_integration_token = POS_TOKEN
    event = {"external_event_id": "evt-auth", "external_sale_id": "sale-auth", "pos_system": "hidden-oasis-pos", "event_type": "sale_completed", "lines": [{"external_product_id": "CAFE-001", "quantity": 1}]}

    missing = client.post("/api/v1/integrations/pos/events", json=event)
    assert missing.status_code == 401
    wrong = client.post("/api/v1/integrations/pos/events", headers={"X-Integration-Token": "wrong-token"}, json=event)
    assert wrong.status_code == 401


def test_pos_event_idempotency_and_reversal(client):
    headers = auth_headers(client)
    location, ingredient, _recipe, _mapping = seed_mapping(client, headers)
    integration_headers = pos_headers()
    event = {"external_event_id": "evt-001", "external_sale_id": "sale-001", "pos_system": "hidden-oasis-pos", "event_type": "sale_completed", "lines": [{"external_product_id": "CAFE-001", "quantity": 2}]}
    first = client.post("/api/v1/integrations/pos/events", headers=integration_headers, json=event)
    assert first.status_code == 201
    duplicate = client.post("/api/v1/integrations/pos/events", headers=integration_headers, json=event)
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == first.json()["id"]
    numeric_equivalent = client.post(
        "/api/v1/integrations/pos/events", headers=integration_headers,
        json={**event, "lines": [{"external_product_id": "CAFE-001", "quantity": "2.000"}]},
    )
    assert numeric_equivalent.status_code == 201
    assert numeric_equivalent.json()["id"] == first.json()["id"]

    # Conflicting retries must never masquerade as successful idempotent
    # delivery: the original stock effect is authoritative.
    for changed in (
        {**event, "lines": [{"external_product_id": "CAFE-001", "quantity": 3}]},
        {**event, "external_sale_id": "another-sale"},
        {**event, "event_type": "sale_voided"},
    ):
        conflict = client.post("/api/v1/integrations/pos/events", headers=integration_headers, json=changed)
        assert conflict.status_code == 409
        assert "different event" in conflict.json()["detail"]

    replayed_sale = client.post(
        "/api/v1/integrations/pos/events",
        headers=integration_headers,
        json={**event, "external_event_id": "evt-001-replay"},
    )
    assert replayed_sale.status_code == 409
    after_sale = client.get(f"/api/v1/stock/balances?item_id={ingredient['id']}&location_id={location['id']}", headers=headers).json()[0]
    assert Decimal(after_sale["quantity"]) == Decimal("96")

    with SessionLocal() as db:
        sale_event = db.scalar(select(IntegrationEvent).where(IntegrationEvent.event_type == "inventory.pos_sale_consumed"))
        assert sale_event is not None
        assert Decimal(sale_event.payload["total_cost"]) == Decimal("20")
        assert len(sale_event.payload["lines"]) == 1
        original_stock_document_id = sale_event.payload["stock_document_id"]

    reversal = client.post("/api/v1/integrations/pos/events", headers=integration_headers, json={**event, "external_event_id": "evt-002", "event_type": "sale_refunded"})
    assert reversal.status_code == 201
    assert reversal.json()["reversal_of_event_id"] == first.json()["id"]
    same_reversal = client.post(
        "/api/v1/integrations/pos/events", headers=integration_headers,
        json={**event, "external_event_id": "evt-002", "event_type": "sale_refunded"},
    )
    assert same_reversal.status_code == 201
    assert same_reversal.json()["id"] == reversal.json()["id"]
    changed_reversal = client.post(
        "/api/v1/integrations/pos/events", headers=integration_headers,
        json={**event, "external_event_id": "evt-002", "event_type": "sale_voided"},
    )
    assert changed_reversal.status_code == 409

    with SessionLocal() as db:
        reversal_event = db.scalar(select(IntegrationEvent).where(IntegrationEvent.event_type == "inventory.pos_sale_reversed"))
        assert reversal_event is not None
        assert Decimal(reversal_event.payload["total_cost"]) == Decimal("20")
        assert reversal_event.payload["reverses_stock_document_id"] == original_stock_document_id
        assert reversal_event.payload["event_type"] == "sale_refunded"

    second_reversal = client.post(
        "/api/v1/integrations/pos/events",
        headers=integration_headers,
        json={**event, "external_event_id": "evt-003", "event_type": "sale_voided"},
    )
    assert second_reversal.status_code == 409
    after_reversal = client.get(f"/api/v1/stock/balances?item_id={ingredient['id']}&location_id={location['id']}", headers=headers).json()[0]
    assert Decimal(after_reversal["quantity"]) == Decimal("100")

    workspace = client.get("/api/v1/integrations/pos/workspace", headers=headers)
    assert workspace.status_code == 200
    assert workspace.json()["summary"]["processed_event_count"] >= 2


def test_pos_catalog_feed_requires_machine_credential_and_returns_menu_variants(client):
    headers = auth_headers(client)
    payload = {
        "name": "Catalog Test Drink",
        "category": "Test Drinks",
        "prep_station": "bar",
        "is_active": True,
        "pos_visible": True,
        "variants": [{"name": "Regular", "sku": "CAT-TEST-001", "barcode": "209999999999", "price": "125.00", "with_drink_price": None, "is_active": True}],
    }
    created = client.post("/api/v1/fnb/menu", headers=headers, json=payload)
    assert created.status_code == 201

    settings.pos_integration_token = POS_TOKEN
    missing = client.get("/api/v1/integrations/pos/catalog")
    assert missing.status_code == 401
    response = client.get("/api/v1/integrations/pos/catalog", headers=pos_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "inventory-procurement"
    row = next(item for item in body["items"] if item["sku"] == "CAT-TEST-001")
    assert row["menu_item_id"] == created.json()["id"]
    assert row["variant_id"] == created.json()["variants"][0]["id"]
    assert row["price"] == "125.00"
    assert row["prep_station"] == "bar"
    assert row["is_active"] is True
