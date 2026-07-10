from decimal import Decimal
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User

def auth(client,email='owner@example.com'):
    r=client.post('/api/v1/auth/login',json={'email':email,'password':'password123'})
    return {'Authorization':f"Bearer {r.json()['access_token']}"}
def second_owner(client):
    with SessionLocal() as db:
        if not db.query(User).filter(User.email=='recipe-approver@example.com').first():
            db.add(User(email='recipe-approver@example.com',full_name='Recipe Approver',password_hash=hash_password('password123'),role='owner')); db.commit()
    return auth(client,'recipe-approver@example.com')
def setup(client,h):
    cat=client.post('/api/v1/categories',headers=h,json={'name':'Recipe Items'}).json(); unit=client.post('/api/v1/units',headers=h,json={'code':'EA','name':'Each'}).json(); loc=client.post('/api/v1/locations',headers=h,json={'code':'KITCHEN','name':'Kitchen'}).json()
    flour=client.post('/api/v1/items',headers=h,json={'sku':'FLOUR','name':'Flour','category_id':cat['id'],'base_unit_id':unit['id'],'standard_cost':'10'}).json()
    sugar=client.post('/api/v1/items',headers=h,json={'sku':'SUGAR','name':'Sugar','category_id':cat['id'],'base_unit_id':unit['id'],'standard_cost':'20'}).json()
    cake=client.post('/api/v1/items',headers=h,json={'sku':'CAKE','name':'Cake','category_id':cat['id'],'base_unit_id':unit['id'],'standard_cost':'0'}).json()
    client.post('/api/v1/stock/receipts',headers=h,json={'location_id':loc['id'],'lines':[{'item_id':flour['id'],'quantity':'100','unit_cost':'10'},{'item_id':sugar['id'],'quantity':'100','unit_cost':'20'}]})
    recipe=client.post('/api/v1/recipes',headers=h,json={'code':'CAKE-R1','name':'Cake Recipe','output_item_id':cake['id'],'yield_quantity':'10','lines':[{'ingredient_item_id':flour['id'],'quantity':'5','waste_factor':'0'},{'ingredient_item_id':sugar['id'],'quantity':'2','waste_factor':'0'}]}).json()
    recipe=client.post(f"/api/v1/recipes/{recipe['id']}/approve",headers=second_owner(client)).json()
    return flour,sugar,cake,loc,recipe

def test_recipe_cost_and_production_batch(client):
    h=auth(client); flour,sugar,cake,loc,recipe=setup(client,h)
    cost=client.get(f"/api/v1/recipes/{recipe['id']}/cost?location_id={loc['id']}",headers=h).json(); assert Decimal(cost['total_cost'])==Decimal('90') and Decimal(cost['cost_per_output_unit'])==Decimal('9')
    batch=client.post('/api/v1/production-batches',headers=h,json={'recipe_id':recipe['id'],'location_id':loc['id'],'planned_quantity':'20'}).json()
    completed=client.post(f"/api/v1/production-batches/{batch['id']}/complete",headers=h,json={'actual_quantity':'20'}); assert completed.status_code==200 and completed.json()['status']=='completed'
    balances=client.get('/api/v1/stock/balances',headers=h).json(); values={(x['item_id'],x['location_id']):Decimal(x['quantity']) for x in balances}
    assert values[(flour['id'],loc['id'])]==Decimal('90') and values[(sugar['id'],loc['id'])]==Decimal('96') and values[(cake['id'],loc['id'])]==Decimal('20')

def test_pos_sale_consumption_idempotency_and_reversal(client):
    h=auth(client); flour,sugar,_,loc,recipe=setup(client,h)
    mapping=client.post('/api/v1/pos-mappings',headers=h,json={'pos_system':'hidden-oasis-pos','external_product_id':'MENU-CAKE','recipe_id':recipe['id'],'location_id':loc['id']}); assert mapping.status_code==201
    payload={'external_event_id':'EVT-SALE-1','external_sale_id':'SALE-1','pos_system':'hidden-oasis-pos','event_type':'sale_completed','lines':[{'external_product_id':'MENU-CAKE','quantity':'2'}]}
    sale=client.post('/api/v1/integrations/pos/events',headers=h,json=payload); assert sale.status_code==201
    duplicate=client.post('/api/v1/integrations/pos/events',headers=h,json=payload); assert duplicate.status_code==201 and duplicate.json()['id']==sale.json()['id']
    balances=client.get('/api/v1/stock/balances',headers=h).json(); values={x['item_id']:Decimal(x['quantity']) for x in balances}; assert values[flour['id']]==Decimal('99') and values[sugar['id']]==Decimal('99.6')
    reversal=client.post('/api/v1/integrations/pos/events',headers=h,json={'external_event_id':'EVT-VOID-1','external_sale_id':'SALE-1','pos_system':'hidden-oasis-pos','event_type':'sale_voided','lines':[{'external_product_id':'MENU-CAKE','quantity':'2'}]}); assert reversal.status_code==201
    balances=client.get('/api/v1/stock/balances',headers=h).json(); values={x['item_id']:Decimal(x['quantity']) for x in balances}; assert values[flour['id']]==Decimal('100') and values[sugar['id']]==Decimal('100')
    second=client.post('/api/v1/integrations/pos/events',headers=h,json={'external_event_id':'EVT-REFUND-1','external_sale_id':'SALE-1','pos_system':'hidden-oasis-pos','event_type':'sale_refunded','lines':[{'external_product_id':'MENU-CAKE','quantity':'2'}]}); assert second.status_code==409
    recon=client.get('/api/v1/integrations/reconciliation',headers=h).json(); assert recon['latest_pos_event_at'] is not None
