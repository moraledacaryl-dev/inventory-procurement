"""Group C: prevent reporting query counts from growing with displayed records.

Tests create synthetic catalogue/PO/recipe data in the isolated test database;
there are no production transactions or external integrations.
"""
from decimal import Decimal

from sqlalchemy import event, select

from app.db.session import SessionLocal, engine
from app.models.procurement import PurchaseOrder, PurchaseOrderLine, Supplier
from app.models.production import Recipe
from app.models.user import User
from tests.test_inventory import login, setup_master
from tests.test_pos_sync import seed_mapping


def count_matching_queries(operation, needle: str):
    seen = []

    def inspect(_connection, _cursor, statement, _params, _context, _many):
        if needle.lower() in statement.lower():
            seen.append(statement)

    event.listen(engine, "before_cursor_execute", inspect)
    try:
        result = operation()
    finally:
        event.remove(engine, "before_cursor_execute", inspect)
    return result, seen


def test_dashboard_recent_po_totals_are_correct_with_one_batched_lines_query(client):
    headers = login(client)
    item, location, _ = setup_master(client, headers)
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        supplier = Supplier(code="C-PERF-SUP", name="Performance test supplier")
        db.add(supplier)
        db.flush()
        for index in range(35):
            po = PurchaseOrder(
                purchase_order_number=f"GC-PO-{index:04d}",
                supplier_id=supplier.id,
                delivery_location_id=location["id"],
                status="draft",
                created_by_user_id=owner.id,
            )
            db.add(po)
            db.flush()
            db.add_all([
                PurchaseOrderLine(
                    purchase_order_id=po.id, item_id=item["id"],
                    ordered_quantity=Decimal("2"), unit_price=Decimal("17.25"),
                ),
                PurchaseOrderLine(
                    purchase_order_id=po.id, item_id=item["id"],
                    ordered_quantity=Decimal("3"), unit_price=Decimal("7.50"),
                ),
            ])
        db.commit()

    response, statements = count_matching_queries(
        lambda: client.get("/api/v1/dashboard/summary", headers=headers),
        "FROM purchase_order_lines",
    )
    assert response.status_code == 200, response.text
    recent = response.json()["recent_purchase_orders"]
    assert len(recent) == 5
    assert all(Decimal(row["total"]) == Decimal("57.00") for row in recent)
    assert response.json()["metrics"]["pending_purchase_orders"] == 35
    assert response.json()["metrics"]["overdue_purchase_orders"] == 0
    assert len(statements) <= 1, f"Expected one aggregate PO-lines query, got {len(statements)}"


def test_pos_workspace_batch_loads_distinct_recipe_statuses_in_one_query(client):
    headers = login(client)
    location, ingredient, recipe, mapping = seed_mapping(client, headers)
    for index in range(12):
        created = client.post("/api/v1/recipes", headers=headers, json={
            "code": f"GC-RECIPE-{index:03d}",
            "name": f"Group C recipe {index}",
            "output_item_id": recipe["output_item_id"],
            "yield_quantity": 1,
            "lines": [{
                "ingredient_item_id": ingredient["id"],
                "quantity": 1,
                "waste_factor": 0,
                "optional": False,
            }],
        })
        assert created.status_code == 201, created.text
        with SessionLocal() as db:
            db.get(Recipe, created.json()["id"]).status = "approved"
            db.commit()
        link = client.post("/api/v1/pos-mappings", headers=headers, json={
            "pos_system": "hidden-oasis-pos",
            "external_product_id": f"GC-ITEM-{index:03d}",
            "recipe_id": created.json()["id"],
            "location_id": location["id"],
        })
        assert link.status_code == 201, link.text

    response, statements = count_matching_queries(
        lambda: client.get("/api/v1/integrations/pos/workspace", headers=headers),
        "FROM recipes",
    )
    assert response.status_code == 200, response.text
    assert response.json()["summary"]["mapping_count"] == 13
    assert response.json()["summary"]["stale_mapping_count"] == 0
    assert all(row["healthy"] for row in response.json()["mappings"])
    assert len(statements) <= 1, f"Expected batched recipe lookup, got {len(statements)}"
