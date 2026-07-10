import io
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.operations import Notification

def auth(client):
    r=client.post('/api/v1/auth/login',json={'email':'owner@example.com','password':'password123'})
    return {'Authorization':f"Bearer {r.json()['access_token']}"}

def test_integration_idempotency_and_retry(client):
    h=auth(client); payload={'direction':'outbound','source_system':'inventory','destination_system':'accounting','event_type':'goods.received','aggregate_type':'goods_receipt','aggregate_id':'gr-1','idempotency_key':'evt-1','payload':{'value':1}}
    first=client.post('/api/v1/integration-events',headers=h,json=payload); second=client.post('/api/v1/integration-events',headers=h,json=payload)
    assert first.status_code==201 and second.json()['id']==first.json()['id']
    retry=client.post(f"/api/v1/integration-events/{first.json()['id']}/retry",headers=h); assert retry.json()['status']=='pending'

def test_notifications_and_audit(client):
    h=auth(client)
    with SessionLocal() as db:
        db.add(Notification(title='Low stock',message='Coffee beans are below minimum',severity='warning'))
        db.add(AuditLog(action='test.action',entity_type='test',details={}))
        db.commit()
    notes=client.get('/api/v1/notifications?unread_only=true',headers=h); assert notes.status_code==200 and len(notes.json())==1
    marked=client.post(f"/api/v1/notifications/{notes.json()[0]['id']}/read",headers=h); assert marked.json()['is_read'] is True
    audit=client.get('/api/v1/audit-logs?action=test.action',headers=h); assert audit.status_code==200 and len(audit.json())==1

def test_csv_exports_and_import_validation(client):
    h=auth(client)
    exported=client.get('/api/v1/exports/items.csv',headers=h); assert exported.status_code==200 and 'sku,name' in exported.text
    bad=io.BytesIO(b'sku,name,category_id,base_unit_id\nX,Test,missing,missing\n')
    response=client.post('/api/v1/imports/items.csv',headers=h,files={'file':('items.csv',bad,'text/csv')}); assert response.status_code==422
