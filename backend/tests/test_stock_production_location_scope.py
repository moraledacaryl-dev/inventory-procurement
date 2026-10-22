"""Stock ledger, F&B production and POS read-model authorization contracts.

A scoped operator sees only permitted stock value and cannot mutate a foreign
production batch. Mixed-location stock documents fail closed rather than expose
a misleading redacted subtotal. Service-token POS integration is unchanged.
"""
from decimal import Decimal

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.pass6 import OperationalAccessScope
from app.models.production import PosSaleEvent, Recipe
from app.models.user import User


def auth(client, email="owner@example.com"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def post(client, path, headers, payload):
    response = client.post(path, json=payload, headers=headers)
    assert response.status_code == 201, (path, response.text)
    return response.json()


def seed(client):
    owner = auth(client)
    cat = post(client, "/api/v1/categories", owner, {"name": "Scoped stock+production"})
    unit = post(client, "/api/v1/units", owner, {"code": "SPL", "name": "Scoped production unit"})
    loc_a, loc_b = [
        post(client, "/api/v1/locations", owner, {"code": code, "name": code, "location_type": "kitchen"})["id"]
        for code in ("STKPROD-A", "STKPROD-B")
    ]
    ingredient = post(client, "/api/v1/items", owner, {
        "sku": "STKPROD-ING", "name": "Scoped ingredient", "category_id": cat["id"],
        "base_unit_id": unit["id"], "standard_cost": "20",
    })["id"]
    output = post(client, "/api/v1/items", owner, {
        "sku": "STKPROD-OUT", "name": "Scoped finished stock", "category_id": cat["id"],
        "base_unit_id": unit["id"], "standard_cost": "1",
    })["id"]
    receipts = [
        post(client, "/api/v1/stock/receipts", owner, {
            "location_id": location,
            "lines": [{"item_id": ingredient, "quantity": "100", "unit_cost": "20"}],
            "reference": "Scoped balance seed",
        })
        for location in (loc_a, loc_b)
    ]
    recipe = post(client, "/api/v1/recipes", owner, {
        "code": "SCOPE-RECIPE", "name": "Scoped recipe",
        "output_item_id": output, "yield_quantity": "10",
        "lines": [{"ingredient_item_id": ingredient, "quantity": "5"}],
    })
    with SessionLocal() as db:
        db.get(Recipe, recipe["id"]).status = "approved"
        for email, role in (("scope-produce@example.com", "inventory_manager"),
                            ("scope-view@example.com", "viewer")):
            db.add(User(email=email, full_name=email, password_hash=hash_password("password123"), role=role))
        db.commit()
        manager_id = db.query(User).filter(User.email == "scope-produce@example.com").one().id
        viewer_id = db.query(User).filter(User.email == "scope-view@example.com").one().id
    scope_ids = []
    for user_id in (manager_id, viewer_id):
        scope_ids.append(post(client, "/api/v1/access-scopes", owner, {
            "user_id": user_id, "location_id": loc_a, "approval_limit": "0",
        })["id"])
    batches = [
        post(client, "/api/v1/production-batches", owner, {
            "recipe_id": recipe["id"], "location_id": loc, "planned_quantity": "10",
        })
        for loc in (loc_a, loc_b)
    ]
    mappings = [
        post(client, "/api/v1/pos-mappings", owner, {
            "pos_system": "hidden-oasis-pos", "external_product_id": "SCOPED-MAP-"+suffix,
            "recipe_id": recipe["id"], "location_id": loc,
        })
        for suffix, loc in (("A", loc_a), ("B", loc_b))
    ]
    return {
        "owner": owner,
        "manager": auth(client, "scope-produce@example.com"),
        "viewer": auth(client, "scope-view@example.com"),
        "a": loc_a, "b": loc_b, "ingredient": ingredient, "output": output,
        "recipe": recipe, "receipts": receipts, "batches": batches,
        "mappings": mappings, "scope_ids": scope_ids,
    }


def test_scoped_stock_ledger_and_mixed_location_documents(client):
    setup = seed(client)
    owner, manager = setup["owner"], setup["manager"]
    a, b = setup["a"], setup["b"]
    first, second = setup["receipts"]
    # Mixed transfer adds two movements under one stock document.
    transfer = post(client, "/api/v1/stock/transfers", owner, {
        "source_location_id": a, "destination_location_id": b,
        "lines": [{"item_id": setup["ingredient"], "quantity": "3"}],
    })
    owner_ledger = client.get("/api/v1/stock/ledger", headers=owner)
    scoped_ledger = client.get("/api/v1/stock/ledger", headers=manager)
    assert owner_ledger.status_code == scoped_ledger.status_code == 200
    assert {x["location_id"] for x in owner_ledger.json()["rows"]} == {a, b}
    assert {x["location_id"] for x in scoped_ledger.json()["rows"]} == {a}
    assert Decimal(scoped_ledger.json()["summary"]["net_value"]) != Decimal(
        owner_ledger.json()["summary"]["net_value"]
    )
    assert client.get(f"/api/v1/stock/ledger?location_id={b}", headers=manager).status_code == 403
    assert client.get(f"/api/v1/stock/ledger?location_id={a}", headers=manager).status_code == 200

    assert client.get(f"/api/v1/stock/documents/{first['id']}", headers=manager).status_code == 200
    assert client.get(f"/api/v1/stock/documents/{second['id']}", headers=manager).status_code == 403
    # One allowed line does not entitle the caller to a multi-location document.
    assert client.get(f"/api/v1/stock/documents/{transfer['id']}", headers=manager).status_code == 403
    assert len(client.get(f"/api/v1/stock/documents/{transfer['id']}",
                          headers=owner).json()["lines"]) == 2

    with SessionLocal() as db:
        db.get(OperationalAccessScope, setup["scope_ids"][0]).is_active = False
        db.commit()
    revoked = client.get("/api/v1/stock/ledger", headers=manager)
    assert revoked.status_code == 200 and revoked.json()["rows"] == []
    assert Decimal(revoked.json()["summary"]["net_value"]) == 0
    assert client.get(f"/api/v1/stock/documents/{first['id']}", headers=manager).status_code == 403


def test_production_costing_and_mutation_use_owned_location(client):
    setup = seed(client)
    owner, manager = setup["owner"], setup["manager"]
    a, b = setup["a"], setup["b"]
    batch_a, batch_b = setup["batches"]
    recipe = setup["recipe"]
    for path in (
        f"/api/v1/recipes/{recipe['id']}/cost?location_id={b}",
        f"/api/v1/recipes/{recipe['id']}/costing-detail?location_id={b}",
        f"/api/v1/recipes/costing/workspace?location_id={b}",
        f"/api/v1/production-batches/{batch_b['id']}/execution-detail",
    ):
        r = client.get(path, headers=manager)
        assert r.status_code == 403, (path, r.text)
    assert client.post(f"/api/v1/recipes/{recipe['id']}/margin-scenario",
                       headers=manager, json={"location_id": b, "selling_price": "100"}).status_code == 403
    assert client.get(f"/api/v1/recipes/{recipe['id']}/cost?location_id={a}",
                      headers=manager).status_code == 200
    assert client.get(f"/api/v1/recipes/{recipe['id']}/costing-detail?location_id={a}",
                      headers=manager).status_code == 200
    assert client.get(f"/api/v1/recipes/costing/workspace?location_id={a}",
                      headers=manager).status_code == 200
    assert client.post(f"/api/v1/recipes/{recipe['id']}/margin-scenario",
                       headers=manager, json={"location_id": a, "selling_price": "100"}).status_code == 200

    listed = client.get("/api/v1/production-batches", headers=manager)
    assert listed.status_code == 200
    assert {row["id"] for row in listed.json()} == {batch_a["id"]}
    assert len(client.get("/api/v1/production-batches", headers=owner).json()) == 2
    denied_create = client.post("/api/v1/production-batches", headers=manager, json={
        "recipe_id": recipe["id"], "location_id": b, "planned_quantity": "2",
    })
    assert denied_create.status_code == 403
    for path, payload in (
        (f"/api/v1/production-batches/{batch_b['id']}/start", None),
        (f"/api/v1/production-batches/{batch_b['id']}/complete", {"actual_quantity": "10"}),
        (f"/api/v1/production-batches/{batch_b['id']}/execute", {
            "actual_output_quantity": "10",
            "materials": [{"item_id": setup["ingredient"], "actual_quantity": "5"}],
        }),
        (f"/api/v1/production-batches/{batch_b['id']}/cancel", {"reason": "Not my location"}),
    ):
        response = client.post(path, headers=manager, json=payload)
        assert response.status_code == 403, (path, response.text)
    b_detail = client.get(f"/api/v1/production-batches/{batch_b['id']}/execution-detail",
                          headers=owner)
    assert b_detail.json()["batch"]["status"] == "planned"

    started = client.post(f"/api/v1/production-batches/{batch_a['id']}/start", headers=manager)
    assert started.status_code == 200, started.text
    executed = client.post(f"/api/v1/production-batches/{batch_a['id']}/execute",
                           headers=manager, json={
        "actual_output_quantity": "10",
        "materials": [{"item_id": setup["ingredient"], "actual_quantity": "5"}],
    })
    assert executed.status_code == 200, executed.text
    assert executed.json()["execution"]["batch"]["location_id"] == a
    assert executed.json()["execution"]["batch"]["status"] == "completed"
    assert client.get(f"/api/v1/production-batches/{batch_b['id']}/execution-detail",
                      headers=owner).json()["batch"]["status"] == "planned"


def test_pos_workspace_filters_unattributed_and_foreign_events(client):
    setup = seed(client)
    owner, viewer = setup["owner"], setup["viewer"]
    a_receipt, b_receipt = setup["receipts"]
    with SessionLocal() as db:
        for key, docid in (("A", a_receipt["id"]), ("B", b_receipt["id"]), ("FAILED", None)):
            db.add(PosSaleEvent(
                external_event_id="SCOPED-EVT-"+key,
                external_sale_id="SCOPED-SALE-"+key,
                pos_system="hidden-oasis-pos", event_type="sale_completed",
                payload={}, status="processed" if docid else "failed",
                stock_document_id=docid, error=None if docid else "Unattributed failure",
            ))
        db.commit()
    owner_result = client.get("/api/v1/integrations/pos/workspace", headers=owner)
    limited = client.get("/api/v1/integrations/pos/workspace", headers=viewer)
    assert owner_result.status_code == limited.status_code == 200
    assert owner_result.json()["summary"]["mapping_count"] == 2
    assert limited.json()["summary"]["mapping_count"] == 1
    assert {x["location_id"] for x in limited.json()["mappings"]} == {setup["a"]}
    assert {x["external_event_id"] for x in limited.json()["events"]} == {"SCOPED-EVT-A"}
    assert limited.json()["summary"]["processed_event_count"] == 1
    assert limited.json()["summary"]["failed_event_count"] == 0
    assert owner_result.json()["summary"]["processed_event_count"] == 2
    assert owner_result.json()["summary"]["failed_event_count"] == 1
