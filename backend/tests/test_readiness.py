import io
from decimal import Decimal
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.operations import BackupRecord
from app.models.user import User

def auth(client,email='owner@example.com'):
    r=client.post('/api/v1/auth/login',json={'email':email,'password':'password123'})
    return {'Authorization':f"Bearer {r.json()['access_token']}"}
def approver(client):
    with SessionLocal() as db:
        if not db.query(User).filter(User.email=='readiness-approver@example.com').first(): db.add(User(email='readiness-approver@example.com',full_name='Approver',password_hash=hash_password('password123'),role='owner')); db.commit()
    return auth(client,'readiness-approver@example.com')
def masters(client,h):
    cat=client.post('/api/v1/categories',headers=h,json={'name':'Readiness'}).json(); unit=client.post('/api/v1/units',headers=h,json={'code':'EA','name':'Each'}).json(); loc=client.post('/api/v1/locations',headers=h,json={'code':'MAIN','name':'Main'}).json(); item=client.post('/api/v1/items',headers=h,json={'sku':'TEST','name':'Test Item','category_id':cat['id'],'base_unit_id':unit['id'],'standard_cost':'10'}).json(); supplier=client.post('/api/v1/suppliers',headers=h,json={'code':'SUP','name':'Supplier'}).json(); return item,loc,supplier

def test_csv_validation_and_apply(client):
    h=auth(client); content=b'sku,name,category,unit,minimum_stock,standard_cost\nCOFFEE,Coffee Beans,Beverage,KG,5,450\n'
    response=client.post('/api/v1/migration/imports/items/validate',headers=h,files={'file':('items.csv',io.BytesIO(content),'text/csv')}); assert response.status_code==201 and response.json()['status']=='validated'
    applied=client.post(f"/api/v1/migration/imports/{response.json()['job_id']}/apply",headers=h); assert applied.status_code==200 and applied.json()['summary']['created']==1
    items=client.get('/api/v1/items?q=COFFEE',headers=h).json(); assert len(items)==1 and Decimal(items[0]['standard_cost'])==Decimal('450')
    duplicate=client.post(f"/api/v1/migration/imports/{response.json()['job_id']}/apply",headers=h); assert duplicate.status_code==409

def test_invalid_import_cannot_be_applied(client):
    h=auth(client); content=b'sku,name,category,unit\n,Missing SKU,Food,EA\n'
    response=client.post('/api/v1/migration/imports/items/validate',headers=h,files={'file':('bad.csv',io.BytesIO(content),'text/csv')}); assert response.status_code==201 and response.json()['status']=='invalid' and response.json()['errors']
    applied=client.post(f"/api/v1/migration/imports/{response.json()['job_id']}/apply",headers=h); assert applied.status_code==409

def test_printable_po_and_safe_cancellation(client):
    h=auth(client); other=approver(client); item,loc,supplier=masters(client,h)
    req=client.post('/api/v1/requisitions',headers=h,json={'department':'Cafe','lines':[{'item_id':item['id'],'quantity':'2','estimated_unit_cost':'10'}]}).json(); client.post(f"/api/v1/requisitions/{req['id']}/approve",headers=other)
    po=client.post('/api/v1/purchase-orders',headers=h,json={'supplier_id':supplier['id'],'requisition_id':req['id'],'delivery_location_id':loc['id'],'lines':[{'item_id':item['id'],'ordered_quantity':'2','unit_price':'10'}]}).json()
    printable=client.get(f"/api/v1/print/purchase-orders/{po['id']}",headers=h); assert printable.status_code==200 and Decimal(printable.json()['totals']['grand_total'])==Decimal('20')
    cancelled=client.post(f"/api/v1/purchase-orders/{po['id']}/cancel",headers=h); assert cancelled.status_code==200 and cancelled.json()['status']=='cancelled'
    req_cancel=client.post(f"/api/v1/requisitions/{req['id']}/cancel",headers=h); assert req_cancel.status_code==200

def test_deployment_and_acceptance_checks(client):
    h=auth(client); item,loc,_=masters(client,h)
    client.post('/api/v1/stock/receipts',headers=h,json={'location_id':loc['id'],'lines':[{'item_id':item['id'],'quantity':'3','unit_cost':'10'}]})
    with SessionLocal() as db: db.add(BackupRecord(filename='inventory-test.sql.gz',status='completed',size_bytes=10,checksum_sha256='a'*64)); db.commit()
    status=client.get('/api/v1/deployment/status',headers=h); assert status.status_code==200 and status.json()['database']=='ok' and status.json()['latest_backup_at']
    run=client.post('/api/v1/acceptance-runs',headers=h,json={'environment':'test'}); assert run.status_code==201 and run.json()['status']=='passed' and run.json()['results']['stock_reconciliation']['passed'] is True

def test_security_headers(client):
    response=client.get('/api/v1/health'); assert response.status_code==200
    assert response.headers['x-content-type-options']=='nosniff' and response.headers['x-frame-options']=='DENY' and response.headers['content-security-policy']


def test_read_only_roles_cannot_create_acceptance_runs(client):
    from sqlalchemy import func, select
    from app.models.readiness import AcceptanceRun

    with SessionLocal() as db:
        db.add_all([
            User(email='readiness-viewer@example.com', full_name='Viewer',
                 password_hash=hash_password('password123'), role='viewer'),
            User(email='readiness-procurement@example.com', full_name='Procurement Officer',
                 password_hash=hash_password('password123'), role='procurement_officer'),
            User(email='readiness-manager@example.com', full_name='Inventory Manager',
                 password_hash=hash_password('password123'), role='inventory_manager'),
        ])
        db.commit()

    for email in ('readiness-viewer@example.com', 'readiness-procurement@example.com'):
        headers = auth(client, email)
        # Reporting remains available, but creating UAT records is a write.
        assert client.get('/api/v1/acceptance-runs', headers=headers).status_code == 200
        assert client.get('/api/v1/deployment/status', headers=headers).status_code == 200
        denied = client.post('/api/v1/acceptance-runs', headers=headers,
                             json={'environment': 'production-candidate'})
        assert denied.status_code == 403

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AcceptanceRun)) == 0
    # Inventory managers have actual inventory write authority.
    allowed = client.post('/api/v1/acceptance-runs',
                          headers=auth(client, 'readiness-manager@example.com'),
                          json={'environment': 'test'})
    assert allowed.status_code == 201
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AcceptanceRun)) == 1


def test_deployment_status_does_not_claim_unversioned_database_is_at_head(client):
    response = client.get('/api/v1/deployment/status', headers=auth(client))
    assert response.status_code == 200
    state = response.json()
    # Unit-test SQLite schema is created directly, without applying Alembic.
    assert state['migrations'] == 'unversioned'
    assert state['status'] == 'attention'
