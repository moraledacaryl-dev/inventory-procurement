import os
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.assets import DepreciationRun, FixedAsset
from app.models.classification import OperationalDimension
from app.models.inventory import Category, CountLine, CountSession, Item, Location, StockDocument, UnitOfMeasure
from app.models.inventory_operations import InventoryLot, LotBalance, TransferOrder, TransferOrderLine
from app.models.operations import IntegrationEvent, Notification
from app.models.pass5 import MaintenancePlan, WorkOrder, WorkOrderPart
from app.models.procurement import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequisition,
    PurchaseRequisitionLine,
    Supplier,
    SupplierItem,
)
from app.models.production import PosProductMapping, ProductionBatch, Recipe, RecipeLine
from app.models.staff_meals import StaffMeal, StaffMealLine
from app.models.user import User
from scripts.seed_acceptance import main as seed_acceptance

VISUAL_PASSWORD = os.getenv("E2E_VISUAL_PASSWORD", "visual-acceptance-password")
VISUAL_USERS = {
    "owner": "visual-owner@example.com",
    "inventory_manager": "visual-inventory-manager@example.com",
    "procurement_officer": "visual-procurement@example.com",
    "receiver": "visual-receiver@example.com",
    "counter": "visual-counter@example.com",
    "viewer": "visual-viewer@example.com",
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def get_or_create(db, model, lookup: dict, defaults: dict | None = None):
    row = db.scalar(select(model).filter_by(**lookup))
    if row is not None:
        return row
    row = model(**lookup, **(defaults or {}))
    db.add(row)
    db.flush()
    return row


def ensure_visual_users() -> None:
    with SessionLocal() as db:
        for role, email in VISUAL_USERS.items():
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    email=email,
                    full_name=f"Visual QA {role.replace('_', ' ').title()}",
                    password_hash=hash_password(VISUAL_PASSWORD),
                    role=role,
                    is_active=True,
                )
                db.add(user)
            else:
                user.full_name = f"Visual QA {role.replace('_', ' ').title()}"
                user.password_hash = hash_password(VISUAL_PASSWORD)
                user.role = role
                user.is_active = True
        db.commit()


def ensure_visual_items() -> None:
    with SessionLocal() as db:
        food = db.scalar(select(Category).where(Category.name == "Food & Beverage"))
        housekeeping = db.scalar(select(Category).where(Category.name == "Housekeeping"))
        each = db.scalar(select(UnitOfMeasure).where(UnitOfMeasure.code == "EA"))
        kg = db.scalar(select(UnitOfMeasure).where(UnitOfMeasure.code == "KG"))
        liter = db.scalar(select(UnitOfMeasure).where(UnitOfMeasure.code == "L"))
        if not all((food, housekeeping, each, kg, liter)):
            raise SystemExit("Base acceptance masters are missing")

        definitions = [
            ("CHICKEN-BREAST", "Chicken Breast", food.id, kg.id, "10", "220"),
            ("EGGS-TRAY", "Eggs - Tray of 30", food.id, each.id, "5", "265"),
            ("POOL-CHLORINE", "Pool Chlorine", housekeeping.id, kg.id, "3", "1850"),
            ("BATH-TOWEL", "Bath Towel - White", housekeeping.id, each.id, "20", "320"),
            ("DISHWASH-LIQ", "Dishwashing Liquid", housekeeping.id, liter.id, "4", "155"),
            ("BREAKFAST-PLATE", "Hidden Oasis Breakfast Plate", food.id, each.id, "0", "145"),
            ("AC-SPLIT-15HP", "Split-Type Air Conditioner 1.5 HP", housekeeping.id, each.id, "0", "28500"),
            ("FILTER-AC", "Air Conditioner Filter", housekeeping.id, each.id, "2", "650"),
        ]
        for sku, name, category_id, unit_id, minimum, cost in definitions:
            item = db.scalar(select(Item).where(Item.sku == sku))
            if item is None:
                db.add(Item(sku=sku, name=name, category_id=category_id, base_unit_id=unit_id, minimum_stock=minimum, standard_cost=cost))
        db.commit()


