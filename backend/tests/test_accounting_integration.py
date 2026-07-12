def auth_headers(client):
    response=client.post('/api/v1/auth/login',json={'email':'owner@example.com','password':'password123'})
    assert response.status_code==200
    return {'Authorization':f"Bearer {response.json()['access_token']}"}


def accounting_headers():return {'X-Integration-Token':'test-accounting-integration-token'}


def create_accounting_event(client,headers,key='acct-test-1',event_type='inventory.stock_document.posted'):
    response=client.post('/api/v1/integration-events',headers=headers,json={'direction':'outbound','source_system':'inventory','destination_system':'accounting','event_type':event_type,'aggregate_type':'stock_document','aggregate_id':'doc-001','idempotency_key':key,'payload':{'lines':[{'item_id':'item-1','quantity':'2','unit_cost':'15'}]}})
    assert response.status_code==201
    return response.json()


def test_accounting_workspace_and_mapping(client):
    headers=auth_headers(client);event=create_accounting_event(client,headers)
    workspace=client.get('/api/v1/integrations/accounting/workspace',headers=headers);assert workspace.status_code==200
    row=next(item for item in workspace.json()['events'] if item['id']==event['id'])
    assert row['mapped'] is True;assert row['debit_account']=='Inventory Asset';assert row['credit_account']=='Inventory Clearing';assert row['amount']==30
    assert row['journal_lines'][0]['side']=='debit';assert row['journal_lines'][1]['side']=='credit';assert workspace.json()['summary']['pending']>=1


def test_accounting_receipt_accept_reject_and_conflict(client):
    auth=auth_headers(client);service=accounting_headers();accepted=create_accounting_event(client,auth,'acct-accept')
    payload={'idempotency_key':'acct-accept','external_receipt_id':'receipt-1001','accepted':True,'external_reference':'JE-1001'}
    response=client.post('/api/v1/integrations/accounting/receipts',headers=service,json=payload);assert response.status_code==200;assert response.json()['status']=='completed'
    repeat=client.post('/api/v1/integrations/accounting/receipts',headers=service,json=payload);assert repeat.status_code==200
    conflict=client.post('/api/v1/integrations/accounting/receipts',headers=service,json={**payload,'external_receipt_id':'receipt-1002','accepted':False});assert conflict.status_code==409

    rejected=create_accounting_event(client,auth,'acct-reject')
    response=client.post('/api/v1/integrations/accounting/receipts',headers=service,json={'idempotency_key':'acct-reject','external_receipt_id':'receipt-2001','accepted':False,'message':'Missing account mapping'})
    assert response.status_code==200;assert response.json()['status']=='failed';assert response.json()['last_error']=='Missing account mapping'
    requeued=client.post(f"/api/v1/integrations/accounting/events/{rejected['id']}/requeue",headers=auth);assert requeued.status_code==200;assert requeued.json()['status']=='pending'


def test_accounting_receipt_requires_service_token(client):
    auth=auth_headers(client);create_accounting_event(client,auth,'acct-secure')
    response=client.post('/api/v1/integrations/accounting/receipts',json={'idempotency_key':'acct-secure','external_receipt_id':'receipt-3001','accepted':True})
    assert response.status_code==401


def test_accounting_workspace_flags_unmapped_event(client):
    headers=auth_headers(client);event=create_accounting_event(client,headers,'acct-unmapped','inventory.unknown.event')
    workspace=client.get('/api/v1/integrations/accounting/workspace',headers=headers);row=next(item for item in workspace.json()['events'] if item['id']==event['id'])
    assert row['mapped'] is False;assert row['debit_account']=='Unmapped'
