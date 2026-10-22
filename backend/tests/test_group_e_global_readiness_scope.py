"""Group E: protect unlocated rollout/migration records and printable procurement documents.

The tests use synthetic fixtures only; no production stock or Accounting posts.
"""
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.pass6 import OperationalAccessScope
from app.models.procurement import PurchaseOrder, PurchaseRequisition
from app.models.readiness import AcceptanceRun, DataImportJob
from app.models.stabilization import OperationalIncident, StaffFeedback
from app.models.user import User


def login(client, email="owner@example.com"):
    response = client.post("/api/v1/auth/login", json={
        "email": email, "password": "password123",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def post(client, path, headers, payload):
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == 201, (path, response.text)
    return response.json()


def seed_users(client):
    owner = login(client)
    a, b = [
        post(client, "/api/v1/locations", owner, {
            "code": code, "name": code,
        })["id"]
        for code in ("GROUP-E-A", "GROUP-E-B")
    ]
    with SessionLocal() as db:
        for email, role in (
            ("group-e-manager@example.com", "inventory_manager"),
            ("group-e-unscoped@example.com", "inventory_manager"),
            ("group-e-buyer@example.com", "procurement_officer"),
        ):
            db.add(User(email=email, full_name=email, role=role,
                        password_hash=hash_password("password123")))
        db.commit()
        ids = {u.email: u.id for u in db.query(User).all()}
    scopes = {}
    for email in ("group-e-manager@example.com", "group-e-buyer@example.com"):
        scopes[email] = post(client, "/api/v1/access-scopes", owner, {
            "user_id": ids[email], "location_id": a,
            "approval_limit": "0",
        })["id"]
    return {
        "owner": owner, "manager": login(client, "group-e-manager@example.com"),
        "unscoped": login(client, "group-e-unscoped@example.com"),
        "buyer": login(client, "group-e-buyer@example.com"),
        "a": a, "b": b, "scopes": scopes,
    }


def test_unlocated_feedback_incident_and_rollout_are_globally_protected(client):
    s = seed_users(client)
    owner, manager = s["owner"], s["manager"]
    feedback = post(client, "/api/v1/feedback", owner, {
        "category": "bug", "severity": "critical",
        "message": "Sensitive global rollout failure in production",
    })
    incident = post(client, "/api/v1/incidents", owner, {
        "source": "api", "severity": "critical", "title": "Private cross-site incident",
        "details": "Contains internal operational context",
    })
    # Location-scoped staff may still submit their own feedback.
    response = client.post("/api/v1/feedback", headers=manager, json={
        "category": "usability", "severity": "normal",
        "message": "Please make stock lookup clearer",
    })
    assert response.status_code == 201, response.text

    blocked = [
        ("get", "/api/v1/feedback", None),
        ("patch", f"/api/v1/feedback/{feedback['id']}", {"status": "resolved"}),
        ("get", "/api/v1/incidents", None),
        ("patch", f"/api/v1/incidents/{incident['id']}", {"status": "resolved"}),
        ("post", "/api/v1/incidents", {
            "source": "api", "severity": "warning",
            "title": "Unauthorized incident", "details": "Cannot create this",
        }),
        ("get", "/api/v1/rollout/summary", None),
        ("post", "/api/v1/rollout/smoke-test", None),
    ]
    for method, path, data in blocked:
        response = getattr(client, method)(path, headers=manager, **({"json": data} if data else {}))
        assert response.status_code == 403, (method, path, response.text)
    assert client.get("/api/v1/feedback", headers=s["unscoped"]).status_code == 200
    assert client.get("/api/v1/incidents", headers=owner).status_code == 200
    assert client.get("/api/v1/rollout/summary", headers=owner).status_code == 200
    with SessionLocal() as db:
        assert db.get(StaffFeedback, feedback["id"]).status == "open"
        assert db.get(OperationalIncident, incident["id"]).status == "open"
        db.get(OperationalAccessScope, s["scopes"]["group-e-manager@example.com"]).is_active = False
        db.commit()
    assert client.get("/api/v1/feedback", headers=manager).status_code == 403


def test_global_import_and_assurance_routes_fail_closed_before_mutations(client):
    s = seed_users(client)
    owner, manager = s["owner"], s["manager"]
    read_endpoints = (
        "/api/v1/migration/imports",
        "/api/v1/deployment/status",
        "/api/v1/acceptance-runs",
        "/api/v1/exports/items.csv",
    )
    for path in read_endpoints:
        assert client.get(path, headers=manager).status_code == 403, path
        assert client.get(path, headers=owner).status_code == 200, path

    csv_file = {"file": ("items.csv", b"sku,name,category,unit\nABC,Item,Food,EA\n", "text/csv")}
    validate = client.post("/api/v1/migration/imports/items/validate",
                           headers=manager, files=csv_file)
    assert validate.status_code == 403, validate.text
    assert client.post("/api/v1/migration/imports/unknown/apply",
                       headers=manager).status_code == 403
    assert client.post("/api/v1/acceptance-runs", headers=manager,
                       json={"environment": "staging"}).status_code == 403
    assert client.post("/api/v1/imports/items.csv", headers=manager,
                       files=csv_file).status_code == 403
    with SessionLocal() as db:
        assert db.query(DataImportJob).count() == 0
        assert db.query(AcceptanceRun).count() == 0

    assert client.get("/api/v1/migration/imports",
                      headers=s["unscoped"]).status_code == 200
    with SessionLocal() as db:
        db.get(OperationalAccessScope, s["scopes"]["group-e-manager@example.com"]).is_active = False
        db.commit()
    assert client.get("/api/v1/deployment/status", headers=manager).status_code == 403


def test_legacy_print_and_cancel_obey_authoritative_location(client):
    s = seed_users(client)
    owner, buyer, a, b = s["owner"], s["buyer"], s["a"], s["b"]
    category = post(client, "/api/v1/categories", owner, {"name": "Group E"})
    unit = post(client, "/api/v1/units", owner, {"code": "GE", "name": "Unit"})
    item = post(client, "/api/v1/items", owner, {
        "sku": "GROUP-E-ITEM", "name": "Stock item", "category_id": category["id"],
        "base_unit_id": unit["id"], "standard_cost": "15",
    })
    supplier = post(client, "/api/v1/suppliers", owner, {
        "code": "GROUP-E-SUP", "name": "Group E Supplier",
    })
    requisitions = [
        post(client, "/api/v1/requisitions", owner, {
            "department": "Cafe", "location_id": loc,
            "lines": [{"item_id": item["id"], "quantity": "2", "estimated_unit_cost": "15"}],
        }) for loc in (a, b)
    ]
    pos = [
        post(client, "/api/v1/purchase-orders", owner, {
            "supplier_id": supplier["id"], "delivery_location_id": loc,
            "lines": [{"item_id": item["id"], "ordered_quantity": "2", "unit_price": "15"}],
        }) for loc in (a, b)
    ]
    po_a, po_b = pos
    req_a, req_b = requisitions

    assert client.get(f"/api/v1/print/purchase-orders/{po_a['id']}",
                      headers=buyer).status_code == 200
    assert client.get(f"/api/v1/print/purchase-orders/{po_b['id']}",
                      headers=buyer).status_code == 403
    assert client.post(f"/api/v1/requisitions/{req_b['id']}/cancel",
                       headers=buyer).status_code == 403
    assert client.post(f"/api/v1/purchase-orders/{po_b['id']}/cancel",
                       headers=buyer).status_code == 403
    assert client.post(f"/api/v1/requisitions/{req_a['id']}/cancel",
                       headers=buyer).status_code == 200

    with SessionLocal() as db:
        assert db.get(PurchaseOrder, po_b["id"]).status == "draft"
        assert db.get(PurchaseRequisition, req_b["id"]).status == "draft" or db.get(
            PurchaseRequisition, req_b["id"]).status == "submitted"
        db.get(PurchaseOrder, po_b["id"]).status = "approved"
        db.commit()

    receipt = post(client, f"/api/v1/receiving/purchase-orders/{po_b['id']}", owner, {
        "delivery_reference": "GROUP-E-RECEIVE",
        "idempotency_key": "group-e-receive",
        "lines": [{
            "purchase_order_line_id": po_b["lines"][0]["id"],
            "received_quantity": "1", "accepted_quantity": "1", "rejected_quantity": "0",
        }],
    })
    receipt_id = receipt.get("id") or receipt.get("goods_receipt_id")
    assert receipt_id, receipt
    assert client.get(f"/api/v1/print/goods-receipts/{receipt_id}",
                      headers=buyer).status_code == 403
    assert client.get(f"/api/v1/print/goods-receipts/{receipt_id}",
                      headers=owner).status_code == 200
