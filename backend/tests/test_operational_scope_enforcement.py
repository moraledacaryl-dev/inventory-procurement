"""Authoritative controls for physical stock locations and monetary approvals."""

from decimal import Decimal

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.pass6 import OperationalAccessScope
from app.models.procurement import PurchaseOrder, PurchaseRequisition
from app.models.inventory import StockDocument, StockBalance
from app.models.user import User


def headers(client, email="owner@example.com"):
    result = client.post("/api/v1/auth/login", json={
        "email": email, "password": "password123",
    })
    assert result.status_code == 200, result.text
    return {"Authorization": f"Bearer {result.json()['access_token']}"}


def setup(client):
    owner = headers(client)
    category = client.post("/api/v1/categories", headers=owner, json={
        "name": "Scope tests",
    }).json()
    unit = client.post("/api/v1/units", headers=owner, json={
        "code": "EACH", "name": "Each",
    }).json()
    locations = []
    for code in ("SCOPE-A", "SCOPE-B"):
        response = client.post("/api/v1/locations", headers=owner, json={
            "code": code, "name": code,
        })
        assert response.status_code == 201, response.text
        locations.append(response.json())
    item = client.post("/api/v1/items", headers=owner, json={
        "sku": "SCOPE-ITEM", "name": "Scoped goods",
        "category_id": category["id"], "base_unit_id": unit["id"],
        "standard_cost": "20",
    }).json()
    supplier = client.post("/api/v1/suppliers", headers=owner, json={
        "code": "SCOPE-SUP", "name": "Scope Supplier",
    }).json()
    with SessionLocal() as db:
        db.add_all([
            User(email="scoped-manager@example.com", full_name="Scoped Manager",
                 role="inventory_manager", password_hash=hash_password("password123")),
            User(email="scoped-procurement@example.com", full_name="Scoped Procurement",
                 role="procurement_officer", password_hash=hash_password("password123")),
        ])
        db.commit()
        ids = {u.email: u.id for u in db.query(User).all()}
    return owner, headers(client, "scoped-manager@example.com"), headers(client, "scoped-procurement@example.com"), locations, item, supplier, ids


