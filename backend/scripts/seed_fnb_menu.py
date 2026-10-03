"""Idempotent seed of the current Hidden Oasis menu verified from photographed menu pages.

Unavailable/covered items and items without a visible current price are deliberately
excluded. Historical Kintoz codes are not reused.
"""
from __future__ import annotations
import hashlib
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db.session import SessionLocal
from app.models.menu import MenuItem, MenuVariant

def row(name, category, price, station="kitchen"):
    variants = price if isinstance(price, list) else [("Regular", price)]
    return {"name":name,"category":category,"prep_station":station,"variants":variants}

CATALOG = [
    # Packaging (previously verified)
    row("Paper Box for Fries","Packaging","5.00","none"),
    row("Plastic Container for Pasta/Chicken","Packaging","15.00","none"),
    row("Box for Nachos","Packaging","50.00","none"),

    # Pizza — current photographed menu
    row("Hawaiian","Pizza",[('Thin Crust 9"',"325.00"),('Thin Crust 12"',"445.00")]),
    row("Pepperoni","Pizza",[('Thin Crust 9"',"325.00"),('Thin Crust 12"',"445.00")]),
    row("Garden Veggie","Pizza",[('Thin Crust 9"',"295.00"),('Thin Crust 12"',"425.00")]),
    row("Oasis Special","Pizza",[('Thin Crust 9"',"355.00"),('Thin Crust 12"',"485.00")]),
    row("Four Cheese","Pizza",[('Thin Crust 9"',"375.00"),('Thin Crust 12"',"505.00")]),

    # Appetizers / quick bites
    row("Lumpiang Shanghai","Appetizers","295.00"),
    row("Croquettes","Appetizers","245.00"),
    row("Nachos","Appetizers","295.00"),
    row("Mozzarella Sticks","Appetizers","275.00"),
    row("Fries","Appetizers",[("Solo","59.00"),("Platter","110.00")]),
    row("Monte Cristo","Quick Bites","135.00"),

    # Main course
    row("Parmesan Chicken (Breast)","Main Course","280.00"),
    row("Fried Chicken","Main Course","225.00"),
    row("Salisbury Steak","Main Course","225.00"),
    row("Red Wine Braised Beef","Main Course","375.00"),
    row("Mushroom Pork Steak","Main Course","265.00"),
    row("Fish and Chips","Main Course","195.00"),
    row("Garlic Parmesan Wings","Chicken Wings",[("Solo","250.00"),("Platter","310.00")]),
    row("Buffalo Wings","Chicken Wings",[("Solo","250.00"),("Platter","310.00")]),
    row("Salted Egg Wings","Chicken Wings",[("Solo","250.00"),("Platter","310.00")]),
    row("Pork Sisig","Filipino Favorites","225.00"),
    row("Grilled Liempo","Filipino Favorites",[("Solo","220.00"),("Platter","650.00")]),
    row("Pancit Canton","Filipino Favorites","265.00"),
    row("Chop Suey","Filipino Favorites","245.00"),
    row("Caesar Salad","Salads","255.00"),
    row("Garden Salad","Salads","215.00"),
    row("Aglio Olio","Pasta","190.00"),
    row("Carbonara","Pasta","225.00"),
    row("Spaghetti Bolognese","Pasta","170.00"),
    row("Duo Cheese Burger","Burgers & Sandwiches","215.00"),
    row("Duo Mushroom Burger","Burgers & Sandwiches","230.00"),
    row("Hotdog Sandwich","Burgers & Sandwiches","125.00"),

    # All-day breakfast — only names/prices that remain visible on the current page
    row("French Toast","All-Day Breakfast","130.00"),
    row("Sunshine Toast","All-Day Breakfast","125.00"),
    row("Classic Pancakes","All-Day Breakfast","115.00"),
    row("Cheesy Mushroom Omelette","All-Day Breakfast","130.00"),

    # Hot coffee
    row("Americano","Hot Coffee","90.00","bar"),
    row("Cappuccino","Hot Coffee","110.00","bar"),
    row("Cafe Latte","Hot Coffee","115.00","bar"),
    row("Mocha Latte","Hot Coffee","125.00","bar"),
    row("Caramel Macchiato","Hot Coffee","125.00","bar"),
    row("French Vanilla Latte","Hot Coffee","125.00","bar"),
    row("Spanish Latte","Hot Coffee","130.00","bar"),
    row("Hazelnut","Hot Coffee","130.00","bar"),
    row("Brown Butter Latte","Hot Coffee","155.00","bar"),

    # Iced coffee M/L
    row("Americano","Iced Coffee",[("M","95.00"),("L","115.00")],"bar"),
    row("Cafe Latte","Iced Coffee",[("M","125.00"),("L","145.00")],"bar"),
    row("Mocha Latte","Iced Coffee",[("M","130.00"),("L","150.00")],"bar"),
    row("Caramel Macchiato","Iced Coffee",[("M","130.00"),("L","150.00")],"bar"),
    row("White Mocha Latte","Iced Coffee",[("M","130.00"),("L","150.00")],"bar"),
    row("French Vanilla Latte","Iced Coffee",[("M","130.00"),("L","150.00")],"bar"),
    row("Spanish Latte","Iced Coffee",[("M","135.00"),("L","155.00")],"bar"),
    row("Hazelnut","Iced Coffee",[("M","135.00"),("L","155.00")],"bar"),
    row("Butterscotch Latte","Iced Coffee",[("M","135.00"),("L","155.00")],"bar"),
    row("Dirty Matcha Latte","Iced Coffee",[("M","140.00"),("L","160.00")],"bar"),
    row("Sea Salt Latte","Iced Coffee",[("M","140.00"),("L","160.00")],"bar"),
    row("Brown Butter Latte","Iced Coffee",[("M","160.00"),("L","180.00")],"bar"),

    # Non-coffee
    row("Sikwate","Non Coffee",[("Hot","85.00"),("Iced","95.00")],"bar"),
    row("Matcha Latte","Non Coffee",[("Hot","120.00"),("Iced","130.00")],"bar"),
    row("Strawberry White","Non Coffee",[("Iced","140.00")],"bar"),

    # Milk tea. Hokkaido, Buko Pandan, Cheesy Mango and Avocado are marked N.A.
    row("Wintermelon","Milk Tea","120.00","bar"),
    row("Okinawa","Milk Tea","120.00","bar"),
    row("Brown Sugar","Milk Tea","120.00","bar"),
    row("Taro","Milk Tea","120.00","bar"),
    row("Salted Caramel","Milk Tea","140.00","bar"),
    row("Matcha","Milk Tea","140.00","bar"),
    row("Lychee","Milk Tea","120.00","bar"),
    row("Oreo Cheesecake","Milk Tea","145.00","bar"),
    row("Hazelnut Cheesecake","Milk Tea","145.00","bar"),

    # Frappuccino / frappe / lemonade
    row("Caramel Macchiato","Frappuccino","170.00","bar"),
    row("Salted Caramel","Frappuccino","170.00","bar"),
    row("Mocha","Frappuccino","170.00","bar"),
    row("Cookies and Cream","Frappuccino","185.00","bar"),
    row("Java Chip","Frappuccino","195.00","bar"),
    row("Strawberry Cream","Frappe","150.00","bar"),
    row("Coconut Cream","Frappe","150.00","bar"),
    row("Green Tea Matcha","Frappe","165.00","bar"),
    row("Matcha Oreo","Frappe","189.00","bar"),
    row("Classic Yellow","Lemonade","79.00","bar"),
    row("Pink Sunset","Lemonade","89.00","bar"),
    row("Ocean Blue","Lemonade","89.00","bar"),

    # Drink extras
    row("Extra Shot","Drink Extras","20.00","bar"),
    row("Pearl","Drink Extras","20.00","bar"),
    row("Nata de Coco","Drink Extras","20.00","bar"),
    row("Coffee Jelly","Drink Extras","20.00","bar"),
]

