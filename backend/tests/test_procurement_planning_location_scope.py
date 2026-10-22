"""Security regression: procurement planning and valuation are location-scoped.

Uses real authenticated HTTP routes, real purchase orders and receipts; a user
assigned to location A must not see or change location B, including in totals.
"""

from decimal import Decimal

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.pass6 import OperationalAccessScope
from app.models.procurement import PurchaseOrder
from app.models.user import User


def login(client, email="owner@example.com"):
    response = client.post("/api/v1/auth/login", json={
        "email": email, "password": "password123",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create(client, path, headers, data):
    result = client.post(path, headers=headers, json=data)
    assert result.status_code == 201, (path, result.text)
    return result.json()


def seed(client):
    owner = login(client)
    cat = create(client, "/api/v1/categories", owner, {"name": "Scoped procurement"})
    unit = create(client, "/api/v1/units", owner, {"code": "PS", "name": "Procurement unit"})
    locations = [
        create(client, "/api/v1/locations", owner, {"code": code, "name": code})["id"]
        for code in ("PLAN-SCOPE-A", "PLAN-SCOPE-B")
    ]
    item = create(client, "/api/v1/items", owner, {
        "sku": "PLAN-SCOPE-ITEM", "name": "Procurement scope goods",
        "category_id": cat["id"], "base_unit_id": unit["id"],
        "standard_cost": "20", "minimum_stock": "10",
    })
    supplier = create(client, "/api/v1/suppliers", owner, {
        "code": "PLAN-SCOPE-SUP", "name": "Scoped Procurement Supplier",
    })
    pos = [
        create(client, "/api/v1/purchase-orders", owner, {
            "supplier_id": supplier["id"], "delivery_location_id": loc,
            "lines": [{"item_id": item["id"], "ordered_quantity": "4", "unit_price": "25"}],
        })
        for loc in locations
    ]
    with SessionLocal() as db:
        for po in pos:
            db.get(PurchaseOrder, po["id"]).status = "approved"
        for email in ("planning-scoped@example.com", "planning-unassigned@example.com"):
            db.add(User(email=email, full_name=email, role="procurement_officer",
                        password_hash=hash_password("password123")))
        db.commit()
        scoped_user = db.query(User).filter(User.email == "planning-scoped@example.com").one()
        scoped_id = scoped_user.id
    scope = create(client, "/api/v1/access-scopes", owner, {
        "user_id": scoped_id, "location_id": locations[0], "approval_limit": "0",
    })["id"]
    for idx, po in enumerate(pos):
        posted = client.post(f"/api/v1/receiving/purchase-orders/{po['id']}",
                             headers=owner, json={
            "delivery_reference": f"PLAN-SCOPE-DR-{idx}",
            "lines": [{"purchase_order_line_id": po["lines"][0]["id"],
                       "received_quantity": "2", "accepted_quantity": "2",
                       "rejected_quantity": "0"}],
        })
        assert posted.status_code == 201, posted.text
    return (owner, login(client, "planning-scoped@example.com"),
            login(client, "planning-unassigned@example.com"),
            locations, item, supplier, pos, scope)


def test_planning_read_and_financial_summary_restrict_assigned_locations(client):
    owner, scoped, unassigned, (a, b), _item, supplier, _pos, _scope = seed(client)
    path = "/api/v1/procurement/planning"
    filtered = client.get(path, headers=scoped)
    assert filtered.status_code == 200, filtered.text
    assert {row["location_id"] for row in filtered.json()["rows"]} == {a}
    assert filtered.json()["summary"]["suggestion_count"] == 1
    assert filtered.json()["summary"]["estimated_value"] == "120.0000" or Decimal(filtered.json()["summary"]["estimated_value"]) == Decimal("120")
    assert client.get(f"{path}?location_id={b}", headers=scoped).status_code == 403
    assert {row["location_id"] for row in client.get(path, headers=owner).json()["rows"]} == {a, b}
    assert {row["location_id"] for row in client.get(path, headers=unassigned).json()["rows"]} == {a, b}

    for endpoint in ("/api/v1/reorder-suggestions", "/api/v1/procurement/planning"):
        assert client.get(f"{endpoint}?location_id={b}", headers=scoped).status_code == 403
    reorder = client.get("/api/v1/reorder-suggestions", headers=scoped)
    assert reorder.status_code == 200, reorder.text
    assert {row["location_id"] for row in reorder.json()} == {a}
    assert {row["location_id"] for row in client.get(
        "/api/v1/reorder-suggestions", headers=unassigned).json()
        if row["location_id"] is not None} == set()

    # Supplier statistics must be recomputed from scoped POs and receipts, not
    # globally aggregated then stripped of location identifiers.
    scoped_report = client.get("/api/v1/supplier-performance", headers=scoped)
    owner_report = client.get("/api/v1/supplier-performance", headers=owner)
    assert scoped_report.status_code == 200, scoped_report.text
    scoped_supplier = next(x for x in scoped_report.json() if x["supplier_id"] == supplier["id"])
    all_supplier = next(x for x in owner_report.json() if x["supplier_id"] == supplier["id"])
    assert scoped_supplier["purchase_orders"] == 1
    assert all_supplier["purchase_orders"] == 2
    assert Decimal(scoped_supplier["ordered_value"]) == Decimal("100")
    assert Decimal(all_supplier["ordered_value"]) == Decimal("200")
    assert Decimal(scoped_supplier["accepted_value"]) == Decimal("50")
    assert Decimal(all_supplier["accepted_value"]) == Decimal("100")


def test_planned_and_automatic_requisitions_block_cross_location_writes(client):
    owner, scoped, _unassigned, (a, b), item, _supplier, _pos, _scope = seed(client)
    before = len(client.get("/api/v1/requisitions", headers=owner).json())
    payload = {
        "department": "Cafe", "location_id": b,
        "justification": "Restock store",
        "lines": [{"item_id": item["id"], "quantity": "3", "estimated_unit_cost": "20"}],
    }
    denied = client.post("/api/v1/procurement/planning/requisitions", headers=scoped, json=payload)
    assert denied.status_code == 403, denied.text
    assert len(client.get("/api/v1/requisitions", headers=owner).json()) == before
    good = create(client, "/api/v1/procurement/planning/requisitions", scoped, {
        **payload, "location_id": a,
    })
    assert good["status"] == "submitted"

    reorder_base = {"department": "Cafe", "item_ids": [item["id"]]}
    for forbidden in (reorder_base, {**reorder_base, "location_id": b}):
        response = client.post("/api/v1/reorder-suggestions/requisition",
                               headers=scoped, json=forbidden)
        assert response.status_code == 403, response.text
    assert len(client.get("/api/v1/requisitions", headers=owner).json()) == before + 1
    allowed = create(client, "/api/v1/reorder-suggestions/requisition", scoped, {
        **reorder_base, "location_id": a,
    })
    assert allowed["status"] == "submitted"
    assert all(f"location:{a}" in line["notes"] for line in allowed["lines"])
    assert len(client.get("/api/v1/requisitions", headers=owner).json()) == before + 2


def test_revoked_scope_is_fail_closed_for_procurement_reads_and_writes(client):
    owner, scoped, _unassigned, (a, b), item, _supplier, _pos, scope_id = seed(client)
    with SessionLocal() as db:
        db.get(OperationalAccessScope, scope_id).is_active = False
        db.commit()

    planning = client.get("/api/v1/procurement/planning", headers=scoped)
    assert planning.status_code == 200 and planning.json()["rows"] == []
    assert planning.json()["summary"]["estimated_value"] in ("0", "0.0000")
    assert client.get("/api/v1/reorder-suggestions", headers=scoped).json() == []
    assert client.get("/api/v1/reorder-suggestions?location_id=" + a,
                      headers=scoped).status_code == 403
    report = client.get("/api/v1/supplier-performance", headers=scoped)
    assert report.status_code == 200
    assert all(row["purchase_orders"] == 0 and Decimal(row["received_value"]) == 0
               for row in report.json())
    response = client.post("/api/v1/procurement/planning/requisitions",
                           headers=scoped, json={
        "department": "Cafe", "location_id": a,
        "justification": "Should be denied",
        "lines": [{"item_id": item["id"], "quantity": "1"}],
    })
    assert response.status_code == 403
    assert client.post("/api/v1/reorder-suggestions/requisition", headers=scoped,
                       json={"department": "Cafe", "location_id": a}).status_code == 403
    assert len(client.get("/api/v1/requisitions", headers=owner).json()) == 0
