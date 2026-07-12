def auth_headers(client):
    response = client.post('/api/v1/auth/login', json={'email': 'owner@example.com', 'password': 'password123'})
    assert response.status_code == 200
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def by_code(rows, code):
    return next(row for row in rows if row['code'] == code)


def seed_reusable_item(client, headers):
    dimensions = client.get('/api/v1/classification/bootstrap', headers=headers).json()['dimensions']
    hotel = by_code(dimensions['workspace'], 'hotel')
    linen = by_code(dimensions['item_type'], 'linen')
    available = by_code(dimensions['condition_status'], 'available')
    laundry = by_code(dimensions['condition_status'], 'in-laundry')
    receipt_reason = by_code(dimensions['movement_reason'], 'receipt')
    laundry_reason = by_code(dimensions['movement_reason'], 'laundry')
    category = client.post('/api/v1/categories', headers=headers, json={'name': 'Hotel linen'}).json()
    unit = client.post('/api/v1/units', headers=headers, json={'code': 'PC', 'name': 'Piece', 'precision': 0}).json()
    clean_store = client.post('/api/v1/locations', headers=headers, json={'code': 'LINEN-CLEAN', 'name': 'Clean linen store', 'location_type': 'linen'}).json()
    laundry_room = client.post('/api/v1/locations', headers=headers, json={'code': 'LAUNDRY', 'name': 'Laundry room', 'location_type': 'linen'}).json()
    item_response = client.post('/api/v1/items', headers=headers, json={
        'sku': 'TOWEL-BATH', 'name': 'Bath towel', 'category_id': category['id'], 'base_unit_id': unit['id'],
        'primary_workspace_id': hotel['id'], 'item_type_id': linen['id'],
    })
    assert item_response.status_code == 201
    return item_response.json(), clean_store, laundry_room, available, laundry, receipt_reason, laundry_reason


def test_reusable_property_laundry_circulation_and_balance_control(client):
    headers = auth_headers(client)
    item, clean_store, laundry_room, available, laundry, receipt_reason, laundry_reason = seed_reusable_item(client, headers)
    receipt = client.post('/api/v1/property/movements', headers=headers, json={
        'item_id': item['id'], 'quantity': 20,
        'destination_location_id': clean_store['id'], 'destination_condition_id': available['id'],
        'movement_reason_id': receipt_reason['id'], 'reference': 'Opening linen stock',
    })
    assert receipt.status_code == 201
    sent = client.post('/api/v1/property/movements', headers=headers, json={
        'item_id': item['id'], 'quantity': 8,
        'source_location_id': clean_store['id'], 'source_condition_id': available['id'],
        'destination_location_id': laundry_room['id'], 'destination_condition_id': laundry['id'],
        'movement_reason_id': laundry_reason['id'], 'reference': 'Laundry run 1',
    })
    assert sent.status_code == 201
    balances = client.get('/api/v1/property/balances', headers=headers).json()
    assert any(row['location_id'] == clean_store['id'] and row['condition_id'] == available['id'] and row['quantity'] == '12.000000' for row in balances)
    assert any(row['location_id'] == laundry_room['id'] and row['condition_id'] == laundry['id'] and row['quantity'] == '8.000000' for row in balances)
    rejected = client.post('/api/v1/property/movements', headers=headers, json={
        'item_id': item['id'], 'quantity': 50,
        'source_location_id': clean_store['id'], 'source_condition_id': available['id'],
        'destination_location_id': laundry_room['id'], 'destination_condition_id': laundry['id'],
    })
    assert rejected.status_code == 409


def test_hotel_par_profile_accepts_only_reusable_property(client):
    headers = auth_headers(client)
    item, clean_store, *_ = seed_reusable_item(client, headers)
    response = client.post('/api/v1/hotel/par-profiles', headers=headers, json={
        'code': 'DELUXE-KING', 'name': 'Deluxe King standard linen', 'profile_type': 'room_type',
        'location_id': clean_store['id'], 'lines': [{'item_id': item['id'], 'par_quantity': 2}],
    })
    assert response.status_code == 201
    profiles = client.get('/api/v1/hotel/par-profiles', headers=headers).json()
    assert profiles[0]['profile']['code'] == 'DELUXE-KING'
    assert profiles[0]['lines'][0]['par_quantity'] == '2.000000'