def identity(item_name: str, variant_name: str, category: str) -> tuple[str, str]:
    digest=hashlib.sha256(f"hidden-oasis|{category}|{item_name}|{variant_name}".encode()).hexdigest()
    number=str(int(digest[:15],16)).zfill(18)
    return "HO-"+digest[:10].upper(), "20"+number[-10:]

def main() -> None:
    db=SessionLocal(); created_items=updated_items=created_variants=updated_variants=0
    try:
        for item_order,r in enumerate(CATALOG):
            item=db.scalar(select(MenuItem).where(MenuItem.name==r["name"],MenuItem.category==r["category"]).options(selectinload(MenuItem.variants)))
            if item is None:
                item=MenuItem(name=r["name"],display_name=r["name"],category=r["category"],prep_station=r["prep_station"],sort_order=item_order,is_active=True,pos_visible=True)
                db.add(item); db.flush(); created_items+=1
            else:
                item.display_name=r["name"]; item.prep_station=r["prep_station"]; item.sort_order=item_order; item.is_active=True; item.pos_visible=True; updated_items+=1
            by_name={v.name:v for v in item.variants}
            for variant_order,(variant_name,price) in enumerate(r["variants"]):
                sku,barcode=identity(r["name"],variant_name,r["category"])
                v=by_name.get(variant_name)
                if v is None:
                    v=MenuVariant(menu_item_id=item.id); db.add(v); created_variants+=1
                else: updated_variants+=1
                v.name=variant_name; v.sku=sku; v.barcode=barcode; v.price=Decimal(price); v.with_drink_price=None; v.sort_order=variant_order; v.is_active=True
            db.flush()
        db.commit()
        print(f"Hidden Oasis menu seed complete: items created={created_items}, items updated={updated_items}, variants created={created_variants}, variants updated={updated_variants}.")
        print(f"Verified catalogue rows: {len(CATALOG)} items / {sum(len(x['variants']) for x in CATALOG)} variants.")
    except Exception:
        db.rollback(); raise
    finally: db.close()
if __name__=="__main__": main()
