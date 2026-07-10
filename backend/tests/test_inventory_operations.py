from decimal import Decimal

def auth(client):
    r=client.post('/api/v1/auth/login',json={'email':'owner@example.com','password':'password123'})
    return {'Authorization':f"Bearer {r.json()['access_token']}"}
def setup(client,h):
    cat=client.post('/api/v1/categories',headers=h,json={'name':'Perishables'}).json()
    each=client.post('/api/v1/units',headers=h,json={'code':'EA','name':'Each'}).json()
    case=client.post('/api/v1/units',headers=h,json={'code':'CS','name':'Case'}).json()
    main=client.post('/api/v1/locations',headers=h,json={'code':'MAIN','name':'Main Store'}).json()
    kitchen=client.post('/api/v1/locations',headers=h,json={'code':'KIT','name':'Kitchen'}).json()
    item=client.post('/api/v1/items',headers=h,json={'sku':'MILK-1L','name':'Milk 1L','category_id':cat['id'],'base_unit_id':each['id'],'minimum_stock':'6','standard_cost':'80'}).json()
    supplier=client.post('/api/v1/suppliers',headers=h,json={'code':'DAIRY','name':'Dairy Supplier'}).json()
    return item,each,case,main,kitchen,supplier

def test_barcode_conversion_location_controls_and_lot_waste(client):
    h=auth(client); item,each,case,main,_,supplier=setup(client,h)
    barcode=client.post(f"/api/v1/items/{item['id']}/barcodes",headers=h,json={'barcode':'4801234567890','is_primary':True}); assert barcode.status_code==201
    lookup=client.get('/api/v1/items/barcode/4801234567890',headers=h).json(); assert lookup['sku']=='MILK-1L'
    conversion=client.post(f"/api/v1/items/{item['id']}/conversions",headers=h,json={'from_unit_id':case['id'],'to_unit_id':each['id'],'multiplier':'12'}); assert conversion.status_code==201
    converted=client.get(f"/api/v1/items/{item['id']}/convert?from_unit_id={case['id']}&to_unit_id={each['id']}&quantity=2",headers=h).json(); assert Decimal(converted['converted_quantity'])==Decimal('24')
    setting=client.post('/api/v1/item-location-settings',headers=h,json={'item_id':item['id'],'location_id':main['id'],'minimum_stock':'10','reorder_quantity':'12','maximum_stock':'30','preferred_supplier_id':supplier['id'],'cycle_count_days':7}); assert setting.status_code==201
    lot=client.post('/api/v1/lots',headers=h,json={'item_id':item['id'],'lot_number':'LOT-001','expiry_date':'2026-07-20','supplier_id':supplier['id']}).json()
    receipt=client.post('/api/v1/lot-transactions',headers=h,json={'lot_id':lot['id'],'location_id':main['id'],'quantity':'20','unit_cost':'80','transaction_type':'receipt'}); assert receipt.status_code==201
    waste=client.post('/api/v1/lot-transactions',headers=h,json={'lot_id':lot['id'],'location_id':main['id'],'quantity':'2','unit_cost':'80','transaction_type':'waste'}); assert waste.status_code==201
    lot_balance=client.get(f"/api/v1/lot-balances?item_id={item['id']}&location_id={main['id']}",headers=h).json()[0]; assert Decimal(lot_balance['quantity'])==Decimal('18')
    valuation=client.get(f"/api/v1/reports/valuation?location_id={main['id']}",headers=h).json()[0]; assert Decimal(valuation['inventory_value'])==Decimal('1440')
    waste_report=client.get('/api/v1/reports/waste',headers=h).json()[0]; assert Decimal(waste_report['quantity'])==Decimal('2')

def test_reservation_transfer_acknowledgement_and_availability(client):
    h=auth(client); item,_,_,main,kitchen,_=setup(client,h)
    client.post('/api/v1/stock/receipts',headers=h,json={'location_id':main['id'],'lines':[{'item_id':item['id'],'quantity':'10','unit_cost':'80'}]})
    reservation=client.post('/api/v1/reservations',headers=h,json={'item_id':item['id'],'location_id':main['id'],'quantity':'3','reference_type':'event','reference_id':'EVT-1'}).json()
    availability=client.get(f"/api/v1/availability?item_id={item['id']}&location_id={main['id']}",headers=h).json()[0]; assert Decimal(availability['available_quantity'])==Decimal('7')
    blocked=client.post('/api/v1/transfer-orders',headers=h,json={'source_location_id':main['id'],'destination_location_id':kitchen['id'],'lines':[{'item_id':item['id'],'quantity':'8'}]}); assert blocked.status_code==409
    client.post(f"/api/v1/reservations/{reservation['id']}/release",headers=h)
    transfer=client.post('/api/v1/transfer-orders',headers=h,json={'source_location_id':main['id'],'destination_location_id':kitchen['id'],'lines':[{'item_id':item['id'],'quantity':'8'}]}).json(); assert transfer['status']=='draft'
    dispatched=client.post(f"/api/v1/transfer-orders/{transfer['id']}/dispatch",headers=h).json(); assert dispatched['status']=='dispatched'
    received=client.post(f"/api/v1/transfer-orders/{transfer['id']}/receive",headers=h).json(); assert received['status']=='received' and received['stock_document_id']
    balances=client.get('/api/v1/stock/balances',headers=h).json(); values={x['location_id']:Decimal(x['quantity']) for x in balances}; assert values[main['id']]==Decimal('2') and values[kitchen['id']]==Decimal('8')

def test_cycle_count_schedule_and_expiry_report(client):
    h=auth(client); item,_,_,main,_,supplier=setup(client,h)
    schedule=client.post('/api/v1/cycle-count-schedules',headers=h,json={'item_id':item['id'],'location_id':main['id'],'frequency_days':7,'next_count_date':'2026-07-11'}); assert schedule.status_code==201
    due=client.get('/api/v1/cycle-count-schedules?due_only=true',headers=h).json(); assert len(due)==1
    lot=client.post('/api/v1/lots',headers=h,json={'item_id':item['id'],'lot_number':'EXP-001','expiry_date':'2026-07-12','supplier_id':supplier['id']}).json()
    client.post('/api/v1/lot-transactions',headers=h,json={'lot_id':lot['id'],'location_id':main['id'],'quantity':'2','unit_cost':'80','transaction_type':'receipt'})
    expiring=client.get('/api/v1/reports/expiry?days=30',headers=h).json(); assert expiring and expiring[0]['lot_number']=='EXP-001'
