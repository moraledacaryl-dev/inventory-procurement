"""Regression proof for location isolation in PO and receiving workflows.

Real route requests exercise both legacy and controlled receiving APIs. Replays
must not disclose out-of-scope receipts after a user's scope is revoked.
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


def create(client, url, headers, payload):
    response = client.post(url, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def seed(client):
    owner = login(client)
    category = create(client, "/api/v1/categories", owner, {"name": "Scoped receiving"})
    unit = create(client, "/api/v1/units", owner, {"code": "RS", "name": "Scope receiving"})
    locations = [
        create(client, "/api/v1/locations", owner, {"code": code, "name": code})["id"]
        for code in ("RECV-SCOPE-A", "RECV-SCOPE-B")
    ]
    item = create(client, "/api/v1/items", owner, {
        "sku": "RCV-SCOPE", "name": "Receiving scope item",
        "category_id": category["id"], "base_unit_id": unit["id"], "standard_cost": "20",
    })
    supplier = create(client, "/api/v1/suppliers", owner, {
        "code": "RCV-SCOPE-SUP", "name": "Scoped Supplier",
    })
    pos = [
        create(client, "/api/v1/purchase-orders", owner, {
            "supplier_id": supplier["id"], "delivery_location_id": location,
            "lines": [{"item_id": item["id"], "ordered_quantity": "8", "unit_price": "20"}],
        })
        for location in locations
    ]
    with SessionLocal() as db:
        for po in pos:
            db.get(PurchaseOrder, po["id"]).status = "approved"
        for email, role in (
            ("scope-receiver@example.com", "receiver"),
            ("scope-buyer@example.com", "procurement_officer"),
        ):
            db.add(User(email=email, full_name=email, role=role,
                        password_hash=hash_password("password123")))
        db.commit()
        ids = {row.email: row.id for row in db.query(User).all()}
    scope_ids = []
    for email in ("scope-receiver@example.com", "scope-buyer@example.com"):
        scope = create(client, "/api/v1/access-scopes", owner, {
            "user_id": ids[email], "location_id": locations[0],
            "approval_limit": "0",
        })
        scope_ids.append(scope["id"])
    receiver = login(client, "scope-receiver@example.com")
    buyer = login(client, "scope-buyer@example.com")
    return owner, receiver, buyer, locations, item, supplier, pos, scope_ids


def receipt_payload(line_id, key, reference):
    return {
        "delivery_reference": reference,
        "idempotency_key": key,
        "lines": [{
            "purchase_order_line_id": line_id, "received_quantity": "2",
            "accepted_quantity": "2", "rejected_quantity": "0",
        }],
    }


def test_receiving_lists_and_mutations_are_location_scoped(client):
    owner, receiver, buyer, (a, b), item, supplier, (po_a, po_b), _scopes = seed(client)
    line_a = po_a["lines"][0]["id"]
    line_b = po_b["lines"][0]["id"]

    # Genuine transactions on both locations must not appear in a scoped workspace.
    receipt_a = receipt_payload(line_a, "rs-owner-a", "RS-OWNER-A")
    receipt_b = receipt_payload(line_b, "rs-owner-b", "RS-OWNER-B")
    for po, payload in ((po_a, receipt_a), (po_b, receipt_b)):
        response = client.post(f"/api/v1/receiving/purchase-orders/{po['id']}",
                               headers=owner, json=payload)
        assert response.status_code == 201, response.text

    scoped_workspace = client.get("/api/v1/receiving/workspace", headers=receiver)
    assert scoped_workspace.status_code == 200, scoped_workspace.text
    data = scoped_workspace.json()
    assert {po["delivery_location_id"] for po in data["purchase_orders"]} == {a}
    assert {row["delivery_location_id"] for row in data["receipts"]} == {a}
    assert data["summary"]["receipts"] == 1
    assert len(client.get("/api/v1/goods-receipts", headers=receiver).json()) == 1
    assert {po["delivery_location_id"] for po in client.get(
        "/api/v1/purchase-orders", headers=buyer).json()} == {a}
    assert len(client.get("/api/v1/receiving/workspace", headers=owner).json()["receipts"]) == 2

    out_of_scope_url = f"/api/v1/receiving/purchase-orders/{po_b['id']}"
    denied_controlled = client.post(out_of_scope_url, headers=receiver, json=receipt_b)
    assert denied_controlled.status_code == 403, denied_controlled.text
    denied_legacy = client.post(f"/api/v1/purchase-orders/{po_b['id']}/receipts",
                                headers=receiver, json=receipt_b)
    assert denied_legacy.status_code == 403, denied_legacy.text
    denied_controlled_return = client.post(
        out_of_scope_url + "/returns", headers=receiver,
        json={"reason": "wrong location", "idempotency_key": "rs-denied-return",
              "lines": [{"purchase_order_line_id": line_b, "quantity": "1"}]},
    )
    assert denied_controlled_return.status_code == 403, denied_controlled_return.text
    denied_legacy_return = client.post(
        f"/api/v1/purchase-orders/{po_b['id']}/returns", headers=receiver,
        json={"reason": "wrong location",
              "lines": [{"purchase_order_line_id": line_b, "quantity": "1"}]},
    )
    assert denied_legacy_return.status_code == 403, denied_legacy_return.text
    assert len(client.get("/api/v1/receiving/workspace", headers=owner).json()["receipts"]) == 2

    rejected_po = client.post("/api/v1/purchase-orders", headers=buyer, json={
        "supplier_id": supplier["id"], "delivery_location_id": b,
        "lines": [{"item_id": item["id"], "ordered_quantity": "1", "unit_price": "20"}],
    })
    assert rejected_po.status_code == 403, rejected_po.text
    allowed_po = client.post("/api/v1/purchase-orders", headers=buyer, json={
        "supplier_id": supplier["id"], "delivery_location_id": a,
        "lines": [{"item_id": item["id"], "ordered_quantity": "1", "unit_price": "20"}],
    })
    assert allowed_po.status_code == 201, allowed_po.text

    # A receiver can still post at their own assigned location.
    allowed_payload = receipt_payload(line_a, "rs-receiver-a", "RS-RECEIVER-A")
    accepted = client.post(f"/api/v1/receiving/purchase-orders/{po_a['id']}",
                           headers=receiver, json=allowed_payload)
    assert accepted.status_code == 201, accepted.text
    assert Decimal(accepted.json()["accepted_value"]) == Decimal("40")
    repeated = client.post(f"/api/v1/receiving/purchase-orders/{po_a['id']}",
                           headers=receiver, json=allowed_payload)
    assert repeated.status_code == 201 and repeated.json()["id"] == accepted.json()["id"]


def test_revoked_receiving_scope_blocks_lists_posts_and_idempotent_replay(client):
    owner, receiver, buyer, (a, b), _item, _supplier, (po_a, po_b), scope_ids = seed(client)
    line_a = po_a["lines"][0]["id"]
    payload = receipt_payload(line_a, "rs-before-revoke", "RS-BEFORE-REVOKE")
    url = f"/api/v1/receiving/purchase-orders/{po_a['id']}"
    posted = client.post(url, headers=receiver, json=payload)
    assert posted.status_code == 201, posted.text

    with SessionLocal() as db:
        for scope_id in scope_ids:
            db.get(OperationalAccessScope, scope_id).is_active = False
        db.commit()

    for path in ("/api/v1/receiving/workspace", "/api/v1/purchase-orders",
                 "/api/v1/goods-receipts"):
        headers = buyer if path == "/api/v1/purchase-orders" else receiver
        response = client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        if path == "/api/v1/receiving/workspace":
            assert response.json()["purchase_orders"] == []
            assert response.json()["receipts"] == []
            assert response.json()["returns"] == []
        else:
            assert response.json() == []
    replay = client.post(url, headers=receiver, json=payload)
    assert replay.status_code == 403, replay.text
    assert client.post(
        f"/api/v1/purchase-orders/{po_a['id']}/receipts",
        headers=receiver, json=payload,
    ).status_code == 403
    assert client.post(
        f"/api/v1/purchase-orders/{po_a['id']}/returns",
        headers=receiver, json={"reason": "revoked",
                               "lines": [{"purchase_order_line_id": line_a, "quantity": "1"}]},
    ).status_code == 403
