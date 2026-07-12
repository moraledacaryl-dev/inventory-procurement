def auth_headers(client):
    response = client.post('/api/v1/auth/login', json={'email':'owner@example.com','password':'password123'})
    assert response.status_code == 200
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def by_code(rows, code):
    return next(row for row in rows if row['code'] == code)


def masters(client, headers):
    structure = client.get('/api/v1/classification/bootstrap', headers=headers).json()['dimensions']
    categories = client.get('/api/v1/categories', headers=headers).json()
    category = categories[0] if categories else client.post('/api/v1/categories', headers=headers, json={'name':'Pass 2'}).json()
    units = client.get('/api/v1/units', headers=headers).json()
    unit = units[0] if units else client.post('/api/v1/units', headers=headers, json={'code':'EA','name':'Each','precision':0}).json()
    return structure, category, unit


def make_item(client, headers, sku, workspace, item_type, category, unit):
    response = client.post('/api/v1/items', headers=headers, json={
        'sku': sku,
        'name': sku.replace('-', ' ').title(),
        'category_id': category['id'],
        'base_unit_id': unit['id'],
        'primary_workspace_id': workspace['id'],
        'item_type_id': item_type['id'],
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_recipe_options_are_derived_from_fnb_classification(client):
    headers = auth_headers(client)
    structure, category, unit = masters(client, headers)
    fnb = by_code(structure['workspace'], 'fnb')
    hotel = by_code(structure['workspace'], 'hotel')
    ingredient_type = by_code(structure['item_type'], 'ingredient')
    output_type = by_code(structure['item_type'], 'finished-fnb-product')
    amenity_type = by_code(structure['item_type'], 'guest-amenity')
    ingredient = make_item(client, headers, 'PASS2-FLOUR', fnb, ingredient_type, category, unit)
    output = make_item(client, headers, 'PASS2-CAKE', fnb, output_type, category, unit)
    amenity = make_item(client, headers, 'PASS2-SHAMPOO', hotel, amenity_type, category, unit)

    options = client.get('/api/v1/recipes/item-options', headers=headers)
    assert options.status_code == 200
    payload = options.json()
    assert ingredient['id'] in {row['id'] for row in payload['ingredients']}
    assert output['id'] in {row['id'] for row in payload['outputs']}
    assert amenity['id'] not in {row['id'] for row in payload['ingredients']}
    assert amenity['id'] not in {row['id'] for row in payload['outputs']}

    created = client.post('/api/v1/recipes', headers=headers, json={
        'code':'PASS2-RECIPE', 'name':'Pass 2 recipe', 'output_item_id':output['id'], 'yield_quantity':1,
        'lines':[{'ingredient_item_id':ingredient['id'],'quantity':1,'waste_factor':0,'optional':False}],
    })
    assert created.status_code == 201, created.text

    blocked = client.post('/api/v1/recipes', headers=headers, json={
        'code':'PASS2-BLOCKED', 'name':'Blocked hotel ingredient', 'output_item_id':output['id'], 'yield_quantity':1,
        'lines':[{'ingredient_item_id':amenity['id'],'quantity':1,'waste_factor':0,'optional':False}],
    })
    assert blocked.status_code == 422
