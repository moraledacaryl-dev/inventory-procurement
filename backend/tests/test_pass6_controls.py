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



def test_access_scope_roster_and_limits_are_owner_only(client):
    from app.core.security import hash_password
    from app.db.session import SessionLocal
    from app.models.user import User

    with SessionLocal() as db:
        db.add_all([
            User(
                email=f'scope-{role}@example.com',
                full_name=f'Scope {role}',
                password_hash=hash_password('password123'),
                role=role,
            )
            for role in ('inventory_manager', 'procurement_officer',
                         'receiver', 'counter', 'viewer')
        ])
        db.commit()

    for role in ('inventory_manager', 'procurement_officer', 'receiver', 'counter', 'viewer'):
        login = client.post('/api/v1/auth/login', json={
            'email': f'scope-{role}@example.com', 'password': 'password123'})
        assert login.status_code == 200
        headers = {'Authorization': f"Bearer {login.json()['access_token']}"}
        assert client.get('/api/v1/access-scope-users', headers=headers).status_code == 403
        assert client.get('/api/v1/access-scopes', headers=headers).status_code == 403
        assert client.get('/api/v1/access-scopes?user_id=some-other-user', headers=headers).status_code == 403

    owner = auth_headers(client)
    assert client.get('/api/v1/access-scope-users', headers=owner).status_code == 200
    assert client.get('/api/v1/access-scopes', headers=owner).status_code == 200


def test_operating_summary_uses_recorded_stock_book_cost_not_standard_cost(client):
    headers = auth_headers(client)
    category = client.post('/api/v1/categories', headers=headers,
                           json={'name': 'Book Cost Test'}).json()
    unit = client.post('/api/v1/units', headers=headers,
                       json={'code': 'EACH', 'name': 'Each'}).json()
    location = client.post('/api/v1/locations', headers=headers,
                           json={'code': 'BOOK', 'name': 'Book Location'}).json()
    item_response = client.post('/api/v1/items', headers=headers, json={
        'sku': 'BOOK-TEST', 'name': 'Book valuation item',
        'category_id': category['id'], 'base_unit_id': unit['id'],
        'standard_cost': '250.00',
    })
    assert item_response.status_code == 201
    item = item_response.json()

    receipt = client.post('/api/v1/stock/receipts', headers=headers, json={
        'location_id': location['id'],
        'lines': [{'item_id': item['id'], 'quantity': '3', 'unit_cost': '11.50'}],
    })
    assert receipt.status_code in (200, 201), receipt.text

    summary = client.get('/api/v1/reports/operating-summary', headers=headers)
    assert summary.status_code == 200
    assert Decimal(summary.json()['stock_units']) == Decimal('3')
    assert Decimal(summary.json()['stock_value']) == Decimal('34.50')
    # The configured standard cost would incorrectly report 3 * 250 = 750.
