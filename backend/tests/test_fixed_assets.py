from decimal import Decimal


def auth_headers(client):
    r=client.post('/api/v1/auth/login',json={'email':'owner@example.com','password':'password123'}); assert r.status_code==200
    return {'Authorization':f"Bearer {r.json()['access_token']}"}


def by_code(rows,code): return next((x for x in rows if x['code']==code),None)


def seed(client,h):
    dims=client.get('/api/v1/classification/bootstrap',headers=h).json()['dimensions']
    assets=by_code(dims['workspace'],'assets-property'); equipment=by_code(dims['item_type'],'equipment')
    asset_class=by_code(dims.get('asset_class',[]),'equipment')
    if not asset_class:
        asset_class=client.post('/api/v1/classification/dimensions',headers=h,json={'dimension_type':'asset_class','code':'equipment','name':'Equipment','behavior_key':'equipment'}).json()
    method=by_code(dims.get('depreciation_method',[]),'straight-line')
    if not method:
        method=client.post('/api/v1/classification/dimensions',headers=h,json={'dimension_type':'depreciation_method','code':'straight-line','name':'Straight line','behavior_key':'straight_line'}).json()
    category=client.post('/api/v1/categories',headers=h,json={'name':'Capital equipment'}).json()
    unit=client.post('/api/v1/units',headers=h,json={'code':'EA','name':'Each','precision':0}).json()
    location=client.post('/api/v1/locations',headers=h,json={'code':'CAFE','name':'Cafe'}).json()
    item=client.post('/api/v1/items',headers=h,json={'sku':'ESPRESSO-MACHINE','name':'Espresso machine','category_id':category['id'],'base_unit_id':unit['id'],'primary_workspace_id':assets['id'],'item_type_id':equipment['id']}).json()
    return item,asset_class,method,location


def test_asset_register_and_idempotent_depreciation(client):
    h=auth_headers(client); item,asset_class,method,location=seed(client,h)
    r=client.post('/api/v1/assets',headers=h,json={'asset_tag':'FA-0001','item_id':item['id'],'asset_class_id':asset_class['id'],'depreciation_method_id':method['id'],'location_id':location['id'],'acquisition_date':'2026-01-01','placed_in_service_date':'2026-01-01','acquisition_cost':120000,'residual_value':0,'useful_life_months':60})
    assert r.status_code==201; asset=r.json(); assert Decimal(str(asset['net_book_value']))==Decimal('120000.00')
    run=client.post('/api/v1/depreciation-runs',headers=h,json={'period':'2026-07'}); assert run.status_code==201; assert Decimal(str(run.json()['total_amount']))==Decimal('2000.00')
    duplicate=client.post('/api/v1/depreciation-runs',headers=h,json={'period':'2026-07'}); assert duplicate.status_code==409
    posted=client.post(f"/api/v1/depreciation-runs/{run.json()['id']}/post",headers=h); assert posted.status_code==200
    assets=client.get('/api/v1/assets',headers=h).json(); assert Decimal(str(assets[0]['accumulated_depreciation']))==Decimal('2000.00')
    second_post=client.post(f"/api/v1/depreciation-runs/{run.json()['id']}/post",headers=h); assert second_post.status_code==409


def test_asset_transfer_impairment_and_disposal(client):
    h=auth_headers(client); item,asset_class,method,location=seed(client,h)
    asset=client.post('/api/v1/assets',headers=h,json={'asset_tag':'FA-0002','item_id':item['id'],'asset_class_id':asset_class['id'],'depreciation_method_id':method['id'],'location_id':location['id'],'acquisition_date':'2026-01-01','placed_in_service_date':'2026-01-01','acquisition_cost':10000,'useful_life_months':60}).json()
    other=client.post('/api/v1/locations',headers=h,json={'code':'HOTEL','name':'Hotel'}).json()
    assert client.post(f"/api/v1/assets/{asset['id']}/events",headers=h,json={'event_type':'transfer','event_date':'2026-07-01','to_location_id':other['id']}).status_code==201
    assert client.post(f"/api/v1/assets/{asset['id']}/events",headers=h,json={'event_type':'impairment','event_date':'2026-07-02','amount':1000}).status_code==201
    assert client.post(f"/api/v1/assets/{asset['id']}/events",headers=h,json={'event_type':'dispose','event_date':'2026-07-03','amount':5000}).status_code==201
    assert client.get('/api/v1/assets?status=disposed',headers=h).json()[0]['status']=='disposed'
