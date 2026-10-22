"""Verify maintenance/financial-report location authorization with real HTTP routes.

A scoped operator must not view/modify another site's work orders or initiate
accounting postings, and CSV exports must not disclose other stock balances.
"""

import csv
import io
from decimal import Decimal

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.operations import IntegrationEvent
from app.models.pass6 import OperationalAccessScope
from app.models.user import User


def auth(client, email="owner@example.com"):
    response = client.post("/api/v1/auth/login", json={
        "email": email, "password": "password123",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create(client, route, headers, data):
    response = client.post(route, headers=headers, json=data)
    assert response.status_code == 201, (route, response.text)
    return response.json()


def by_code(rows, code):
    return next((r for r in rows if r["code"] == code), None)


def seed(client):
    owner = auth(client)
    dims = client.get("/api/v1/classification/bootstrap", headers=owner).json()["dimensions"]
    assets = by_code(dims["workspace"], "assets-property")
    equip = by_code(dims["item_type"], "equipment")
    asset_class = by_code(dims.get("asset_class", []), "equipment")
    if not asset_class:
        asset_class = create(client, "/api/v1/classification/dimensions", owner, {
            "dimension_type": "asset_class", "code": "equipment",
            "name": "Equipment", "behavior_key": "equipment",
        })
    method = by_code(dims.get("depreciation_method", []), "straight-line")
    if not method:
        method = create(client, "/api/v1/classification/dimensions", owner, {
            "dimension_type": "depreciation_method", "code": "straight-line",
            "name": "Straight line", "behavior_key": "straight_line",
        })
    cat = create(client, "/api/v1/categories", owner, {"name": "Secure maintenance category"})
    unit = create(client, "/api/v1/units", owner, {"code": "SMA", "name": "Maintenance piece", "precision": 0})
    a, b = [
        create(client, "/api/v1/locations", owner, {"code": code, "name": code})["id"]
        for code in ("MAINT-SCOPE-A", "MAINT-SCOPE-B")
    ]
    item = create(client, "/api/v1/items", owner, {
        "sku": "MAINT-SCOPE-ITEM", "name": "Generator",
        "category_id": cat["id"], "base_unit_id": unit["id"],
        "primary_workspace_id": assets["id"], "item_type_id": equip["id"],
        "standard_cost": "100",
    })["id"]
    asset_ids = []
    for idx, loc in enumerate((a, b)):
        result = create(client, "/api/v1/assets", owner, {
            "asset_tag": "MAINT-SCOPE-" + str(idx), "item_id": item,
            "asset_class_id": asset_class["id"],
            "depreciation_method_id": method["id"], "location_id": loc,
            "acquisition_date": "2026-01-01",
            "placed_in_service_date": "2026-01-01",
            "acquisition_cost": 60000, "useful_life_months": 60,
        })
        asset_ids.append(result["id"])
        create(client, "/api/v1/stock/receipts", owner, {
            "location_id": loc,
            "lines": [{"item_id": item, "quantity": "5", "unit_cost": 100}],
        })
    with SessionLocal() as db:
        for email, role in (
            ("maint-scoped@example.com", "inventory_manager"),
            ("maint-unscoped@example.com", "inventory_manager"),
            ("maint-procurement@example.com", "procurement_officer"),
            ("maint-viewer@example.com", "viewer"),
        ):
            db.add(User(email=email, full_name=email, role=role,
                        password_hash=hash_password("password123")))
        db.commit()
        users = {
            u.email: u.id for u in db.query(User).filter(User.email.like("maint-%")).all()
        }
    scopes = {}
    for email in ("maint-scoped@example.com", "maint-procurement@example.com",
                  "maint-viewer@example.com"):
        scopes[email] = create(client, "/api/v1/access-scopes", owner, {
            "user_id": users[email], "location_id": a,
            "approval_limit": "0",
        })["id"]
    return {
        "owner": owner, "scoped": auth(client, "maint-scoped@example.com"),
        "unscoped": auth(client, "maint-unscoped@example.com"),
        "procurement": auth(client, "maint-procurement@example.com"),
        "viewer": auth(client, "maint-viewer@example.com"),
        "a": a, "b": b, "assets": asset_ids, "item": item, "scopes": scopes,
    }


def plan_payload(asset, code):
    return {
        "code": code, "name": "Inspection " + code,
        "asset_id": asset, "interval_days": 30, "next_due_date": "2026-12-01",
    }


def order_payload(asset, plan=None):
    return {
        "asset_id": asset, "title": "Inspect generator",
        "plan_id": plan, "parts": [],
    }


def test_maintenance_scope_filters_and_prevents_foreign_accounting_posting(client):
    s = seed(client)
    owner, scoped, unscoped = s["owner"], s["scoped"], s["unscoped"]
    asset_a, asset_b = s["assets"]
    plan_a = create(client, "/api/v1/maintenance/plans", owner,
                    plan_payload(asset_a, "MAINT-PLAN-A"))
    plan_b = create(client, "/api/v1/maintenance/plans", owner,
                    plan_payload(asset_b, "MAINT-PLAN-B"))
    order_a = create(client, "/api/v1/maintenance/work-orders", owner,
                     order_payload(asset_a, plan_a["id"]))
    order_b = create(client, "/api/v1/maintenance/work-orders", owner,
                     order_payload(asset_b, plan_b["id"]))
    assert {x["id"] for x in client.get("/api/v1/maintenance/plans", headers=scoped).json()} == {plan_a["id"]}
    assert {x["id"] for x in client.get("/api/v1/maintenance/work-orders", headers=scoped).json()} == {order_a["id"]}
    assert len(client.get("/api/v1/maintenance/work-orders", headers=unscoped).json()) == 2
    assert len(client.get("/api/v1/maintenance/work-orders", headers=owner).json()) == 2

    assert client.post("/api/v1/maintenance/plans", headers=scoped,
                       json=plan_payload(asset_b, "FOREIGN-PLAN")).status_code == 403
    assert client.post("/api/v1/maintenance/work-orders", headers=scoped,
                       json=order_payload(asset_b)).status_code == 403
    # A plan for one asset cannot be attached to a different asset.
    assert client.post("/api/v1/maintenance/work-orders", headers=owner,
                       json=order_payload(asset_a, plan_b["id"])).status_code == 422

    with SessionLocal() as db:
        initial_events = db.query(IntegrationEvent).count()
    assert client.post(f"/api/v1/maintenance/work-orders/{order_b['id']}/start",
                       headers=scoped).status_code == 403
    assert client.post(f"/api/v1/maintenance/work-orders/{order_b['id']}/complete",
                       headers=scoped, json={"labor_cost": 200, "external_cost": 50}).status_code == 403
    assert next(x for x in client.get("/api/v1/maintenance/work-orders", headers=owner).json()
                if x["id"] == order_b["id"])["status"] == "open"
    with SessionLocal() as db:
        assert db.query(IntegrationEvent).count() == initial_events

    assert client.post(f"/api/v1/maintenance/work-orders/{order_a['id']}/start",
                       headers=scoped).status_code == 200
    allowed = client.post(f"/api/v1/maintenance/work-orders/{order_a['id']}/complete",
                          headers=scoped,
                          json={"labor_cost": "200", "external_cost": "50"})
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["status"] == "completed"
    with SessionLocal() as db:
        assert db.query(IntegrationEvent).count() == initial_events + 1

    with SessionLocal() as db:
        db.get(OperationalAccessScope, s["scopes"]["maint-scoped@example.com"]).is_active = False
        db.commit()
    assert client.get("/api/v1/maintenance/plans", headers=scoped).json() == []
    assert client.get("/api/v1/maintenance/work-orders", headers=scoped).json() == []
    assert client.post("/api/v1/maintenance/plans", headers=scoped,
                       json=plan_payload(asset_a, "REVOKED-PLAN")).status_code == 403
    assert client.post(f"/api/v1/maintenance/work-orders/{order_b['id']}/complete",
                       headers=scoped, json={}).status_code == 403


def test_valued_csv_exports_and_global_diagnostics_are_scope_protected(client):
    s = seed(client)
    owner, viewer, scoped, procurement = s["owner"], s["viewer"], s["scoped"], s["procurement"]
    a, b = s["a"], s["b"]
    def csv_rows(headers):
        result = client.get("/api/v1/exports/balances.csv", headers=headers)
        assert result.status_code == 200, result.text
        return list(csv.DictReader(io.StringIO(result.text)))
    assert {r["location_id"] for r in csv_rows(owner)} == {a, b}
    assert {r["location_id"] for r in csv_rows(scoped)} == {a}
    assert {r["location_id"] for r in csv_rows(viewer)} == {a}
    assert {r["location_id"] for r in csv_rows(s["unscoped"])} == {a, b}

    sensitive = (
        "/api/v1/audit-logs", "/api/v1/integration-events",
        "/api/v1/backups", "/api/v1/integrations/accounting/workspace",
        "/api/v1/integrations/operations/workspace",
        "/api/v1/integrations/reconciliation",
        "/api/v1/accounting-mappings", "/api/v1/purchase-line-treatments",
    )
    for endpoint in sensitive:
        response = client.get(endpoint, headers=viewer)
        if endpoint in ("/api/v1/accounting-mappings", "/api/v1/purchase-line-treatments"):
            # Only inventory operators hold these read permissions.
            assert response.status_code == 403, (endpoint, response.text)
        else:
            assert response.status_code == 403, (endpoint, response.text)
    assert client.get("/api/v1/audit-logs", headers=owner).status_code == 200
    assert client.get("/api/v1/backups", headers=owner).status_code == 200
    assert client.get("/api/v1/accounting-mappings", headers=owner).status_code == 200
    assert client.get("/api/v1/integrations/reconciliation", headers=owner).status_code == 200
    for path in ("/api/v1/accounting-mappings", "/api/v1/purchase-line-treatments"):
        assert client.get(path, headers=scoped).status_code == 403

    payload = {"direction": "outbound", "source_system": "inventory",
               "destination_system": "accounting", "event_type": "manual.test",
               "aggregate_type": "test", "aggregate_id": "1",
               "idempotency_key": "should-not-create-global-event", "payload": {}}
    assert client.post("/api/v1/integration-events", headers=procurement,
                       json=payload).status_code == 403
    assert client.post("/api/v1/integration-events/process", headers=procurement).status_code == 403
    assert client.post("/api/v1/accounting-mappings", headers=scoped, json={
        "event_key": "should-not-create", "debit_account": "A",
        "credit_account": "B",
    }).status_code == 403
    assert client.post("/api/v1/purchase-line-treatments", headers=scoped, json={
        "source_type": "purchase_order_line", "source_line_id": "unknown",
        "treatment": "fixed_asset", "intended_location_id": a,
    }).status_code == 403

    with SessionLocal() as db:
        db.get(OperationalAccessScope, s["scopes"]["maint-scoped@example.com"]).is_active = False
        db.commit()
    assert csv_rows(scoped) == []
    assert client.get("/api/v1/integration-events", headers=scoped).status_code == 403
