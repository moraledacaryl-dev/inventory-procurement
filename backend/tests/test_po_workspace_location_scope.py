"""Protect purchase order detail and quotation workspaces by assigned location."""

from decimal import Decimal

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.pass6 import OperationalAccessScope
from app.models.procurement import PurchaseRequisition
from app.models.user import User


def login(client, email="owner@example.com"):
    result = client.post("/api/v1/auth/login", json={
        "email": email, "password": "password123",
    })
    assert result.status_code == 200, result.text
    return {"Authorization": f"Bearer {result.json()['access_token']}"}


def create(client, endpoint, headers, payload):
    result = client.post(endpoint, json=payload, headers=headers)
    assert result.status_code == 201, (endpoint, result.text)
    return result.json()


def seed(client):
    owner = login(client)
    cat = create(client, "/api/v1/categories", owner, {"name": "PO Scoped"})
    unit = create(client, "/api/v1/units", owner, {"code": "PX", "name": "PO Scope Unit"})
    locations = [
        create(client, "/api/v1/locations", owner, {"code": code, "name": code})["id"]
        for code in ("PO-SCOPE-A", "PO-SCOPE-B")
    ]
    item = create(client, "/api/v1/items", owner, {
        "sku": "PO-SCOPE-ITEM", "name": "Scoped PO item",
        "category_id": cat["id"], "base_unit_id": unit["id"], "standard_cost": "10",
    })
    supplier = create(client, "/api/v1/suppliers", owner, {
        "code": "PO-SCOPE-SUP", "name": "Scoped PO supplier",
    })
    reqs = [
        create(client, "/api/v1/requisitions", owner, {
            "department": "Cafe", "justification": "Buy scoped stock",
            "lines": [{"item_id": item["id"], "quantity": "5", "estimated_unit_cost": "10"}],
        })
        for _ in locations
    ]
    with SessionLocal() as db:
        for req in reqs:
            db.get(PurchaseRequisition, req["id"]).status = "approved"
        for email in ("po-scoped@example.com", "po-unassigned@example.com"):
            db.add(User(email=email, full_name=email, role="procurement_officer",
                        password_hash=hash_password("password123")))
        db.commit()
        user_id = db.query(User).filter(User.email == "po-scoped@example.com").one().id
    scope = create(client, "/api/v1/access-scopes", owner, {
        "user_id": user_id, "location_id": locations[0], "approval_limit": "0",
    })["id"]
    quotes = [
        create(client, "/api/v1/quotations", owner, {
            "requisition_id": req["id"], "supplier_id": supplier["id"],
            "lines": [{"item_id": item["id"], "quantity": "5", "unit_price": "10"}],
        })
        for req in reqs
    ]
    pos = [
        create(client, "/api/v1/purchase-orders", owner, {
            "supplier_id": supplier["id"], "requisition_id": req["id"],
            "quotation_id": quote["id"], "delivery_location_id": loc,
            "lines": [{"item_id": item["id"], "ordered_quantity": "5", "unit_price": "10"}],
        })
        for req, quote, loc in zip(reqs, quotes, locations)
    ]
    return owner, login(client, "po-scoped@example.com"), login(
        client, "po-unassigned@example.com"), locations, item, supplier, reqs, quotes, pos, scope


def test_po_workspace_and_detail_hide_cross_location_financials(client):
    owner, scoped, unassigned, (a, b), _item, _supplier, (req_a, req_b), (q_a, q_b), (po_a, po_b), _scope = seed(client)
    path = "/api/v1/procurement/quotation-workspace"
    limited = client.get(path, headers=scoped)
    assert limited.status_code == 200, limited.text
    limited = limited.json()
    assert {po["delivery_location_id"] for po in limited["purchase_orders"]} == {a}
    assert {req["id"] for req in limited["requisitions"]} == {req_a["id"]}
    assert limited["summary"]["quotations"] == 1
    assert limited["summary"]["approved_requisitions"] == 1
    assert limited["summary"]["open_purchase_orders"] == 1
    assert Decimal(limited["summary"]["open_commitment_value"]) == Decimal("50")
    assert limited["requisitions"][0]["quotations"][0]["id"] == q_a["id"]

    for headers in (owner, unassigned):
        unrestricted = client.get(path, headers=headers)
        assert unrestricted.status_code == 200, unrestricted.text
        data = unrestricted.json()
        assert {po["delivery_location_id"] for po in data["purchase_orders"]} == {a, b}
        assert {req["id"] for req in data["requisitions"]} == {req_a["id"], req_b["id"]}
        assert data["summary"]["quotations"] == 2
        assert Decimal(data["summary"]["open_commitment_value"]) == Decimal("100")

    detail_path = f"/api/v1/purchase-orders/{po_b['id']}/detail"
    assert client.get(detail_path, headers=scoped).status_code == 403
    assert client.get(detail_path, headers=owner).status_code == 200
    assert client.get(f"/api/v1/purchase-orders/{po_a['id']}/detail",
                      headers=scoped).status_code == 200


