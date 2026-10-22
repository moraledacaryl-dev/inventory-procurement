"""Regression coverage for authoritative requisition location provenance.

Legacy NULL locations remain unassigned, independent of line-note hints.
Quotations inherit ownership from the typed parent requisition.
"""

from decimal import Decimal

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.pass6 import OperationalAccessScope
from app.models.procurement import PurchaseRequisition
from app.models.user import User


def auth(client, email="owner@example.com"):
    r = client.post("/api/v1/auth/login", json={
        "email": email, "password": "password123",
    })
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def post(client, path, header, payload):
    r = client.post(path, headers=header, json=payload)
    assert r.status_code == 201, (path, r.text)
    return r.json()


def scenario(client):
    owner = auth(client)
    category = post(client, "/api/v1/categories", owner, {"name": "Location owner test"})
    unit = post(client, "/api/v1/units", owner, {"code": "LOR", "name": "Loc ownership unit"})
    a, b = [
        post(client, "/api/v1/locations", owner, {"code": code, "name": code})["id"]
        for code in ("OWNER-LOC-A", "OWNER-LOC-B")
    ]
    item = post(client, "/api/v1/items", owner, {
        "sku": "LOC-OWNER-ITEM", "name": "Owned supplies",
        "category_id": category["id"], "base_unit_id": unit["id"],
        "standard_cost": "10", "minimum_stock": "20",
    })["id"]
    supplier = post(client, "/api/v1/suppliers", owner, {
        "code": "LOC-OWNER-SUP", "name": "Owned supplier",
    })["id"]
    with SessionLocal() as db:
        for email in ("loc-a@example.com", "loc-b@example.com", "loc-open@example.com"):
            db.add(User(
                email=email, full_name=email, role="procurement_officer",
                password_hash=hash_password("password123"),
            ))
        db.commit()
        ids = {x.email: x.id for x in db.query(User).filter(
            User.email.in_(["loc-a@example.com", "loc-b@example.com"])
        ).all()}
    scopes = {}
    for email, loc in (("loc-a@example.com", a), ("loc-b@example.com", b)):
        scopes[email] = post(client, "/api/v1/access-scopes", owner, {
            "user_id": ids[email], "location_id": loc, "approval_limit": "10000",
        })["id"]
    return owner, auth(client, "loc-a@example.com"), auth(client, "loc-b@example.com"), auth(client, "loc-open@example.com"), a, b, item, supplier, scopes


def req_payload(item, location_id=None, notes=None):
    return {
        "department": "Operations",
        "justification": "Proper location provenance",
        **({"location_id": location_id} if location_id else {}),
        "lines": [{
            "item_id": item, "quantity": "4",
            "estimated_unit_cost": "15",
            **({"notes": notes} if notes else {}),
        }],
    }


def quote_payload(req, supplier, item):
    return {
        "requisition_id": req, "supplier_id": supplier,
        "lines": [{"item_id": item, "quantity": "4", "unit_price": "18"}],
    }


def po_payload(req, quote, supplier, item, location):
    return {
        "supplier_id": supplier, "requisition_id": req, "quotation_id": quote,
        "delivery_location_id": location,
        "lines": [{"item_id": item, "ordered_quantity": "4", "unit_price": "18"}],
    }