def create_scope(client, owner, user_id, **values):
    response = client.post("/api/v1/access-scopes", headers=owner, json={
        "user_id": user_id, **values,
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_posting_enforces_active_location_scope_for_all_stock_document_kinds(client):
    owner, manager, _buyer, (a, b), item, _supplier, ids = setup(client)
    manager_id = ids["scoped-manager@example.com"]
    scope = create_scope(client, owner, manager_id, location_id=a["id"])

    receipt_a = client.post("/api/v1/stock/receipts", headers=manager, json={
        "location_id": a["id"],
        "lines": [{"item_id": item["id"], "quantity": "10", "unit_cost": "20"}],
    })
    assert receipt_a.status_code == 201, receipt_a.text

    denied_receipt = client.post("/api/v1/stock/receipts", headers=manager, json={
        "location_id": b["id"],
        "lines": [{"item_id": item["id"], "quantity": "8", "unit_cost": "20"}],
    })
    assert denied_receipt.status_code == 403
    denied_transfer = client.post("/api/v1/stock/transfers", headers=manager, json={
        "source_location_id": a["id"], "destination_location_id": b["id"],
        "lines": [{"item_id": item["id"], "quantity": "2"}],
    })
    assert denied_transfer.status_code == 403
    denied_adjustment = client.post("/api/v1/stock/adjustments", headers=manager, json={
        "location_id": b["id"],
        "lines": [{"item_id": item["id"], "quantity_delta": "2",
                   "unit_cost": "20", "reason": "stock correction"}],
    })
    assert denied_adjustment.status_code == 403

    with SessionLocal() as db:
        balances = {(x.item_id, x.location_id): Decimal(x.quantity)
                    for x in db.query(StockBalance).all()}
        assert balances == {(item["id"], a["id"]): Decimal("10")}
        assert db.query(StockDocument).count() == 1
        db.get(OperationalAccessScope, scope["id"]).is_active = False
        db.commit()

    denied_inactive = client.post("/api/v1/stock/issues", headers=manager, json={
        "location_id": a["id"],
        "lines": [{"item_id": item["id"], "quantity": "1"}],
    })
    assert denied_inactive.status_code == 403

    owner_receipt = client.post("/api/v1/stock/receipts", headers=owner, json={
        "location_id": b["id"],
        "lines": [{"item_id": item["id"], "quantity": "1", "unit_cost": "20"}],
    })
    assert owner_receipt.status_code == 201


def test_unconfigured_location_scopes_preserve_legacy_role_operation(client):
    owner, manager, _buyer, (_a, b), item, _supplier, _ids = setup(client)
    response = client.post("/api/v1/stock/receipts", headers=manager, json={
        "location_id": b["id"],
        "lines": [{"item_id": item["id"], "quantity": "1", "unit_cost": "20"}],
    })
    assert response.status_code == 201, response.text


def test_procurement_approvals_require_active_limit_and_correct_location(client):
    owner, _manager, buyer, (a, b), item, supplier, ids = setup(client)
    buyer_id = ids["scoped-procurement@example.com"]

    req = client.post("/api/v1/requisitions", headers=owner, json={
        "department": "Cafe",
        "lines": [{"item_id": item["id"], "quantity": "2",
                   "estimated_unit_cost": "40"}],
    })
    assert req.status_code == 201
    req_id = req.json()["id"]
    endpoint = f"/api/v1/requisitions/{req_id}/approve"

    assert client.post(endpoint, headers=buyer).status_code == 403
    global_scope = create_scope(client, owner, buyer_id, approval_limit="79")
    assert client.post(endpoint, headers=buyer).status_code == 403

    with SessionLocal() as db:
        scope = db.get(OperationalAccessScope, global_scope["id"])
        scope.approval_limit = Decimal("80")
        db.commit()
    approved_req = client.post(endpoint, headers=buyer)
    assert approved_req.status_code == 200, approved_req.text

    po = client.post("/api/v1/purchase-orders", headers=owner, json={
        "supplier_id": supplier["id"],
        "requisition_id": req_id,
        "delivery_location_id": a["id"],
        "lines": [{"item_id": item["id"], "ordered_quantity": "2",
                   "unit_price": "35"}],
    })
    assert po.status_code == 201, po.text
    po_id = po.json()["id"]
    po_endpoint = f"/api/v1/purchase-orders/{po_id}/approve"

    with SessionLocal() as db:
        scope = db.get(OperationalAccessScope, global_scope["id"])
        scope.location_id = b["id"]
        db.commit()
    assert client.post(po_endpoint, headers=buyer).status_code == 403
    with SessionLocal() as db:
        scope = db.get(OperationalAccessScope, global_scope["id"])
        scope.location_id = a["id"]
        scope.approval_limit = Decimal("69")
        db.commit()
    assert client.post(po_endpoint, headers=buyer).status_code == 403
    with SessionLocal() as db:
        scope = db.get(OperationalAccessScope, global_scope["id"])
        scope.approval_limit = Decimal("70")
        db.commit()
    approved_po = client.post(po_endpoint, headers=buyer)
    assert approved_po.status_code == 200, approved_po.text
    assert approved_po.json()["status"] == "approved"
    with SessionLocal() as db:
        row = db.get(PurchaseOrder, po_id)
        assert row.approved_by_user_id == buyer_id
        assert db.get(PurchaseRequisition, req_id).approved_by_user_id == buyer_id


def test_inactive_and_dimensional_scopes_cannot_grant_global_approval(client):
    owner, _manager, buyer, (a, _b), item, _supplier, ids = setup(client)
    req = client.post("/api/v1/requisitions", headers=owner, json={
        "department": "Cafe",
        "lines": [{"item_id": item["id"], "quantity": "1",
                   "estimated_unit_cost": "20"}],
    }).json()
    buyer_id = ids["scoped-procurement@example.com"]
    scope = create_scope(client, owner, buyer_id, location_id=a["id"],
                         approval_limit="999", is_active=False)
    endpoint = f"/api/v1/requisitions/{req['id']}/approve"
    assert client.post(endpoint, headers=buyer).status_code == 403
    with SessionLocal() as db:
        db.get(OperationalAccessScope, scope["id"]).is_active = True
        db.commit()
    # A location-limited scope cannot approve an unlocated requisition.
    assert client.post(endpoint, headers=buyer).status_code == 403



def test_scoped_item_detail_aggregates_only_authorized_locations(client):
    owner, manager, _buyer, (a, b), item, supplier, ids = setup(client)
    scope = create_scope(client, owner, ids["scoped-manager@example.com"], location_id=a["id"])

    for loc, qty, unit_cost in ((a, "4", "20"), (b, "7", "40")):
        result = client.post("/api/v1/stock/receipts", headers=owner, json={
            "location_id": loc["id"],
            "lines": [{"item_id": item["id"], "quantity": qty, "unit_cost": unit_cost}],
        })
        assert result.status_code == 201, result.text
        setting = client.post("/api/v1/item-location-settings", headers=owner, json={
            "item_id": item["id"], "location_id": loc["id"],
            "minimum_stock": "1", "reorder_quantity": "2",
        })
        assert setting.status_code == 201, setting.text

    supplier_item = client.post(f"/api/v1/suppliers/{supplier['id']}/items",
                                headers=owner, json={
                                    "item_id": item["id"], "last_price": "99",
                                })
    assert supplier_item.status_code == 201, supplier_item.text

    detail = client.get(f"/api/v1/items/{item['id']}", headers=manager)
    assert detail.status_code == 200, detail.text
    scoped = detail.json()
    assert {x["location_id"] for x in scoped["balances"]} == {a["id"]}
    assert {x["location_id"] for x in scoped["recent_movements"]} == {a["id"]}
    assert Decimal(str(scoped["totals"]["quantity"])) == Decimal("4")
    assert Decimal(str(scoped["totals"]["inventory_value"])) == Decimal("80")
    assert scoped["totals"]["movement_count"] == 1
    assert scoped["totals"]["location_count"] == 1

    unrestricted = client.get(f"/api/v1/items/{item['id']}", headers=owner).json()
    assert {x["location_id"] for x in unrestricted["balances"]} == {a["id"], b["id"]}
    assert Decimal(str(unrestricted["totals"]["quantity"])) == Decimal("11")
    assert Decimal(str(unrestricted["totals"]["inventory_value"])) == Decimal("360")
    assert unrestricted["totals"]["movement_count"] == 2

    configuration = client.get(
        f"/api/v1/items/{item['id']}/configuration", headers=manager,
    )
    assert configuration.status_code == 200, configuration.text
    assert {x["location_id"] for x in configuration.json()["location_settings"]} == {a["id"]}
    assert configuration.json()["supplier_items"] == []
    full_config = client.get(
        f"/api/v1/items/{item['id']}/configuration", headers=owner,
    ).json()
    assert {x["location_id"] for x in full_config["location_settings"]} == {a["id"], b["id"]}
    assert Decimal(full_config["supplier_items"][0]["last_price"]) == Decimal("99")
    assert client.get(
        f"/api/v1/suppliers/{supplier['id']}/items", headers=manager,
    ).status_code == 403
    assert client.get(
        f"/api/v1/suppliers/{supplier['id']}/items", headers=owner,
    ).status_code == 200

    with SessionLocal() as db:
        db.get(OperationalAccessScope, scope["id"]).is_active = False
        db.commit()
    detail = client.get(f"/api/v1/items/{item['id']}", headers=manager).json()
    assert detail["balances"] == []
    assert detail["recent_movements"] == []
    assert Decimal(str(detail["totals"]["quantity"])) == 0
    assert Decimal(str(detail["totals"]["inventory_value"])) == 0
    assert detail["totals"]["movement_count"] == 0
    cfg = client.get(f"/api/v1/items/{item['id']}/configuration", headers=manager).json()
    assert cfg["location_settings"] == []
    assert cfg["supplier_items"] == []


def test_explicit_location_scope_rejects_global_catalogue_mutations(client):
    owner, manager, _buyer, (a, b), item, _supplier, ids = setup(client)
    scope = create_scope(client, owner, ids["scoped-manager@example.com"], location_id=a["id"])
    new_item = {
        "sku": "DENIED-NEW-ITEM", "name": "Denied Item",
        "category_id": item["category_id"], "base_unit_id": item["base_unit_id"],
        "standard_cost": "10",
    }
    expected_denied = [
        ("post", "/api/v1/categories", {"name": "Denied category"}),
        ("post", "/api/v1/units", {"code": "BADUNIT", "name": "Denied unit"}),
        ("post", "/api/v1/locations", {"code": "BADLOC", "name": "Denied location"}),
        ("post", "/api/v1/items", new_item),
        ("patch", f"/api/v1/items/{item['id']}", {"name": "Tampered item"}),
        ("post", "/api/v1/classification/dimensions", {
            "dimension_type": "department", "code": "denied", "name": "Denied department",
        }),
        ("patch", "/api/v1/classification/dimensions/not-a-real-id", {"name": "Denied"}),
        ("patch", f"/api/v1/classification/items/{item['id']}", {}),
        ("post", "/api/v1/classification/items/bulk-assign", {
            "lines": [{"item_id": item["id"]}],
        }),
        ("post", f"/api/v1/items/{item['id']}/barcodes", {
            "barcode": "DENIED-BARCODE-123",
        }),
        ("post", f"/api/v1/items/{item['id']}/conversions", {
            "from_unit_id": item["base_unit_id"],
            "to_unit_id": item["base_unit_id"], "multiplier": "2",
        }),
    ]
    for method, route, payload in expected_denied:
        response = getattr(client, method)(route, headers=manager, json=payload)
        assert response.status_code == 403, (method, route, response.text)

    with SessionLocal() as db:
        unchanged_item = db.get(__import__("app.models.inventory", fromlist=["Item"]).Item, item["id"])
        assert unchanged_item.name == "Scoped goods"

    # Role permissions still allow a legacy account without configured scope.
    with SessionLocal() as db:
        db.get(OperationalAccessScope, scope["id"]).is_active = False
        db.commit()
    assert client.post("/api/v1/categories", headers=manager, json={
        "name": "Still denied when revoked",
    }).status_code == 403
    with SessionLocal() as db:
        db.delete(db.get(OperationalAccessScope, scope["id"]))
        db.commit()
    assert client.post("/api/v1/categories", headers=manager, json={
        "name": "Legacy category",
    }).status_code == 201
    assert client.post("/api/v1/items", headers=manager, json=new_item).status_code == 201
    assert client.patch(f"/api/v1/items/{item['id']}", headers=manager,
                        json={"name": "Authorized legacy edit"}).status_code == 200
    assert client.post("/api/v1/categories", headers=owner, json={
        "name": "Owner category",
    }).status_code == 201


def test_explicit_location_scope_rejects_global_menu_and_pos_rule_mutations(client):
    owner, manager, _buyer, (a, _b), item, _supplier, ids = setup(client)
    create_scope(client, owner, ids["scoped-manager@example.com"], location_id=a["id"])
    menu = {"name": "Scope Latte", "category": "Coffee",
            "variants": [{"name": "Regular", "price": "100"}]}
    rule = {"name": "Scope combo", "qualifier_tag": "combo", "target_tag": "target"}
    modifier = {"name": "Scope add-on", "group": {
        "id": "addons", "label": "Add-ons", "mode": "multi",
        "options": [{"label": "Pearl", "price_delta": 20}],
    }}
    item_created = client.post("/api/v1/fnb/menu", headers=owner, json=menu)
    rule_created = client.post("/api/v1/fnb/pos-rules/pricing",
                               headers=owner, json=rule)
    modifier_created = client.post("/api/v1/fnb/pos-rules/modifiers",
                                   headers=owner, json=modifier)
    assert item_created.status_code == 201, item_created.text
    assert rule_created.status_code == 201, rule_created.text
    assert modifier_created.status_code == 201, modifier_created.text

    blocked = [
        ("post", "/api/v1/fnb/menu", menu),
        ("put", f"/api/v1/fnb/menu/{item_created.json()['id']}", menu),
        ("post", "/api/v1/fnb/pos-rules/pricing", rule),
        ("put", f"/api/v1/fnb/pos-rules/pricing/{rule_created.json()['id']}", rule),
        ("post", "/api/v1/fnb/pos-rules/modifiers", modifier),
        ("put", f"/api/v1/fnb/pos-rules/modifiers/{modifier_created.json()['id']}", modifier),
    ]
    for method, route, payload in blocked:
        response = getattr(client, method)(route, headers=manager, json=payload)
        assert response.status_code == 403, (method, route, response.text)

    assert client.get("/api/v1/fnb/menu", headers=manager).status_code == 200
    assert client.get("/api/v1/fnb/pos-rules", headers=manager).status_code == 200
    with SessionLocal() as db:
        from app.models.menu import MenuItem
        from app.models.pos_rules import PosModifierTemplate, PosPricingRule
        assert db.query(MenuItem).count() == 1
        assert db.query(PosPricingRule).count() == 1
        assert db.query(PosModifierTemplate).count() == 1
        assert db.query(PosPricingRule).first().name == "Scope combo"
