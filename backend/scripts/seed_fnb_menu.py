"""Idempotent seed for the verified Hidden Oasis sellable menu.

This seed intentionally contains only entries whose current selling price has been
verified. It does not import the legacy Kintoz catalogue wholesale.

Run from backend/ with the production environment loaded:
    .venv/bin/python scripts/seed_fnb_menu.py
"""
from __future__ import annotations

import hashlib
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.models.menu import MenuItem, MenuVariant

CATALOG = [
    # Packaging sold through POS.
    {"name":"Paper Box for Fries","category":"Packaging","prep_station":"none","variants":[("Regular","5.00")]},
    {"name":"Plastic Container for Pasta/Chicken","category":"Packaging","prep_station":"none","variants":[("Regular","15.00")]},
    {"name":"Box for Nachos","category":"Packaging","prep_station":"none","variants":[("Regular","50.00")]},

    # Current pizza range. Both current sizes are explicitly Thin Crust.
    {"name":"Hawaiian","category":"Pizza","prep_station":"kitchen","variants":[('Thin Crust 9"',"325.00"),('Thin Crust 12"',"445.00")]},
    {"name":"Pepperoni","category":"Pizza","prep_station":"kitchen","variants":[('Thin Crust 9"',"325.00"),('Thin Crust 12"',"445.00")]},
    {"name":"Garden Veggie","category":"Pizza","prep_station":"kitchen","variants":[('Thin Crust 9"',"295.00"),('Thin Crust 12"',"425.00")]},
    {"name":"Oasis Special","category":"Pizza","prep_station":"kitchen","variants":[('Thin Crust 9"',"355.00"),('Thin Crust 12"',"485.00")]},
    {"name":"Four Cheese","category":"Pizza","prep_station":"kitchen","variants":[('Thin Crust 9"',"375.00"),('Thin Crust 12"',"505.00")]},
]

def identity(item_name: str, variant_name: str) -> tuple[str, str]:
    # Stable new identifiers: reruns produce the same SKU/barcode.
    digest = hashlib.sha256(f"hidden-oasis|{item_name}|{variant_name}".encode()).hexdigest()
    number = str(int(digest[:15], 16)).zfill(18)
    return "HO-" + digest[:10].upper(), "20" + number[-10:]

def main() -> None:
    db = SessionLocal()
    created_items = updated_items = created_variants = updated_variants = 0
    try:
        for item_order, row in enumerate(CATALOG):
            item = db.scalar(
                select(MenuItem)
                .where(MenuItem.name == row["name"], MenuItem.category == row["category"])
                .options(selectinload(MenuItem.variants))
            )
            if item is None:
                item = MenuItem(
                    name=row["name"], display_name=row["name"], category=row["category"],
                    prep_station=row["prep_station"], sort_order=item_order,
                    is_active=True, pos_visible=True,
                )
                db.add(item)
                db.flush()
                created_items += 1
            else:
                item.display_name = row["name"]
                item.prep_station = row["prep_station"]
                item.sort_order = item_order
                item.is_active = True
                item.pos_visible = True
                updated_items += 1

            by_name = {v.name: v for v in item.variants}
            keep = set()
            for variant_order, (variant_name, price) in enumerate(row["variants"]):
                sku, barcode = identity(row["name"], variant_name)
                variant = by_name.get(variant_name)
                if variant is None:
                    variant = MenuVariant(menu_item_id=item.id)
                    db.add(variant)
                    created_variants += 1
                else:
                    updated_variants += 1
                variant.name = variant_name
                variant.sku = sku
                variant.barcode = barcode
                variant.price = Decimal(price)
                variant.with_drink_price = None
                variant.sort_order = variant_order
                variant.is_active = True
                keep.add(variant_name)

            # Do not delete unexpected production data. Only seed/update verified rows.
            db.flush()

        db.commit()
        print(
            f"Hidden Oasis menu seed complete: items created={created_items}, "
            f"items updated={updated_items}, variants created={created_variants}, "
            f"variants updated={updated_variants}."
        )
        print(f"Verified catalogue rows: {len(CATALOG)} items / {sum(len(x['variants']) for x in CATALOG)} variants.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
