def login(client):
    r=client.post('/api/v1/auth/login',json={'email':'owner@example.com','password':'password123'})
    return {'Authorization':f"Bearer {r.json()['access_token']}"}
def setup_master(client,h):
    cat=client.post('/api/v1/categories',headers=h,json={'name':'Beverages'}).json(); unit=client.post('/api/v1/units',headers=h,json={'code':'EA','name':'Each'}).json(); a=client.post('/api/v1/locations',headers=h,json={'code':'MAIN','name':'Main Store'}).json(); b=client.post('/api/v1/locations',headers=h,json={'code':'BAR','name':'Bar'}).json(); item=client.post('/api/v1/items',headers=h,json={'sku':'COKE-1','name':'Coke','category_id':cat['id'],'base_unit_id':unit['id'],'minimum_stock':'2','standard_cost':'40'}).json(); return item,a,b
def test_inventory_flow(client):
    h=login(client); item,a,b=setup_master(client,h)
    r=client.post('/api/v1/stock/receipts',headers=h,json={'location_id':a['id'],'idempotency_key':'receipt-1','lines':[{'item_id':item['id'],'quantity':'10','unit_cost':'40'}]}); assert r.status_code==201
    same=client.post('/api/v1/stock/receipts',headers=h,json={'location_id':a['id'],'idempotency_key':'receipt-1','lines':[{'item_id':item['id'],'quantity':'10','unit_cost':'40'}]}); assert same.json()['id']==r.json()['id']
    t=client.post('/api/v1/stock/transfers',headers=h,json={'source_location_id':a['id'],'destination_location_id':b['id'],'lines':[{'item_id':item['id'],'quantity':'3'}]}); assert t.status_code==201 and len(t.json()['movements'])==2
    i=client.post('/api/v1/stock/issues',headers=h,json={'location_id':b['id'],'lines':[{'item_id':item['id'],'quantity':'1'}]}); assert i.status_code==201
    balances=client.get('/api/v1/stock/balances',headers=h).json(); values={x['location_id']:x['quantity'] for x in balances}; costs={x['location_id']:x['average_cost'] for x in balances}
    assert values[a['id']]=='7.0000' and values[b['id']]=='2.0000'
    assert costs[b['id']]=='40.0000'
def test_negative_stock_is_blocked(client):
    h=login(client); item,a,_=setup_master(client,h); r=client.post('/api/v1/stock/issues',headers=h,json={'location_id':a['id'],'lines':[{'item_id':item['id'],'quantity':'1'}]}); assert r.status_code==409
def test_count_posts_variance(client):
    h=login(client); item,a,_=setup_master(client,h); client.post('/api/v1/stock/receipts',headers=h,json={'location_id':a['id'],'lines':[{'item_id':item['id'],'quantity':'5','unit_cost':'40'}]}); count=client.post('/api/v1/counts',headers=h,json={'location_id':a['id']}).json(); posted=client.post(f"/api/v1/counts/{count['id']}/post",headers=h,json={'lines':[{'item_id':item['id'],'counted_quantity':'4'}]}); assert posted.status_code==200 and posted.json()['status']=='posted'; bal=client.get(f"/api/v1/stock/balances?item_id={item['id']}&location_id={a['id']}",headers=h).json()[0]; assert bal['quantity']=='4.0000'
