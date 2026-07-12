from app.db.session import SessionLocal
from app.models.inventory import StockBalance


def auth_headers(client):
    response=client.post('/api/v1/auth/login',json={'email':'owner@example.com','password':'password123'})
    assert response.status_code==200
    return {'Authorization':f"Bearer {response.json()['access_token']}"}


def seed_stock(client,headers):
    category=client.post('/api/v1/categories',headers=headers,json={'name':'Assurance'}).json()
    unit=client.post('/api/v1/units',headers=headers,json={'code':'ASR','name':'Assurance unit','precision':3}).json()
    location=client.post('/api/v1/locations',headers=headers,json={'code':'ASR-LOC','name':'Assurance Location','location_type':'storage'}).json()
    item=client.post('/api/v1/items',headers=headers,json={'sku':'ASR-ITEM','name':'Assurance Item','category_id':category['id'],'base_unit_id':unit['id'],'standard_cost':10}).json()
    receipt=client.post('/api/v1/stock/receipts',headers=headers,json={'location_id':location['id'],'idempotency_key':'assurance-seed','lines':[{'item_id':item['id'],'quantity':5,'unit_cost':10}]})
    assert receipt.status_code==201
    return item,location


def test_final_assurance_reconciles_stock(client):
    headers=auth_headers(client)
    item,location=seed_stock(client,headers)
    response=client.get('/api/v1/reports/final-assurance',headers=headers)
    assert response.status_code==200
    payload=response.json()
    assert payload['summary']['stock_mismatches']==0
    assert any(check['key']=='stock_reconciliation' and check['status']=='passed' for check in payload['checks'])

    with SessionLocal() as db:
        balance=db.query(StockBalance).filter_by(item_id=item['id'],location_id=location['id']).one()
        balance.quantity=7
        db.commit()

    response=client.get('/api/v1/reports/final-assurance',headers=headers)
    assert response.status_code==200
    payload=response.json()
    assert payload['overall_status']=='critical'
    assert payload['summary']['stock_mismatches']==1
    mismatch=next(row for row in payload['stock_mismatches'] if row['item_id']==item['id'])
    assert mismatch['ledger_quantity']=='5.0000'
    assert mismatch['balance_quantity']=='7.0000'


def test_record_and_export_final_assurance(client):
    headers=auth_headers(client)
    recorded=client.post('/api/v1/reports/final-assurance/record',headers=headers)
    assert recorded.status_code==200
    assert recorded.json()['generated_at']
    exported=client.get('/api/v1/reports/final-assurance.csv',headers=headers)
    assert exported.status_code==200
    assert 'text/csv' in exported.headers['content-type']
    assert 'overall_status' in exported.text