def seed_scenario_stock() -> None:
    client = TestClient(app)
    login = client.post("/api/v1/auth/login", json={"email": VISUAL_USERS["owner"], "password": VISUAL_PASSWORD})
    login.raise_for_status()
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    items = {row["sku"]: row for row in client.get("/api/v1/items", headers=headers).json()}
    locations = {row["code"]: row for row in client.get("/api/v1/locations", headers=headers).json()}
    main_location = locations["MAIN"]
    receipt = client.post(
        "/api/v1/stock/receipts",
        headers=headers,
        json={
            "location_id": main_location["id"],
            "reference": "VISUAL-QA-OPENING",
            "notes": "Isolated screenshot-certification scenario stock",
            "idempotency_key": "visual-qa-opening-stock-v2",
            "lines": [
                {"item_id": items["CHICKEN-BREAST"]["id"], "quantity": "3", "unit_cost": "220", "reason": "Visual QA low-stock scenario"},
                {"item_id": items["BATH-TOWEL"]["id"], "quantity": "40", "unit_cost": "320", "reason": "Visual QA healthy-stock scenario"},
                {"item_id": items["DISHWASH-LIQ"]["id"], "quantity": "2", "unit_cost": "155", "reason": "Visual QA low-stock scenario"},
                {"item_id": items["FILTER-AC"]["id"], "quantity": "4", "unit_cost": "650", "reason": "Visual QA maintenance spare"},
            ],
        },
    )
    if receipt.status_code not in {200, 201, 409}:
        raise SystemExit(f"Visual scenario receipt failed: {receipt.status_code} {receipt.text}")


