def login(client):
    r = client.post('/api/v1/auth/login', json={'email': 'owner@example.com', 'password': 'password123'})
    return {'Authorization': f"Bearer {r.json()['access_token']}"}


def setup_master(client, headers):
    cat = client.post('/api/v1/categories', headers=headers, json={'name': 'Ingredients'}).json()
    unit = client.post('/api/v1/units', headers=headers, json={'code': 'KG', 'name': 'Kilogram'}).json()
    location = client.post('/api/v1/locations', headers=headers, json={'code': 'KITCHEN', 'name': 'Kitchen'}).json()
    chicken = client.post('/api/v1/items', headers=headers, json={
        'sku': 'CHICKEN', 'name': 'Chicken', 'category_id': cat['id'], 'base_unit_id': unit['id'], 'standard_cost': '180'
    }).json()
    rice = client.post('/api/v1/items', headers=headers, json={
        'sku': 'RICE', 'name': 'Rice', 'category_id': cat['id'], 'base_unit_id': unit['id'], 'standard_cost': '60'
    }).json()
    client.post('/api/v1/stock/receipts', headers=headers, json={
        'location_id': location['id'],
        'lines': [
            {'item_id': chicken['id'], 'quantity': '10', 'unit_cost': '180'},
            {'item_id': rice['id'], 'quantity': '20', 'unit_cost': '60'},
        ],
    })
    return location, chicken, rice


def meal_payload(location, chicken, rice, key='meal-1'):
    return {
        'meal_name': 'Chicken adobo',
        'meal_period': 'Lunch',
        'servings': 10,
        'location_id': location['id'],
        'notes': 'Staff lunch',
        'idempotency_key': key,
        'lines': [
            {'item_id': chicken['id'], 'quantity': '2'},
            {'item_id': rice['id'], 'quantity': '3'},
        ],
    }


def test_staff_meal_preview_post_and_reverse(client):
    headers = login(client)
    location, chicken, rice = setup_master(client, headers)
    payload = meal_payload(location, chicken, rice)

    preview = client.post('/api/v1/staff-meals/preview', headers=headers, json=payload)
    assert preview.status_code == 200
    assert preview.json()['total_cost'] == '540.0000'
    assert preview.json()['cost_per_serving'] == '54.0000'

    posted = client.post('/api/v1/staff-meals', headers=headers, json=payload)
    assert posted.status_code == 201
    meal = posted.json()
    assert meal['status'] == 'posted'
    assert meal['meal_name'] == 'Chicken adobo'
    assert len(meal['lines']) == 2
    assert {line['unit_cost'] for line in meal['lines']} == {'180.0000', '60.0000'}

    balances = client.get(f"/api/v1/stock/balances?location_id={location['id']}", headers=headers).json()
    by_item = {row['item_id']: row['quantity'] for row in balances}
    assert by_item[chicken['id']] == '8.0000'
    assert by_item[rice['id']] == '17.0000'

    reversed_response = client.post(f"/api/v1/staff-meals/{meal['id']}/reverse", headers=headers)
    assert reversed_response.status_code == 200
    assert reversed_response.json()['status'] == 'reversed'

    balances = client.get(f"/api/v1/stock/balances?location_id={location['id']}", headers=headers).json()
    by_item = {row['item_id']: row['quantity'] for row in balances}
    assert by_item[chicken['id']] == '10.0000'
    assert by_item[rice['id']] == '20.0000'


def test_staff_meal_idempotency_prevents_double_consumption(client):
    headers = login(client)
    location, chicken, rice = setup_master(client, headers)
    payload = meal_payload(location, chicken, rice, key='same-meal')

    first = client.post('/api/v1/staff-meals', headers=headers, json=payload)
    second = client.post('/api/v1/staff-meals', headers=headers, json=payload)
    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()['id'] == first.json()['id']

    balances = client.get(f"/api/v1/stock/balances?location_id={location['id']}", headers=headers).json()
    by_item = {row['item_id']: row['quantity'] for row in balances}
    assert by_item[chicken['id']] == '8.0000'
    assert by_item[rice['id']] == '17.0000'


def test_staff_meal_rejects_duplicate_ingredient_and_insufficient_stock(client):
    headers = login(client)
    location, chicken, rice = setup_master(client, headers)
    payload = meal_payload(location, chicken, rice)
    payload['lines'] = [
        {'item_id': chicken['id'], 'quantity': '1'},
        {'item_id': chicken['id'], 'quantity': '1'},
    ]
    duplicate = client.post('/api/v1/staff-meals', headers=headers, json=payload)
    assert duplicate.status_code == 409

    payload = meal_payload(location, chicken, rice, key='too-much')
    payload['lines'] = [{'item_id': chicken['id'], 'quantity': '99'}]
    insufficient = client.post('/api/v1/staff-meals', headers=headers, json=payload)
    assert insufficient.status_code == 409