def test_typed_requisitions_and_workspace_lists_and_quotes_are_isolated(client):
    owner, user_a, user_b, no_scope, a, b, item, supplier, scopes = scenario(client)
    # The forged B hint cannot override the authoritative A location.
    req_a = post(client, "/api/v1/requisitions", owner, req_payload(item, a, f"location:{b}"))
    req_b = post(client, "/api/v1/requisitions", owner, req_payload(item, b))
    legacy = post(client, "/api/v1/requisitions", owner, req_payload(item, notes=f"location:{a}"))
    assert req_a["location_id"] == a
    assert legacy["location_id"] is None

    for headers, expected in ((owner, {req_a["id"], req_b["id"], legacy["id"]}),
                              (no_scope, {req_a["id"], req_b["id"], legacy["id"]}),
                              (user_a, {req_a["id"]}), (user_b, {req_b["id"]})):
        listed = client.get("/api/v1/requisitions", headers=headers)
        workspace = client.get("/api/v1/procurement/requisitions/workspace", headers=headers)
        assert listed.status_code == 200 and workspace.status_code == 200
        assert {x["id"] for x in listed.json()} == expected
        assert {x["id"] for x in workspace.json()} == expected

    for req in (req_a, req_b, legacy):
        with SessionLocal() as db:
            db.get(PurchaseRequisition, req["id"]).status = "approved"
            db.commit()
    q_a = post(client, "/api/v1/quotations", owner, quote_payload(req_a["id"], supplier, item))
    q_b = post(client, "/api/v1/quotations", owner, quote_payload(req_b["id"], supplier, item))
    q_legacy = post(client, "/api/v1/quotations", owner, quote_payload(legacy["id"], supplier, item))

    for headers, expected_quotes in (
        (owner, {q_a["id"], q_b["id"], q_legacy["id"]}),
        (user_a, {q_a["id"]}), (user_b, {q_b["id"]}),
    ):
        listed = client.get("/api/v1/quotations", headers=headers)
        assert listed.status_code == 200, listed.text
        assert {x["id"] for x in listed.json()} == expected_quotes
    assert client.get("/api/v1/quotations?requisition_id=" + req_b["id"],
                      headers=user_a).status_code == 403
    assert client.get("/api/v1/requisitions/" + req_b["id"] + "/quotation-comparison",
                      headers=user_a).status_code == 403
    assert client.get("/api/v1/requisitions/" + legacy["id"] + "/quotation-comparison",
                      headers=user_a).status_code == 403
    assert client.post("/api/v1/quotations", headers=user_a, json=quote_payload(
        req_b["id"], supplier, item)).status_code == 403
    assert client.post("/api/v1/quotations", headers=user_a, json=quote_payload(
        legacy["id"], supplier, item)).status_code == 403

    # Unawarded quotations must be visible when the parent PR has a typed
    # authorized location; they are not dependent on a PO already existing.
    workspace_a = client.get("/api/v1/procurement/quotation-workspace", headers=user_a)
    assert workspace_a.status_code == 200, workspace_a.text
    assert {x["id"] for x in workspace_a.json()["requisitions"]} == {req_a["id"]}
    assert workspace_a.json()["requisitions"][0]["quotations"][0]["id"] == q_a["id"]
    assert workspace_a.json()["summary"]["quotations"] == 1

    # Pending PR units use the typed A location, not the editable line-note B hint.
    plan_b = client.get("/api/v1/procurement/planning?location_id=" + b, headers=owner)
    assert plan_b.status_code == 200
    assert all(x["location_id"] == b for x in plan_b.json()["rows"])

    with SessionLocal() as db:
        db.get(OperationalAccessScope, scopes["loc-a@example.com"]).is_active = False
        db.commit()
    assert client.get("/api/v1/requisitions", headers=user_a).json() == []
    assert client.get("/api/v1/quotations", headers=user_a).json() == []
    assert client.get("/api/v1/procurement/requisitions/workspace", headers=user_a).json() == []
    assert client.get("/api/v1/procurement/quotation-workspace",
                      headers=user_a).json()["requisitions"] == []