def test_forbidden_po_amend_and_cancel_do_not_mutate_then_allow_own_location(client):
    owner, scoped, _unassigned, (a, b), item, _supplier, _reqs, _quotes, (po_a, po_b), _scope = seed(client)
    payload = {
        "notes": "Unauthorized change",
        "lines": [{"item_id": item["id"], "ordered_quantity": "1", "unit_price": "100"}],
    }
    forbidden = client.patch(f"/api/v1/purchase-orders/{po_b['id']}/amend",
                             headers=scoped, json=payload)
    assert forbidden.status_code == 403, forbidden.text
    cancelled = client.post(f"/api/v1/purchase-orders/{po_b['id']}/cancel-workspace",
                            headers=scoped)
    assert cancelled.status_code == 403, cancelled.text
    owner_b = client.get(f"/api/v1/purchase-orders/{po_b['id']}/detail", headers=owner).json()
    assert owner_b["purchase_order"]["status"] == "draft"
    assert Decimal(owner_b["summary"]["total"]) == Decimal("50")
    assert owner_b["purchase_order"]["notes"] is None

    amended = client.patch(f"/api/v1/purchase-orders/{po_a['id']}/amend",
                           headers=scoped, json={
        "notes": "Authorized A",
        "lines": [{"item_id": item["id"], "ordered_quantity": "3", "unit_price": "15"}],
    })
    assert amended.status_code == 200, amended.text
    assert Decimal(amended.json()["summary"]["total"]) == Decimal("45")
    assert amended.json()["purchase_order"]["delivery_location_id"] == a
    good_cancel = client.post(f"/api/v1/purchase-orders/{po_a['id']}/cancel-workspace",
                              headers=scoped)
    assert good_cancel.status_code == 200, good_cancel.text
    assert good_cancel.json()["purchase_order"]["status"] == "cancelled"
    assert client.get(f"/api/v1/purchase-orders/{po_b['id']}/detail",
                      headers=owner).json()["purchase_order"]["status"] == "draft"


def test_award_destination_must_be_in_scope_and_disabled_scope_fails_closed(client):
    owner, scoped, _unassigned, (a, b), item, supplier, _reqs, _quotes, (po_a, po_b), scope_id = seed(client)
    req = create(client, "/api/v1/requisitions", owner, {
        "department": "Cafe", "lines": [{"item_id": item["id"], "quantity": "2"}],
    })
    with SessionLocal() as db:
        db.get(PurchaseRequisition, req["id"]).status = "approved"
        db.commit()
    quote = create(client, "/api/v1/quotations", owner, {
        "requisition_id": req["id"], "supplier_id": supplier["id"],
        "lines": [{"item_id": item["id"], "quantity": "2", "unit_price": "10"}],
    })
    url = f"/api/v1/requisitions/{req['id']}/award-quotation"
    before = len(client.get("/api/v1/purchase-orders", headers=owner).json())
    denied = client.post(url, headers=scoped, json={
        "quotation_id": quote["id"], "delivery_location_id": b,
    })
    assert denied.status_code == 403, denied.text
    assert len(client.get("/api/v1/purchase-orders", headers=owner).json()) == before

    with SessionLocal() as db:
        db.get(OperationalAccessScope, scope_id).is_active = False
        db.commit()
    workspace = client.get("/api/v1/procurement/quotation-workspace", headers=scoped)
    assert workspace.status_code == 200, workspace.text
    assert workspace.json()["requisitions"] == []
    assert workspace.json()["purchase_orders"] == []
    assert workspace.json()["summary"]["open_commitment_value"] in ("0", "0.0000")
    for po in (po_a, po_b):
        assert client.get(f"/api/v1/purchase-orders/{po['id']}/detail",
                          headers=scoped).status_code == 403
        assert client.post(f"/api/v1/purchase-orders/{po['id']}/cancel-workspace",
                           headers=scoped).status_code == 403
    assert client.post(url, headers=scoped, json={
        "quotation_id": quote["id"], "delivery_location_id": a,
    }).status_code == 403
    assert len(client.get("/api/v1/purchase-orders", headers=owner).json()) == before
