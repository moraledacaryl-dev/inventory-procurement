from decimal import Decimal


def auth_headers(client):
    r=client.post('/api/v1/auth/login',json={'email':'owner@example.com','password':'password123'}); assert r.status_code==200
    return {'Authorization':f"Bearer {r.json()['access_token']}"}


def by_code(rows,code): return next((x for x in rows if x['code']==code),None)


def seed_asset(client,h):
    dims=client.get('/api/v1/classification/bootstrap',headers=h).json()['dimensions']
    assets=by_code(dims['workspace'],'assets-property'); equipment=by_code(dims['item_type'],'equipment')
    asset_class=by_code(dims.get('asset_class',[]),'equipment')
    if not asset_class:
        asset_class=client.post('/api/v1/classification/dimensions',headers=h,json={'dimension_type':'asset_class','code':'equipment','name':'Equipment','behavior_key':'equipment'}).json()
    method=by_code(dims.get('depreciation_method',[]),'straight-line')
    if not method:
        method=client.post('/api/v1/classification/dimensions',headers=h,json={'dimension_type':'depreciation_method','code':'straight-line','name':'Straight line','behavior_key':'straight_line'}).json()
    category=client.post('/api/v1/categories',headers=h,json={'name':'Maintenance assets'}).json()
    unit=client.post('/api/v1/units',headers=h,json={'code':'EA5','name':'Each','precision':0}).json()
    location=client.post('/api/v1/locations',headers=h,json={'code':'PLANT','name':'Plant room'}).json()
    item=client.post('/api/v1/items',headers=h,json={'sku':'GENERATOR-01','name':'Generator','category_id':category['id'],'base_unit_id':unit['id'],'primary_workspace_id':assets['id'],'item_type_id':equipment['id']}).json()
    asset=client.post('/api/v1/assets',headers=h,json={'asset_tag':'FA-MAINT-1','item_id':item['id'],'asset_class_id':asset_class['id'],'depreciation_method_id':method['id'],'location_id':location['id'],'acquisition_date':'2026-01-01','placed_in_service_date':'2026-01-01','acquisition_cost':60000,'useful_life_months':60}).json()
    return asset,item,location


def test_maintenance_plan_work_order_and_accounting_event(client):
    h=auth_headers(client); asset,item,_=seed_asset(client,h)
    plan=client.post('/api/v1/maintenance/plans',headers=h,json={'code':'GEN-MONTHLY','name':'Generator monthly inspection','asset_id':asset['id'],'interval_days':30,'next_due_date':'2026-07-31'}); assert plan.status_code==201
    wo=client.post('/api/v1/maintenance/work-orders',headers=h,json={'asset_id':asset['id'],'plan_id':plan.json()['id'],'title':'Inspect generator','parts':[{'item_id':item['id'],'quantity':1,'unit_cost':100}]}); assert wo.status_code==201
    assert client.post(f"/api/v1/maintenance/work-orders/{wo.json()['id']}/start",headers=h).status_code==200
    done=client.post(f"/api/v1/maintenance/work-orders/{wo.json()['id']}/complete",headers=h,json={'labor_cost':200,'external_cost':50,'downtime_hours':1,'completion_notes':'Completed'}); assert done.status_code==200
    assert done.json()['status']=='completed'
    rows=client.get('/api/v1/maintenance/work-orders?status=completed',headers=h).json(); assert rows[0]['status']=='completed'


def test_purchase_line_treatment_and_editable_accounting_mapping(client):
    h=auth_headers(client)
    mapping=client.post('/api/v1/accounting-mappings',headers=h,json={'event_key':'inventory.maintenance.completed','debit_account':'Repairs and Maintenance','credit_account':'Accounts Payable'}); assert mapping.status_code==201
    treatment=client.post('/api/v1/purchase-line-treatments',headers=h,json={'source_type':'purchase_order_line','source_line_id':'line-1','treatment':'service_expense','accounting_mapping_id':mapping.json()['id'],'project_reference':'Hotel renovation'}); assert treatment.status_code==201
    updated=client.post('/api/v1/purchase-line-treatments',headers=h,json={'source_type':'purchase_order_line','source_line_id':'line-1','treatment':'fixed_asset','accounting_mapping_id':mapping.json()['id']}); assert updated.status_code==201
    assert updated.json()['treatment']=='fixed_asset'
    rows=client.get('/api/v1/accounting-mappings',headers=h).json(); assert rows[0]['debit_account']=='Repairs and Maintenance'
