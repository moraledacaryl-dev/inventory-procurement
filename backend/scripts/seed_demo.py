import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.inventory import Category, UnitOfMeasure, Location, Item
from app.models.procurement import Supplier

def get_or_create(db,model,lookup,defaults=None):
    row=db.scalar(select(model).filter_by(**lookup))
    if row:return row,False
    row=model(**lookup,**(defaults or {}));db.add(row);db.flush();return row,True

def main():
    created=0
    with SessionLocal() as db:
        food,new=get_or_create(db,Category,{'name':'Food & Beverage'},{'description':'Cafe and kitchen inventory'});created+=new
        housekeeping,new=get_or_create(db,Category,{'name':'Housekeeping'},{'description':'Room and cleaning supplies'});created+=new
        each,new=get_or_create(db,UnitOfMeasure,{'code':'EA'},{'name':'Each','precision':0});created+=new
        kg,new=get_or_create(db,UnitOfMeasure,{'code':'KG'},{'name':'Kilogram','precision':3});created+=new
        liter,new=get_or_create(db,UnitOfMeasure,{'code':'L'},{'name':'Liter','precision':3});created+=new
        locations=[('MAIN','Main Storeroom','storeroom'),('KITCHEN','Cafe Kitchen','kitchen'),('BAR','Cafe Bar','bar'),('HOUSE','Housekeeping Store','storeroom')]
        locs={}
        for code,name,kind in locations:
            loc,new=get_or_create(db,Location,{'code':code},{'name':name,'location_type':kind});created+=new;locs[code]=loc
        items=[('COFFEE-BEAN','Coffee Beans',food.id,kg.id,'2','650'),('MILK-FRESH','Fresh Milk',food.id,liter.id,'12','95'),('SUGAR-WHITE','White Sugar',food.id,kg.id,'5','75'),('CLEANER-ALL','All-Purpose Cleaner',housekeeping.id,liter.id,'4','120'),('TISSUE-ROLL','Tissue Roll',housekeeping.id,each.id,'24','18')]
        for sku,name,category_id,unit_id,minimum,cost in items:
            _,new=get_or_create(db,Item,{'sku':sku},{'name':name,'category_id':category_id,'base_unit_id':unit_id,'minimum_stock':minimum,'standard_cost':cost});created+=new
        suppliers=[('CAFE-SUPPLY','Cafe Supply Partner'),('HOUSE-SUPPLY','Housekeeping Supply Partner')]
        for code,name in suppliers:
            _,new=get_or_create(db,Supplier,{'code':code},{'name':name,'payment_terms_days':30});created+=new
        db.commit()
    print(f'Demo seed complete. Created {created} records.')
if __name__=='__main__':main()
