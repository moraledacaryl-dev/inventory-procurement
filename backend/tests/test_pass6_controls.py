from decimal import Decimal


def auth_headers(client):
    response=client.post('/api/v1/auth/login',json={'email':'owner@example.com','password':'password123'})
    assert response.status_code==200
    return {'Authorization':f"Bearer {response.json()['access_token']}"}


def test_operating_summary_saved_view_and_migration_review(client):
    h=auth_headers(client)
    summary=client.get('/api/v1/reports/operating-summary',headers=h)
    assert summary.status_code==200
    assert Decimal(summary.json()['stock_value'])>=0
    saved=client.post('/api/v1/saved-views',headers=h,json={'module_key':'operating-summary','name':'Owner summary','filters':{'workspace_id':''},'columns':['stock_value'],'is_default':True})
    assert saved.status_code==201
    views=client.get('/api/v1/saved-views?module_key=operating-summary',headers=h)
    assert views.status_code==200 and views.json()[0]['name']=='Owner summary'
    review=client.get('/api/v1/classification/migration-review',headers=h)
    assert review.status_code==200


def test_operational_access_scope(client):
    h=auth_headers(client)
    users=client.get('/api/v1/access-scope-users',headers=h)
    assert users.status_code==200
    owner=users.json()[0]
    workspaces=client.get('/api/v1/classification/dimensions?dimension_type=workspace&active=true',headers=h).json()
    response=client.post('/api/v1/access-scopes',headers=h,json={'user_id':owner['id'],'workspace_id':workspaces[0]['id'],'approval_limit':25000})
    assert response.status_code==201
    scopes=client.get(f"/api/v1/access-scopes?user_id={owner['id']}",headers=h)
    assert scopes.status_code==200
    assert Decimal(str(scopes.json()[0]['approval_limit']))==Decimal('25000')
