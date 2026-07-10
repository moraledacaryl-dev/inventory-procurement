import io
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.operations import Notification, IntegrationEvent
from app.services.integration_worker import claim_events, process_event

class SuccessResponse:
    def raise_for_status(self): return None
class SuccessClient:
    def post(self,*args,**kwargs): return SuccessResponse()
class FailureClient:
    def post(self,*args,**kwargs): raise RuntimeError('destination unavailable')

def auth(client):
    r=client.post('/api/v1/auth/login',json={'email':'owner@example.com','password':'password123'})
    return {'Authorization':f"Bearer {r.json()['access_token']}"}

def test_integration_idempotency_retry_and_worker_delivery(client):
    h=auth(client); payload={'direction':'outbound','source_system':'inventory','destination_system':'accounting','event_type':'goods.received','aggregate_type':'goods_receipt','aggregate_id':'gr-1','idempotency_key':'evt-1','payload':{'value':1}}
    first=client.post('/api/v1/integration-events',headers=h,json=payload); second=client.post('/api/v1/integration-events',headers=h,json=payload)
    assert first.status_code==201 and second.json()['id']==first.json()['id']
    with SessionLocal() as db:
        claimed=claim_events(db,'test-worker'); assert len(claimed)==1
        delivered=process_event(db,claimed[0].id,'test-worker',{'accounting':'https://accounting.test/events'},SuccessClient())
        assert delivered.status=='completed' and delivered.attempts==1
    retry=client.post(f"/api/v1/integration-events/{first.json()['id']}/retry",headers=h); assert retry.json()['status']=='pending' and retry.json()['attempts']==0

def test_worker_backoff_and_dead_letter(client):
    h=auth(client); payload={'direction':'outbound','source_system':'inventory','destination_system':'accounting','event_type':'failure.test','aggregate_type':'test','aggregate_id':'1','idempotency_key':'evt-fail','payload':{},'max_attempts':1}
    event=client.post('/api/v1/integration-events',headers=h,json=payload).json()
    with SessionLocal() as db:
        claimed=claim_events(db,'failure-worker'); result=process_event(db,claimed[0].id,'failure-worker',{'accounting':'https://accounting.test/events'},FailureClient())
        assert result.status=='dead_letter' and result.attempts==1
    notes=client.get('/api/v1/notifications?unread_only=true',headers=h).json(); assert any('requires attention' in n['title'] for n in notes)

def test_notifications_are_read_per_user_and_audited(client):
    h=auth(client)
    with SessionLocal() as db:
        db.add(Notification(title='Low stock',message='Coffee beans are below minimum',severity='warning'))
        db.add(AuditLog(action='test.action',entity_type='test',details={}))
        db.commit()
    notes=client.get('/api/v1/notifications?unread_only=true',headers=h); assert notes.status_code==200 and len(notes.json())==1 and notes.json()[0]['is_read'] is False
    marked=client.post(f"/api/v1/notifications/{notes.json()[0]['id']}/read",headers=h); assert marked.json()['is_read'] is True
    assert client.get('/api/v1/notifications?unread_only=true',headers=h).json()==[]
    audit=client.get('/api/v1/audit-logs?action=notification.read',headers=h); assert audit.status_code==200 and len(audit.json())==1

def test_csv_exports_and_import_validation(client):
    h=auth(client)
    exported=client.get('/api/v1/exports/items.csv',headers=h); assert exported.status_code==200 and 'sku,name' in exported.text
    bad=io.BytesIO(b'sku,name,category_id,base_unit_id\nX,Test,missing,missing\n')
    response=client.post('/api/v1/imports/items.csv',headers=h,files={'file':('items.csv',bad,'text/csv')}); assert response.status_code==422
