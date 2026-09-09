import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.inventory import Category, Item, UnitOfMeasure
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
        ]
        for sku, name, category_id, unit_id, minimum, cost in definitions:
            item = db.scalar(select(Item).where(Item.sku == sku))
            if item is None:
                db.add(
                    Item(
                        sku=sku,
                        name=name,
                        category_id=category_id,
                        base_unit_id=unit_id,
                        minimum_stock=minimum,
                        standard_cost=cost,
                    )
                )
        db.commit()


def seed_scenario_stock() -> None:
    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": VISUAL_USERS["owner"], "password": VISUAL_PASSWORD},
    )
    login.raise_for_status()
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    items = {row["sku"]: row for row in client.get("/api/v1/items", headers=headers).json()}
    locations = {row["code"]: row for row in client.get("/api/v1/locations", headers=headers).json()}
    main_location = locations["MAIN"]

    # Purposefully creates a mixture of healthy and low stock. Items with no receipt
    # remain zero-stock so dashboard/exception states are represented as well.
    receipt = client.post(
        "/api/v1/stock/receipts",
        headers=headers,
        json={
            "location_id": main_location["id"],
            "reference": "VISUAL-QA-OPENING",
            "notes": "Isolated screenshot-certification scenario stock",
            "idempotency_key": "visual-qa-opening-stock-v1",
            "lines": [
                {"item_id": items["CHICKEN-BREAST"]["id"], "quantity": "3", "unit_cost": "220", "reason": "Visual QA low-stock scenario"},
                {"item_id": items["BATH-TOWEL"]["id"], "quantity": "40", "unit_cost": "320", "reason": "Visual QA healthy-stock scenario"},
                {"item_id": items["DISHWASH-LIQ"]["id"], "quantity": "2", "unit_cost": "155", "reason": "Visual QA low-stock scenario"},
            ],
        },
    )
    if receipt.status_code not in {200, 201, 409}:
        raise SystemExit(f"Visual scenario receipt failed: {receipt.status_code} {receipt.text}")


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
    print("Visual acceptance dataset ready.")
    for role, email in VISUAL_USERS.items():
        print(f"  {role}: {email}")


if __name__ == "__main__":
    main()
