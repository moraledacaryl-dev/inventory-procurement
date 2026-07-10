from app.db.session import SessionLocal
from app.models.operations import BackupRecord

def auth(client):
    login=client.post('/api/v1/auth/login',json={'email':'owner@example.com','password':'password123'})
    return {'Authorization':f"Bearer {login.json()['access_token']}"}

def test_feedback_lifecycle_and_rollout_hold(client):
    h=auth(client)
    created=client.post('/api/v1/feedback',headers=h,json={'category':'bug','severity':'critical','page':'stock','message':'Stock issue button failed during pilot'}); assert created.status_code==201
    summary=client.get('/api/v1/rollout/summary',headers=h).json(); assert summary['status']=='hold' and summary['high_priority_feedback']==1
    resolved=client.patch(f"/api/v1/feedback/{created.json()['id']}",headers=h,json={'status':'resolved'}); assert resolved.status_code==200 and resolved.json()['status']=='resolved'
    summary=client.get('/api/v1/rollout/summary',headers=h).json(); assert summary['high_priority_feedback']==0

def test_incident_lifecycle(client):
    h=auth(client)
    created=client.post('/api/v1/incidents',headers=h,json={'source':'api','severity':'critical','title':'POS webhook failure','details':'Webhook returned a request ID for investigation','request_id':'req-123'}); assert created.status_code==201 and created.json()['incident_number'].startswith('INC-')
    incident_id=created.json()['id']
    acknowledged=client.patch(f'/api/v1/incidents/{incident_id}',headers=h,json={'status':'acknowledged'}); assert acknowledged.status_code==200 and acknowledged.json()['acknowledged_at']
    resolved=client.patch(f'/api/v1/incidents/{incident_id}',headers=h,json={'status':'resolved'}); assert resolved.status_code==200 and resolved.json()['resolved_at']

def test_smoke_test_requires_backup_and_reconciles_ledger(client):
    h=auth(client)
    failed=client.post('/api/v1/rollout/smoke-test',headers=h).json(); assert failed['status']=='failed' and failed['checks']['backup_present'] is False
    with SessionLocal() as db:
        db.add(BackupRecord(filename='pilot.sql.gz',status='completed',size_bytes=100,checksum_sha256='b'*64)); db.commit()
    passed=client.post('/api/v1/rollout/smoke-test',headers=h).json(); assert passed['status']=='passed' and all(passed['checks'].values())

def test_feedback_validation(client):
    h=auth(client)
    bad=client.post('/api/v1/feedback',headers=h,json={'category':'unknown','severity':'normal','message':'bad'}); assert bad.status_code==422