def test_scoped_creation_and_approval_and_po_location_invariants(client):
    owner, user_a, user_b, no_scope, a, b, item, supplier, _scopes = scenario(client)
    for payload in (req_payload(item), req_payload(item, b)):
        denied = client.post("/api/v1/requisitions", headers=user_a, json=payload)
        assert denied.status_code == 403, denied.text
    req = post(client, "/api/v1/requisitions", owner, req_payload(item, a))
    assert client.post("/api/v1/requisitions/" + req["id"] + "/reject",
                       headers=user_b).status_code == 403
    assert client.post("/api/v1/requisitions/" + req["id"] + "/approve",
                       headers=user_b).status_code == 403
    approved = client.post("/api/v1/requisitions/" + req["id"] + "/approve",
                           headers=user_a)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["location_id"] == a
    quote = post(client, "/api/v1/quotations", user_a, quote_payload(req["id"], supplier, item))
    wrong_po = client.post("/api/v1/purchase-orders", headers=owner, json=po_payload(
        req["id"], quote["id"], supplier, item, b))
    assert wrong_po.status_code == 409, wrong_po.text
    wrong_award = client.post("/api/v1/requisitions/" + req["id"] + "/award-quotation",
                              headers=owner, json={
        "quotation_id": quote["id"], "delivery_location_id": b,
    })
    assert wrong_award.status_code == 409, wrong_award.text
    assert client.post("/api/v1/requisitions/" + req["id"] + "/award-quotation",
                       headers=user_b, json={
        "quotation_id": quote["id"], "delivery_location_id": b,
    }).status_code == 403
    po = post(client, "/api/v1/purchase-orders", user_a, po_payload(
        req["id"], quote["id"], supplier, item, a))
    assert po["delivery_location_id"] == a
    assert client.post("/api/v1/purchase-orders/" + po["id"] + "/approve",
                       headers=user_b).status_code == 403
    assert client.post("/api/v1/purchase-orders/" + po["id"] + "/approve",
                       headers=user_a).status_code == 409  # creator cannot approve


def test_legacy_untagged_is_unassigned_and_notes_cannot_grant_scope(client):
    owner, user_a, _user_b, _open, a, b, item, supplier, _scopes = scenario(client)
    legacy = post(client, "/api/v1/requisitions", owner, req_payload(item, notes="location:" + a))
    with SessionLocal() as db:
        row = db.get(PurchaseRequisition, legacy["id"])
        assert row.location_id is None
        row.status = "approved"
        db.commit()
    assert client.post("/api/v1/quotations", headers=user_a,
                       json=quote_payload(legacy["id"], supplier, item)).status_code == 403
    assert client.get("/api/v1/requisitions/" + legacy["id"] + "/quotation-comparison",
                      headers=user_a).status_code == 403
    assert client.post("/api/v1/purchase-orders", headers=user_a,
                       json={"supplier_id": supplier, "requisition_id": legacy["id"],
                             "delivery_location_id": a,
                             "lines": [{"item_id": item, "ordered_quantity": "2",
                                        "unit_price": "10"}]}).status_code == 403
    # Owner can continue managing historical work without an automatic backfill.
    q = post(client, "/api/v1/quotations", owner,
             quote_payload(legacy["id"], supplier, item))
    assert q["requisition_id"] == legacy["id"]


def test_read_only_legacy_audit_preserves_null_and_reports_conflicts(client):
    from scripts.audit_requisition_locations import report
    owner, _a_user, _b_user, _open, a, b, item, supplier, _scopes = scenario(client)
    legacy = post(client, "/api/v1/requisitions", owner,
                  req_payload(item, notes=f"location:{b}"))
    typed = post(client, "/api/v1/requisitions", owner, req_payload(item, a))
    with SessionLocal() as db:
        first = report(db)
        second = report(db)
        assert first == second  # no writes, even across repeat reads
        assert first["read_only"] is True
        assert first["requisition_total"] == 2
        assert first["authoritatively_assigned"] == 1
        assert first["unassigned_requires_review"] == 1
        assert first["typed_location_po_conflicts"] == 0
        assert first["unassigned_sample"][0]["requisition_id"] == legacy["id"]
        assert db.get(PurchaseRequisition, legacy["id"]).location_id is None
        assert db.get(PurchaseRequisition, typed["id"]).location_id == a
