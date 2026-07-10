from decimal import Decimal

def auth(client):
    r=client.post('/api/v1/auth/login',json={'email':'owner@example.com','password':'password123'})
    return {'Authorization':f"Bearer {r.json()['access_token']}"}
def masters(client,h):
    cat=client.post('/api/v1/categories',headers=h,json={'name':'Food'}).json(); unit=client.post('/api/v1/units',headers=h,json={'code':'EA','name':'Each'}).json(); loc=client.post('/api/v1/locations',headers=h,json={'code':'MAIN','name':'Main'}).json(); item=client.post('/api/v1/items',headers=h,json={'sku':'RICE','name':'Rice','category_id':cat['id'],'base_unit_id':unit['id']}).json(); supplier=client.post('/api/v1/suppliers',headers=h,json={'code':'SUP-1','name':'Supplier One','payment_terms_days':30}).json(); return item,loc,supplier
def approved_po(client,h,item,loc,supplier,quantity='10',price='48'):
    req=client.post('/api/v1/requisitions',headers=h,json={'department':'Cafe','justification':'Replenishment','lines':[{'item_id':item['id'],'quantity':quantity,'estimated_unit_cost':'50'}]}).json()
    req=client.post(f"/api/v1/requisitions/{req['id']}/approve",headers=h).json()
    quote=client.post('/api/v1/quotations',headers=h,json={'requisition_id':req['id'],'supplier_id':supplier['id'],'delivery_days':2,'payment_terms_days':30,'lines':[{'item_id':item['id'],'quantity':quantity,'unit_price':price}]}).json()
    po=client.post('/api/v1/purchase-orders',headers=h,json={'supplier_id':supplier['id'],'requisition_id':req['id'],'quotation_id':quote['id'],'delivery_location_id':loc['id'],'lines':[{'item_id':item['id'],'ordered_quantity':quantity,'unit_price':price}]}).json()
    return client.post(f"/api/v1/purchase-orders/{po['id']}/approve",headers=h).json(),req,quote
def test_procurement_to_partial_and_full_receipt(client):
    h=auth(client); item,loc,supplier=masters(client,h); po,req,quote=approved_po(client,h,item,loc,supplier); line=po['lines'][0]
    comparison=client.get(f"/api/v1/requisitions/{req['id']}/quotation-comparison",headers=h).json(); assert Decimal(comparison[0]['total'])==Decimal('480')
    first=client.post(f"/api/v1/purchase-orders/{po['id']}/receipts",headers=h,json={'delivery_reference':'DR-1','idempotency_key':'grn-1','lines':[{'purchase_order_line_id':line['id'],'received_quantity':'4','accepted_quantity':'4','rejected_quantity':'0'}]}); assert first.status_code==201
    repeat=client.post(f"/api/v1/purchase-orders/{po['id']}/receipts",headers=h,json={'delivery_reference':'DR-1','idempotency_key':'grn-1','lines':[{'purchase_order_line_id':line['id'],'received_quantity':'4','accepted_quantity':'4','rejected_quantity':'0'}]}); assert repeat.status_code==201 and repeat.json()['id']==first.json()['id']
    after=client.get('/api/v1/purchase-orders',headers=h).json()[0]; assert after['status']=='partially_received' and after['lines'][0]['received_quantity']=='4.0000'
    second=client.post(f"/api/v1/purchase-orders/{po['id']}/receipts",headers=h,json={'delivery_reference':'DR-2','lines':[{'purchase_order_line_id':line['id'],'received_quantity':'6','accepted_quantity':'5','rejected_quantity':'1'}]}); assert second.status_code==201
    after=client.get('/api/v1/purchase-orders',headers=h).json()[0]; assert after['status']=='received' and after['lines'][0]['received_quantity']=='10.0000'
    bal=client.get('/api/v1/stock/balances',headers=h).json()[0]; assert bal['quantity']=='9.0000'
    ret=client.post(f"/api/v1/purchase-orders/{po['id']}/returns",headers=h,json={'reason':'Damaged after inspection','idempotency_key':'return-1','lines':[{'purchase_order_line_id':line['id'],'quantity':'2'}]}); assert ret.status_code==201
    ret_repeat=client.post(f"/api/v1/purchase-orders/{po['id']}/returns",headers=h,json={'reason':'Damaged after inspection','idempotency_key':'return-1','lines':[{'purchase_order_line_id':line['id'],'quantity':'2'}]}); assert ret_repeat.json()['id']==ret.json()['id']
    bal=client.get('/api/v1/stock/balances',headers=h).json()[0]; assert bal['quantity']=='7.0000'
def test_fully_rejected_delivery_is_recorded_without_stock(client):
    h=auth(client); item,loc,supplier=masters(client,h); po,_,_=approved_po(client,h,item,loc,supplier,quantity='3'); line=po['lines'][0]
    receipt=client.post(f"/api/v1/purchase-orders/{po['id']}/receipts",headers=h,json={'delivery_reference':'DR-REJECTED','lines':[{'purchase_order_line_id':line['id'],'received_quantity':'3','accepted_quantity':'0','rejected_quantity':'3'}]})
    assert receipt.status_code==201 and receipt.json()['lines'][0]['accepted_quantity']=='0.0000'
    assert client.get('/api/v1/stock/balances',headers=h).json()==[]
def test_unapproved_requisition_blocks_quote(client):
    h=auth(client); item,_,supplier=masters(client,h)
    req=client.post('/api/v1/requisitions',headers=h,json={'department':'Cafe','lines':[{'item_id':item['id'],'quantity':'1'}]}).json()
    r=client.post('/api/v1/quotations',headers=h,json={'requisition_id':req['id'],'supplier_id':supplier['id'],'lines':[{'item_id':item['id'],'quantity':'1','unit_price':'10'}]}); assert r.status_code==409
