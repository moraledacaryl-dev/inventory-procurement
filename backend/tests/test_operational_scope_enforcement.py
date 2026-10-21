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
    if response.status_code == 500:
        # Expose the server exception in CI; HTTP middleware intentionally masks
        # details from clients.
        from app.api.routes.pass6_controls import ScopeIn, set_access_scope
        with SessionLocal() as db:
            actor = db.query(User).filter(User.email == "owner@example.com").first()
            set_access_scope(ScopeIn(user_id=user_id, **values), db, actor)
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