def seed_operational_scenarios() -> None:
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == VISUAL_USERS["owner"]))
        receiver = db.scalar(select(User).where(User.email == VISUAL_USERS["receiver"]))
        counter = db.scalar(select(User).where(User.email == VISUAL_USERS["counter"]))
        items = {x.sku: x for x in db.scalars(select(Item)).all()}
        locations = {x.code: x for x in db.scalars(select(Location)).all()}
        suppliers = {x.code: x for x in db.scalars(select(Supplier)).all()}
        if not owner or not receiver or not counter:
            raise SystemExit("Visual users are missing")
        main = locations["MAIN"]
        kitchen = locations["KITCHEN"]
        house = locations["HOUSE"]
        cafe_supplier = suppliers["CAFE-SUPPLY"]
        house_supplier = suppliers["HOUSE-SUPPLY"]

        cafe_supplier.contact_name = "Maria Santos"
        cafe_supplier.email = "orders@cafesupply.test"
        cafe_supplier.phone = "+63 917 555 0101"
        cafe_supplier.address = "National Highway, Gingoog City, Misamis Oriental"
        house_supplier.contact_name = "Ramon Villanueva"
        house_supplier.phone = "+63 917 555 0202"
        house_supplier.address = "Cagayan de Oro City, Misamis Oriental"
        for supplier, sku, price, lead, preferred in [
            (cafe_supplier, "CHICKEN-BREAST", "215", 2, True),
            (cafe_supplier, "EGGS-TRAY", "258", 2, True),
            (house_supplier, "BATH-TOWEL", "305", 5, True),
            (house_supplier, "POOL-CHLORINE", "1795", 4, True),
        ]:
            get_or_create(db, SupplierItem, {"supplier_id": supplier.id, "item_id": items[sku].id}, {"last_price": Decimal(price), "lead_time_days": lead, "minimum_order_quantity": Decimal("1"), "is_preferred": preferred})

        req_open = get_or_create(db, PurchaseRequisition, {"requisition_number": "VR-2026-001"}, {
            "department": "Cafe Kitchen", "needed_by": date.today() + timedelta(days=2), "justification": "Weekend breakfast occupancy forecast", "status": "submitted", "requested_by_user_id": owner.id,
        })
        if not req_open.lines:
            req_open.lines.extend([
                PurchaseRequisitionLine(item_id=items["CHICKEN-BREAST"].id, quantity=Decimal("18"), estimated_unit_cost=Decimal("220"), notes="Breakfast and cafe production"),
                PurchaseRequisitionLine(item_id=items["EGGS-TRAY"].id, quantity=Decimal("6"), estimated_unit_cost=Decimal("265"), notes="Breakfast service"),
            ])
        req_approved = get_or_create(db, PurchaseRequisition, {"requisition_number": "VR-2026-002"}, {
            "department": "Housekeeping", "needed_by": date.today() + timedelta(days=7), "justification": "Par replenishment for family rooms", "status": "approved", "requested_by_user_id": owner.id, "approved_by_user_id": owner.id, "approved_at": now() - timedelta(days=1),
        })
        if not req_approved.lines:
            req_approved.lines.append(PurchaseRequisitionLine(item_id=items["BATH-TOWEL"].id, quantity=Decimal("24"), estimated_unit_cost=Decimal("320"), notes="Replace stained and worn towels"))

        po_defs = [
            ("VPO-2026-001", cafe_supplier, req_open, "approved", date.today() + timedelta(days=2), "Breakfast replenishment", [("CHICKEN-BREAST", "18", "0", "215"), ("EGGS-TRAY", "6", "0", "258")]),
            ("VPO-2026-002", house_supplier, req_approved, "partially_received", date.today() - timedelta(days=2), "Partial delivery; towel balance outstanding", [("BATH-TOWEL", "24", "12", "305"), ("POOL-CHLORINE", "4", "4", "1795")]),
            ("VPO-2026-003", cafe_supplier, None, "approved", date.today() - timedelta(days=5), "Overdue emergency pantry replenishment", [("SUGAR-WHITE", "12", "0", "72")]),
            ("VPO-2026-004", house_supplier, None, "received", date.today() - timedelta(days=10), "Completed housekeeping replenishment", [("CLEANER-ALL", "10", "10", "118")]),
        ]
        pos: dict[str, PurchaseOrder] = {}
        for number, supplier, req, status, due, notes, lines in po_defs:
            po = get_or_create(db, PurchaseOrder, {"purchase_order_number": number}, {
                "supplier_id": supplier.id, "requisition_id": req.id if req else None, "delivery_location_id": main.id, "expected_delivery_date": due, "status": status, "notes": notes, "created_by_user_id": owner.id, "approved_by_user_id": owner.id if status != "draft" else None, "approved_at": now() - timedelta(days=3) if status != "draft" else None,
            })
            if not po.lines:
                for sku, ordered, received, price in lines:
                    po.lines.append(PurchaseOrderLine(item_id=items[sku].id, ordered_quantity=Decimal(ordered), received_quantity=Decimal(received), returned_quantity=Decimal("0"), unit_price=Decimal(price)))
            pos[number] = po
        db.flush()

        partial_po = pos["VPO-2026-002"]
        if db.scalar(select(GoodsReceipt).where(GoodsReceipt.goods_receipt_number == "VGR-2026-001")) is None:
            doc = StockDocument(document_number="VGR-STOCK-001", document_type="receipt", status="posted", reference="DEL-88931", notes="Visual QA partial receipt", posted_by_user_id=receiver.id, posted_at=now() - timedelta(days=1))
            db.add(doc); db.flush()
            gr = GoodsReceipt(goods_receipt_number="VGR-2026-001", purchase_order_id=partial_po.id, stock_document_id=doc.id, delivery_reference="DEL-88931", received_by_user_id=receiver.id, received_at=now() - timedelta(days=1), notes="One towel carton outstanding; chlorine complete")
            db.add(gr); db.flush()
            for line in partial_po.lines:
                received = Decimal("12") if line.item_id == items["BATH-TOWEL"].id else Decimal("4")
                gr.lines.append(GoodsReceiptLine(purchase_order_line_id=line.id, item_id=line.item_id, received_quantity=received, accepted_quantity=received, rejected_quantity=Decimal("0"), unit_cost=line.unit_price))

        count_defs = [
            ("VCOUNT-001", main, "open", "Routine storeroom cycle count", True, [("CHICKEN-BREAST", "3", None, None)]),
            ("VCOUNT-002", house, "submitted", "Towel variance requires review", True, [("BATH-TOWEL", "40", "36", "4 towels issued to rooms before posting")]),
            ("VCOUNT-003", kitchen, "approved", "Kitchen close count approved", False, [("SUGAR-WHITE", "15", "14.5", "0.5 kg usage timing difference")]),
        ]
        for number, loc, status, notes, blind, lines in count_defs:
            session = get_or_create(db, CountSession, {"count_number": number}, {"location_id": loc.id, "status": status, "notes": notes, "blind_count": blind, "approval_threshold": Decimal("2"), "created_by_user_id": counter.id, "approved_by_user_id": owner.id if status == "approved" else None, "approved_at": now() if status == "approved" else None})
            if not session.lines:
                for sku, system_qty, counted_qty, note in lines:
                    session.lines.append(CountLine(item_id=items[sku].id, system_quantity=Decimal(system_qty), counted_quantity=Decimal(counted_qty) if counted_qty is not None else None, note=note))

        transfer_defs = [
            ("VTR-001", main, kitchen, "draft", "Prepare breakfast stock", None, None),
            ("VTR-002", main, house, "dispatched", "Housekeeping restock in transit", now() - timedelta(hours=3), None),
            ("VTR-003", main, kitchen, "received", "Completed kitchen replenishment", now() - timedelta(days=2), now() - timedelta(days=2, hours=-1)),
        ]
        for number, source, destination, status, notes, dispatched_at, received_at in transfer_defs:
            transfer = get_or_create(db, TransferOrder, {"transfer_number": number}, {"source_location_id": source.id, "destination_location_id": destination.id, "status": status, "notes": notes, "created_by_user_id": owner.id, "dispatched_by_user_id": owner.id if dispatched_at else None, "received_by_user_id": receiver.id if received_at else None, "dispatched_at": dispatched_at, "received_at": received_at})
            if not transfer.lines:
                transfer.lines.append(TransferOrderLine(item_id=items["BATH-TOWEL"].id if destination == house else items["SUGAR-WHITE"].id, quantity=Decimal("8") if destination == house else Decimal("3")))

        recipe = get_or_create(db, Recipe, {"code": "REC-BREAKFAST-001"}, {"name": "Hidden Oasis Breakfast Plate", "output_item_id": items["BREAKFAST-PLATE"].id, "yield_quantity": Decimal("1"), "version": 1, "status": "approved", "notes": "Egg, chicken and pantry breakfast plate", "created_by_user_id": owner.id, "approved_by_user_id": owner.id, "approved_at": now() - timedelta(days=7)})
        if not recipe.lines:
            recipe.lines.extend([
                RecipeLine(ingredient_item_id=items["CHICKEN-BREAST"].id, quantity=Decimal("0.18"), waste_factor=Decimal("0.05"), optional=False),
                RecipeLine(ingredient_item_id=items["EGGS-TRAY"].id, quantity=Decimal("0.07"), waste_factor=Decimal("0"), optional=False),
                RecipeLine(ingredient_item_id=items["SUGAR-WHITE"].id, quantity=Decimal("0.01"), waste_factor=Decimal("0"), optional=True),
            ])
        for number, status, planned, actual, notes in [
            ("VBATCH-001", "planned", "25", None, "Tomorrow breakfast prep; chicken is currently short"),
            ("VBATCH-002", "in_progress", "18", None, "Breakfast prep underway"),
            ("VBATCH-003", "completed", "20", "19", "Completed with one-plate yield variance"),
        ]:
            get_or_create(db, ProductionBatch, {"batch_number": number}, {"recipe_id": recipe.id, "location_id": kitchen.id, "planned_quantity": Decimal(planned), "actual_quantity": Decimal(actual) if actual else None, "status": status, "notes": notes, "created_by_user_id": owner.id, "completed_by_user_id": owner.id if status == "completed" else None, "completed_at": now() - timedelta(days=1) if status == "completed" else None})
        get_or_create(db, PosProductMapping, {"pos_system": "hidden-oasis-pos", "external_product_id": "BREAKFAST-PLATE"}, {"recipe_id": recipe.id, "location_id": kitchen.id, "is_active": True})

        meal_doc = db.scalar(select(StockDocument).where(StockDocument.document_number == "VMEAL-STOCK-001"))
        if meal_doc is None:
            meal_doc = StockDocument(document_number="VMEAL-STOCK-001", document_type="staff_meal", status="posted", reference="VMEAL-001", notes="Visual QA staff meal", posted_by_user_id=owner.id, posted_at=now() - timedelta(hours=6))
            db.add(meal_doc); db.flush()
        if db.scalar(select(StaffMeal).where(StaffMeal.meal_number == "VMEAL-001")) is None:
            meal = StaffMeal(meal_number="VMEAL-001", meal_name="Chicken Adobo Staff Lunch", meal_period="lunch", servings=8, location_id=kitchen.id, notes="Staff meal for AM and PM shift handover", status="posted", posted_document_id=meal_doc.id, created_by_user_id=owner.id, created_at=now() - timedelta(hours=6))
            db.add(meal); db.flush()
            meal.lines.extend([
                StaffMealLine(line_number=1, item_id=items["CHICKEN-BREAST"].id, quantity=Decimal("1.5"), unit_cost=Decimal("220")),
                StaffMealLine(line_number=2, item_id=items["SUGAR-WHITE"].id, quantity=Decimal("0.08"), unit_cost=Decimal("75")),
            ])

        asset_class = get_or_create(db, OperationalDimension, {"dimension_type": "asset_class", "code": "HVAC"}, {"name": "HVAC Equipment", "description": "Air-conditioning and ventilation equipment", "behavior_key": "equipment", "settings": {}, "is_system": False, "is_active": True})
        dep_method = get_or_create(db, OperationalDimension, {"dimension_type": "depreciation_method", "code": "SL"}, {"name": "Straight Line", "description": "Straight-line depreciation", "behavior_key": "straight_line", "settings": {}, "is_system": True, "is_active": True})
        fixed_type = get_or_create(db, OperationalDimension, {"dimension_type": "item_type", "code": "FIXED-ASSET"}, {"name": "Fixed Asset", "description": "Capital equipment", "behavior_key": "fixed_asset", "settings": {}, "is_system": True, "is_active": True})
        items["AC-SPLIT-15HP"].item_type_id = fixed_type.id
        asset = get_or_create(db, FixedAsset, {"asset_tag": "HO-HVAC-003"}, {"item_id": items["AC-SPLIT-15HP"].id, "asset_class_id": asset_class.id, "depreciation_method_id": dep_method.id, "location_id": house.id, "custodian_user_id": owner.id, "serial_number": "AC15-2025-003", "model_number": "INV-15HP", "acquisition_date": date.today() - timedelta(days=420), "placed_in_service_date": date.today() - timedelta(days=410), "acquisition_cost": Decimal("28500"), "capitalized_cost": Decimal("1500"), "residual_value": Decimal("1500"), "useful_life_months": 60, "accumulated_depreciation": Decimal("6412.50"), "status": "active", "condition": "fair", "warranty_expiry": date.today() + timedelta(days=45), "notes": "Guestroom split-type unit; cooling performance under observation", "created_by_user_id": owner.id})
        plan = get_or_create(db, MaintenancePlan, {"code": "PM-HVAC-003"}, {"name": "Quarterly AC cleaning", "asset_id": asset.id, "interval_days": 90, "checklist": "Clean filters; inspect drain; check refrigerant pressure; test temperature drop", "assigned_user_id": owner.id, "next_due_date": date.today() - timedelta(days=3), "is_active": True})
        get_or_create(db, WorkOrder, {"work_order_number": "VMWO-001"}, {"asset_id": asset.id, "plan_id": plan.id, "title": "Guestroom AC cooling weak", "description": "Guest reported slower cooling during afternoon peak heat.", "priority": "high", "status": "open", "assigned_user_id": owner.id, "scheduled_date": date.today() + timedelta(days=1), "labor_cost": Decimal("0"), "external_cost": Decimal("0"), "downtime_hours": Decimal("0"), "created_by_user_id": owner.id})
        completed_wo = get_or_create(db, WorkOrder, {"work_order_number": "VMWO-002"}, {"asset_id": asset.id, "plan_id": plan.id, "title": "Quarterly preventive cleaning", "description": "Scheduled preventive maintenance", "priority": "normal", "status": "completed", "assigned_user_id": owner.id, "scheduled_date": date.today() - timedelta(days=90), "started_at": now() - timedelta(days=90, hours=2), "completed_at": now() - timedelta(days=90), "labor_cost": Decimal("500"), "external_cost": Decimal("0"), "downtime_hours": Decimal("1.5"), "completion_notes": "Filters washed and drain line cleared", "created_by_user_id": owner.id})
        if not completed_wo.parts:
            completed_wo.parts.append(WorkOrderPart(item_id=items["FILTER-AC"].id, quantity=Decimal("1"), unit_cost=Decimal("650")))
        get_or_create(db, DepreciationRun, {"period": date.today().strftime("%Y-%m")}, {"status": "draft", "total_amount": Decimal("475"), "created_by_user_id": owner.id})

        lot = get_or_create(db, InventoryLot, {"item_id": items["MILK-FRESH"].id, "lot_number": "MILK-SEP10-A"}, {"manufactured_date": date.today() - timedelta(days=3), "expiry_date": date.today() + timedelta(days=2), "supplier_id": cafe_supplier.id, "status": "active"})
        get_or_create(db, LotBalance, {"lot_id": lot.id, "location_id": kitchen.id}, {"quantity": Decimal("6")})

        for key, status, attempts, error in [
            ("visual-accounting-complete", "completed", 1, None),
            ("visual-ops-retry", "retry", 2, "Operations endpoint returned 503 during simulated QA window"),
            ("visual-accounting-failed", "failed", 4, "Accounting destination validation rejected simulated malformed cost center"),
        ]:
            get_or_create(db, IntegrationEvent, {"idempotency_key": key}, {"direction": "outbound", "source_system": "inventory-procurement", "destination_system": "accounting" if "accounting" in key else "operations-command-center", "event_type": "inventory.visual_qa", "aggregate_type": "visual_certification", "aggregate_id": key, "payload": {"scenario": key, "visual_only": True}, "status": status, "attempts": attempts, "max_attempts": 8, "last_error": error, "available_at": now(), "processed_at": now() - timedelta(minutes=30) if status == "completed" else None})

        for title, message, severity in [
            ("Low stock: Chicken Breast", "Main Storeroom is below the configured minimum for Chicken Breast.", "warning"),
            ("Overdue purchase order", "VPO-2026-003 is past its expected delivery date.", "critical"),
            ("Count variance awaiting review", "VCOUNT-002 has a four-unit towel variance.", "warning"),
        ]:
            if db.scalar(select(Notification).where(Notification.title == title)) is None:
                db.add(Notification(user_id=owner.id, title=title, message=message, severity=severity))

        db.commit()


def main() -> None:
    database_url = os.getenv("DATABASE_URL", "").lower()
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    if not any(marker in database_url for marker in ("e2e", "acceptance", "visual", "screenshot", "localhost", "127.0.0.1")):
        raise SystemExit("Refusing to seed a database that does not look isolated/test-only")

    seed_acceptance()
    ensure_visual_users()
    ensure_visual_items()
    seed_scenario_stock()
    seed_operational_scenarios()
    print("Visual acceptance dataset ready with enriched workflow scenarios.")
    for role, email in VISUAL_USERS.items():
        print(f"  {role}: {email}")


if __name__ == "__main__":
    main()
