"""Enrich an existing, isolated visual-acceptance database for UI previews.

Usage: python scripts/prepare_ui_demo.py /tmp/inventory-visual-demo.db
Run seed_visual_acceptance.py first. This refuses production database paths.
"""
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

database = Path(sys.argv[1]).resolve() if len(sys.argv) == 2 else None
if not database or database.parent != Path("/tmp").resolve() or not database.name.startswith("inventory-visual-") or database.suffix != ".db" or not database.is_file():
    raise SystemExit("Use an existing /tmp/inventory-visual-*.db sample database.")
with sqlite3.connect(database) as source, sqlite3.connect(str(database) + ".before-polish") as backup:
    source.backup(backup)
os.environ["DATABASE_URL"] = f"sqlite:///{database}"
os.environ.setdefault("JWT_SECRET", "local-inventory-visual-demo-only-secret")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.classification import ItemWorkspaceAssignment, OperationalDimension
from app.models.inventory import Item, Location, StockDocument
from app.models.pos_rules import PosModifierTemplate, PosPricingRule
from app.models.property import HotelParLine, HotelParProfile, PropertyBalance, PropertyMovement
from app.models.user import User
from scripts.seed_fnb_menu import main as seed_menu

seed_menu()
with SessionLocal() as db:
    dimensions = {(row.dimension_type, row.code): row for row in db.scalars(select(OperationalDimension))}
    locations = {row.code: row for row in db.scalars(select(Location))}
    owner = db.scalar(select(User).where(User.email == "demo@example.com"))
    if not owner:
        raise SystemExit("Demo owner is missing. Seed the isolated demo first.")
    mapping = {
        "COFFEE-BEAN": "beverage-ingredient", "MILK-FRESH": "beverage-ingredient",
        "SUGAR-WHITE": "ingredient", "CHICKEN-BREAST": "ingredient", "EGGS-TRAY": "ingredient",
        "BREAKFAST-PLATE": "finished-fnb-product", "CLEANER-ALL": "housekeeping-supply",
        "DISHWASH-LIQ": "housekeeping-supply", "TISSUE-ROLL": "guest-amenity",
        "BATH-TOWEL": "linen", "AC-SPLIT-15HP": "equipment",
        "FILTER-AC": "maintenance-supply", "POOL-CHLORINE": "maintenance-supply",
    }
    items = {row.sku: row for row in db.scalars(select(Item))}
    for sku, type_code in mapping.items():
        item = items[sku]
        kind = dimensions["item_type", type_code]
        item.item_type_id = kind.id
        item.record_class_id = kind.parent_id
        item.primary_workspace_id = kind.workspace_id
        item.default_location_id = locations["HOUSE" if type_code in ("linen", "guest-amenity", "housekeeping-supply") else "MAIN"].id
        assignment = db.scalar(select(ItemWorkspaceAssignment).where(ItemWorkspaceAssignment.item_id == item.id, ItemWorkspaceAssignment.workspace_id == kind.workspace_id))
        if not assignment:
            db.add(ItemWorkspaceAssignment(item_id=item.id, workspace_id=kind.workspace_id, is_primary=True))
    # Distribute the sample opening documents over the preview period.
    for document in db.scalars(select(StockDocument)):
        if document.reference in ("ACCEPTANCE-OPENING", "VISUAL-QA-OPENING"):
            days = 27 if document.reference == "ACCEPTANCE-OPENING" else 13
            document.posted_at = datetime.now(timezone.utc) - timedelta(days=days)
            for movement in document.movements:
                movement.created_at = document.posted_at
                movement.reason = "Opening stock" if days == 27 else "Supply delivery"
    towel = items["BATH-TOWEL"]
    available = dimensions["condition_status", "available"]
    house = locations["HOUSE"]
    if not db.scalar(select(PropertyBalance).where(PropertyBalance.item_id == towel.id)):
        db.add(PropertyBalance(item_id=towel.id, location_id=house.id, condition_id=available.id, quantity=40))
        db.add(PropertyMovement(movement_number="DEMO-LINEN-001", item_id=towel.id, quantity=40, destination_location_id=house.id, destination_condition_id=available.id, movement_reason_id=dimensions["movement_reason", "receipt"].id, reference="Opening linen stock", created_by_user_id=owner.id))
    profile = db.scalar(select(HotelParProfile).where(HotelParProfile.code == "DEMO-DELUXE"))
    if not profile:
        profile = HotelParProfile(code="DEMO-DELUXE", name="Deluxe room", location_id=house.id)
        db.add(profile)
        db.flush()
        db.add(HotelParLine(profile_id=profile.id, item_id=towel.id, par_quantity=4))
    if not db.scalar(select(PosPricingRule).where(PosPricingRule.name == "Breakfast with a drink")):
        db.add(PosPricingRule(name="Breakfast with a drink", qualifier_tag="drink", target_tag="breakfast", priority=100))
    if not db.scalar(select(PosModifierTemplate).where(PosModifierTemplate.name == "Coffee preferences")):
        db.add(PosModifierTemplate(name="Coffee preferences", config_json='{"id":"coffee-preferences","label":"Milk","mode":"single","options":[{"label":"Regular","price_delta":0},{"label":"Oat milk","price_delta":35}]}'))
    db.commit()
print("Sample catalogue, menu, linen, selling rules and valuation history prepared.")
