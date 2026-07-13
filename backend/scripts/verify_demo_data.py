import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from app.db.session import SessionLocal, engine
from app.models.inventory import Category, Item, Location, UnitOfMeasure
from app.models.procurement import Supplier

EXPECTED = {
    "categories": 2,
    "units": 3,
    "locations": 4,
    "items": 5,
    "suppliers": 2,
}


def count_rows(db, model) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def main() -> None:
    if engine.dialect.name != "postgresql":
        raise SystemExit(f"PostgreSQL verification requires PostgreSQL, got {engine.dialect.name}")

    with SessionLocal() as db:
        actual = {
            "categories": count_rows(db, Category),
            "units": count_rows(db, UnitOfMeasure),
            "locations": count_rows(db, Location),
            "items": count_rows(db, Item),
            "suppliers": count_rows(db, Supplier),
        }
        if actual != EXPECTED:
            raise SystemExit(f"Demo-data counts changed during migration: expected={EXPECTED}, actual={actual}")

        coffee = db.scalar(select(Item).where(Item.sku == "COFFEE-BEAN"))
        if coffee is None:
            raise SystemExit("COFFEE-BEAN disappeared during migration")
        if Decimal(coffee.minimum_stock) != Decimal("2"):
            raise SystemExit(f"COFFEE-BEAN minimum stock changed: {coffee.minimum_stock}")
        if Decimal(coffee.standard_cost) != Decimal("650"):
            raise SystemExit(f"COFFEE-BEAN standard cost changed: {coffee.standard_cost}")

    print("PostgreSQL demo-data migration verification passed.")


if __name__ == "__main__":
    main()
