"""Group A: deterministic stock locks, rollback integrity and concurrent postings."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal, engine
from app.models.inventory import StockBalance, StockDocument, StockMovement
from app.models.operations import IntegrationEvent
from app.models.user import User
from app.services import inventory as stock_service


def auth(client):
    response = client.post("/api/v1/auth/login", json={
        "email": "owner@example.com", "password": "password123",
    })
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create(client, path, headers, payload):
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == 201, (path, response.text)
    return response.json()


def fixtures(client):
    headers = auth(client)
    category = create(client, "/api/v1/categories", headers, {"name": "Group A concurrency"})
    unit = create(client, "/api/v1/units", headers, {
        "code": "GAA", "name": "Group A counted items",
    })
    locations = [
        create(client, "/api/v1/locations", headers, {
            "code": code, "name": code,
        })["id"] for code in ["GROUP-A-A", "GROUP-A-B"]
    ]
    items = [
        create(client, "/api/v1/items", headers, {
            "sku": code, "name": code, "category_id": category["id"],
            "base_unit_id": unit["id"], "standard_cost": "10",
        })["id"] for code in ["GROUP-A-ONE", "GROUP-A-TWO"]
    ]
    for location in locations:
        create(client, "/api/v1/stock/receipts", headers, {
            "location_id": location, "lines": [
                {"item_id": item, "quantity": "100", "unit_cost": "10"}
                for item in items
            ],
        })
    with SessionLocal() as db:
        owner_id = db.scalar(select(User.id).where(User.email == "owner@example.com"))
    return owner_id, items, locations


def test_transfer_acquires_each_balance_once_in_stable_order(client, monkeypatch):
    owner, items, locations = fixtures(client)
    first, second = sorted(items)
    source, destination = locations
    recorded = []
    actual = stock_service._balance

    def trace(db, item_id, location_id):
        recorded.append((item_id, location_id))
        return actual(db, item_id, location_id)

    monkeypatch.setattr(stock_service, "_balance", trace)
    # Deliberately reverse items in request order and include source-cost
    # lookups. Both transfer endpoints must lock the same canonical keys.
    entries = stock_service.transfer_entries(
        source, destination,
        [type("Line", (), {"item_id": item, "quantity": Decimal("2"),
                           "unit_cost": Decimal("0"), "reason": None})()
         for item in (second, first)],
    )
    with SessionLocal() as db:
        doc = stock_service.post_document(
            db, kind="transfer", actor_id=owner, entries=entries,
            reference="LOCK-ORDER-GROUP-A",
        )
        assert len(doc.movements) == 4
    assert recorded == sorted(set(recorded))
    assert set(recorded) == {
        (item, location) for item in items for location in locations
    }


def test_invalid_second_stock_line_rolls_back_everything(client):
    owner, items, locations = fixtures(client)
    source = locations[0]
    with SessionLocal() as db:
        before = {
            row.item_id: Decimal(row.quantity)
            for row in db.scalars(select(StockBalance).where(
                StockBalance.location_id == source,
            )).all()
        }
        documents_before = len(db.scalars(select(StockDocument)).all())
        events_before = len(db.scalars(select(IntegrationEvent)).all())
    # First line valid, second would take inventory negative. Entire
    # transaction must roll back, including source events.
    response = client.post("/api/v1/stock/issues", headers=auth(client), json={
        "location_id": source,
        "lines": [
            {"item_id": items[0], "quantity": "2"},
            {"item_id": items[1], "quantity": "101"},
        ],
    })
    assert response.status_code == 409, response.text
    with SessionLocal() as db:
        after = {
            row.item_id: Decimal(row.quantity)
            for row in db.scalars(select(StockBalance).where(
                StockBalance.location_id == source,
            )).all()
        }
        assert after == before
        assert len(db.scalars(select(StockDocument)).all()) == documents_before
        assert len(db.scalars(select(IntegrationEvent)).all()) == events_before


def test_concurrent_opposite_direction_stock_documents_do_not_deadlock(client):
    if engine.dialect.name != "postgresql":
        pytest.skip("Concurrency/deadlock regression requires PostgreSQL")
    owner, items, locations = fixtures(client)
    a, b = locations
    barrier = Barrier(2)

    def transfer(kind, source, destination):
        # Different document-type sequences expose competing lock orders.
        lines = [
            {"item_id": item, "location_id": source,
             "quantity": Decimal("-4"), "unit_cost": Decimal("0"),
             "reason": "Group A out"}
            for item in items
        ] + [
            {"item_id": item, "location_id": destination,
             "quantity": Decimal("4"), "unit_cost": Decimal("0"),
             "cost_from_location_id": source, "reason": "Group A in"}
            for item in items
        ]
        barrier.wait(timeout=10)
        with SessionLocal() as db:
            result = stock_service.post_document(
                db, kind=kind, actor_id=owner,
                entries=lines, reference=kind,
            )
            return result.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        left = pool.submit(transfer, "concurrent_a", a, b)
        right = pool.submit(transfer, "concurrent_b", b, a)
        assert left.result(timeout=20) != right.result(timeout=20)

    with SessionLocal() as db:
        for location in locations:
            balances = db.scalars(select(StockBalance).where(
                StockBalance.location_id == location,
                StockBalance.item_id.in_(items),
            )).all()
            assert len(balances) == 2
            assert all(Decimal(row.quantity) == Decimal("100") for row in balances)
        recorded = db.scalars(select(StockDocument).where(
            StockDocument.document_type.in_(["concurrent_a", "concurrent_b"]),
        )).all()
        assert len(recorded) == 2
        assert len(db.scalars(select(StockMovement).where(
            StockMovement.document_id.in_([row.id for row in recorded]),
        )).all()) == 8
        assert len(db.scalars(select(IntegrationEvent).where(
            IntegrationEvent.aggregate_id.in_([row.id for row in recorded]),
            IntegrationEvent.destination_system == "accounting",
        )).all()) == 2
