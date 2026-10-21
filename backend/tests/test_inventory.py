def login(client):
    r=client.post('/api/v1/auth/login',json={'email':'owner@example.com','password':'password123'})
    return {'Authorization':f"Bearer {r.json()['access_token']}"}
def setup_master(client,h):
    cat=client.post('/api/v1/categories',headers=h,json={'name':'Beverages'}).json(); unit=client.post('/api/v1/units',headers=h,json={'code':'EA','name':'Each'}).json(); a=client.post('/api/v1/locations',headers=h,json={'code':'MAIN','name':'Main Store'}).json(); b=client.post('/api/v1/locations',headers=h,json={'code':'BAR','name':'Bar'}).json(); item=client.post('/api/v1/items',headers=h,json={'sku':'COKE-1','name':'Coke','category_id':cat['id'],'base_unit_id':unit['id'],'minimum_stock':'2','standard_cost':'40'}).json(); return item,a,b
def test_inventory_flow(client):
    h=login(client); item,a,b=setup_master(client,h)
    r=client.post('/api/v1/stock/receipts',headers=h,json={'location_id':a['id'],'idempotency_key':'receipt-1','lines':[{'item_id':item['id'],'quantity':'10','unit_cost':'40'}]}); assert r.status_code==201
    same=client.post('/api/v1/stock/receipts',headers=h,json={'location_id':a['id'],'idempotency_key':'receipt-1','lines':[{'item_id':item['id'],'quantity':'10','unit_cost':'40'}]}); assert same.json()['id']==r.json()['id']
    t=client.post('/api/v1/stock/transfers',headers=h,json={'source_location_id':a['id'],'destination_location_id':b['id'],'lines':[{'item_id':item['id'],'quantity':'3'}]}); assert t.status_code==201 and len(t.json()['movements'])==2
    i=client.post('/api/v1/stock/issues',headers=h,json={'location_id':b['id'],'lines':[{'item_id':item['id'],'quantity':'1','unit_cost':'999'}]}); assert i.status_code==201
    assert i.json()['movements'][0]['unit_cost']=='40.0000'
    balances=client.get('/api/v1/stock/balances',headers=h).json(); values={x['location_id']:x['quantity'] for x in balances}; costs={x['location_id']:x['average_cost'] for x in balances}
    assert values[a['id']]=='7.0000' and values[b['id']]=='2.0000'
    assert costs[b['id']]=='40.0000'
def test_negative_stock_is_blocked(client):
    h=login(client); item,a,_=setup_master(client,h); r=client.post('/api/v1/stock/issues',headers=h,json={'location_id':a['id'],'lines':[{'item_id':item['id'],'quantity':'1'}]}); assert r.status_code==409
def test_count_posts_variance(client):
    h=login(client); item,a,_=setup_master(client,h); client.post('/api/v1/stock/receipts',headers=h,json={'location_id':a['id'],'lines':[{'item_id':item['id'],'quantity':'5','unit_cost':'40'}]}); count=client.post('/api/v1/counts',headers=h,json={'location_id':a['id']}).json(); posted=client.post(f"/api/v1/counts/{count['id']}/post",headers=h,json={'lines':[{'item_id':item['id'],'counted_quantity':'4'}]}); assert posted.status_code==200 and posted.json()['status']=='posted'; bal=client.get(f"/api/v1/stock/balances?item_id={item['id']}&location_id={a['id']}",headers=h).json()[0]; assert bal['quantity']=='4.0000'


def test_negative_movement_cost_is_rejected_by_stock_service(client):
    from decimal import Decimal
    from app.db.session import SessionLocal
    from app.models.user import User
    from app.services.inventory import InventoryError, post_document
    from sqlalchemy import select
    import pytest

    h = login(client)
    item, location, _ = setup_master(client, h)
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        with pytest.raises(InventoryError, match="unit cost cannot be negative"):
            post_document(db, kind="receipt", actor_id=owner.id, entries=[{
                "item_id": item["id"], "location_id": location["id"],
                "quantity": Decimal("2"), "unit_cost": Decimal("-10"),
            }])
        db.rollback()


def test_negative_stock_replenishment_does_not_inflate_average_cost(client):
    from decimal import Decimal
    from app.db.session import SessionLocal
    from app.models.user import User
    from app.models.inventory import Item, StockBalance
    from app.services.inventory import post_document
    from sqlalchemy import select

    h = login(client)
    item, location, _ = setup_master(client, h)
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        stock_item = db.get(Item, item["id"])
        stock_item.allow_negative_stock = True
        db.commit()
        post_document(db, kind="issue", actor_id=owner.id, entries=[{
            "item_id": item["id"], "location_id": location["id"],
            "quantity": Decimal("-5"),
        }])
        post_document(db, kind="receipt", actor_id=owner.id, entries=[{
            "item_id": item["id"], "location_id": location["id"],
            "quantity": Decimal("10"), "unit_cost": Decimal("120"),
        }])
        balance = db.scalar(select(StockBalance).where(
            StockBalance.item_id == item["id"],
            StockBalance.location_id == location["id"],
        ))
        assert balance.quantity == Decimal("5")
        assert balance.average_cost == Decimal("120")


def test_transfer_preserves_source_average_cost(client):
    from decimal import Decimal
    h = login(client)
    item, source, destination = setup_master(client, h)
    first = client.post('/api/v1/stock/receipts', headers=h, json={
        'location_id': source['id'],
        'lines': [{'item_id': item['id'], 'quantity': '10', 'unit_cost': '40'}],
    })
    assert first.status_code == 201
    second = client.post('/api/v1/stock/receipts', headers=h, json={
        'location_id': source['id'],
        'lines': [{'item_id': item['id'], 'quantity': '10', 'unit_cost': '60'}],
    })
    assert second.status_code == 201
    transfer = client.post('/api/v1/stock/transfers', headers=h, json={
        'source_location_id': source['id'], 'destination_location_id': destination['id'],
        'lines': [{'item_id': item['id'], 'quantity': '4', 'unit_cost': '999'}],
    })
    assert transfer.status_code == 201
    assert [Decimal(m['unit_cost']) for m in transfer.json()['movements']] == [Decimal('50'), Decimal('50')]
    balances = client.get('/api/v1/stock/balances', headers=h).json()
    by_location = {row['location_id']: row for row in balances}
    assert Decimal(by_location[source['id']]['quantity']) == Decimal('16')
    assert Decimal(by_location[destination['id']]['quantity']) == Decimal('4')
    assert Decimal(by_location[source['id']]['average_cost']) == Decimal('50')
    assert Decimal(by_location[destination['id']]['average_cost']) == Decimal('50')


def test_positive_count_adjustment_preserves_existing_stock_value(client):
    from decimal import Decimal
    h = login(client)
    item, location, _ = setup_master(client, h)
    receipt = client.post('/api/v1/stock/receipts', headers=h, json={
        'location_id': location['id'],
        'lines': [{'item_id': item['id'], 'quantity': '10', 'unit_cost': '40'}],
    })
    assert receipt.status_code == 201
    count = client.post('/api/v1/counts', headers=h, json={
        'location_id': location['id'],
    })
    assert count.status_code == 201
    posted = client.post(f"/api/v1/counts/{count.json()['id']}/post", headers=h, json={
        'lines': [{'item_id': item['id'], 'counted_quantity': '12'}],
    })
    assert posted.status_code == 200
    assert posted.json()['status'] == 'posted'
    balance = client.get('/api/v1/stock/balances', headers=h).json()
    matching = next(x for x in balance if x['item_id'] == item['id'] and x['location_id'] == location['id'])
    assert Decimal(matching['quantity']) == Decimal('12')
    assert Decimal(matching['average_cost']) == Decimal('40')


def test_positive_manual_adjustment_uses_standard_cost_without_balance(client):
    from decimal import Decimal
    h = login(client)
    item, location, _ = setup_master(client, h)
    response = client.post('/api/v1/stock/adjustments', headers=h, json={
        'location_id': location['id'],
        'lines': [{'item_id': item['id'], 'quantity_delta': '3',
                   'unit_cost': '0', 'reason': 'opening count correction'}],
    })
    assert response.status_code == 201
    assert Decimal(response.json()['movements'][0]['unit_cost']) == Decimal('40')
    balance = client.get('/api/v1/stock/balances', headers=h).json()
    matching = next(x for x in balance if x['item_id'] == item['id'] and x['location_id'] == location['id'])
    assert Decimal(matching['quantity']) == Decimal('3')
    assert Decimal(matching['average_cost']) == Decimal('40')


def test_concurrent_first_balance_creation_is_serialized_on_postgres(client):
    from concurrent.futures import ThreadPoolExecutor
    from decimal import Decimal
    from threading import Event
    from sqlalchemy import func, select
    from app.db.session import SessionLocal, engine
    from app.models.inventory import StockBalance
    from app.services.inventory import _balance
    import pytest

    if engine.dialect.name != 'postgresql':
        pytest.skip('PostgreSQL advisory locks are specific to PostgreSQL')
    h = login(client)
    item, location, _ = setup_master(client, h)
    item_id, location_id = item['id'], location['id']
    first_holds_lock = Event()
    release_first = Event()
    second_started = Event()
    second_finished = Event()

    def first_writer():
        with SessionLocal() as db:
            row = _balance(db, item_id, location_id)
            row.quantity = Decimal(row.quantity) + Decimal('5')
            db.flush()
            first_holds_lock.set()
            assert release_first.wait(timeout=10)
            db.commit()

    def second_writer():
        assert first_holds_lock.wait(timeout=10)
        second_started.set()
        with SessionLocal() as db:
            row = _balance(db, item_id, location_id)
            row.quantity = Decimal(row.quantity) + Decimal('7')
            db.commit()
        second_finished.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(first_writer)
        assert first_holds_lock.wait(timeout=10)
        second = pool.submit(second_writer)
        try:
            assert second_started.wait(timeout=10)
            assert not second_finished.wait(timeout=0.25), 'second posting bypassed the balance lock'
        finally:
            release_first.set()
        first.result(timeout=15)
        second.result(timeout=15)

    with SessionLocal() as db:
        rows = db.scalars(select(StockBalance).where(
            StockBalance.item_id == item_id, StockBalance.location_id == location_id,
        )).all()
        assert len(rows) == 1
        assert Decimal(rows[0].quantity) == Decimal('12')


def test_stock_request_replay_is_bound_to_original_payload(client):
    from decimal import Decimal
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.inventory import StockDocument, StockBalance

    headers = login(client)
    item, location, _ = setup_master(client, headers)
    original = {
        'location_id': location['id'],
        'idempotency_key': 'replay-original-payload',
        'reference': 'DELIVERY-001',
        'lines': [{'item_id': item['id'], 'quantity': '5', 'unit_cost': '40'}],
    }
    first = client.post('/api/v1/stock/receipts', headers=headers, json=original)
    assert first.status_code == 201
    equivalent = {**original, 'lines': [{**original['lines'][0], 'quantity': '5.00', 'unit_cost': '40.000'}]}
    replay = client.post('/api/v1/stock/receipts', headers=headers, json=equivalent)
    assert replay.status_code == 201
    assert replay.json()['id'] == first.json()['id']
    for changed in (
        {**original, 'reference': 'DELIVERY-002'},
        {**original, 'lines': [{**original['lines'][0], 'quantity': '6'}]},
        {**original, 'lines': [{**original['lines'][0], 'unit_cost': '41'}]},
    ):
        conflict = client.post('/api/v1/stock/receipts', headers=headers, json=changed)
        assert conflict.status_code == 409
        assert 'Idempotency key' in conflict.json()['detail']

    cross_type = client.post('/api/v1/stock/issues', headers=headers, json={
        'location_id': location['id'], 'idempotency_key': original['idempotency_key'],
        'lines': [{'item_id': item['id'], 'quantity': '2'}],
    })
    assert cross_type.status_code == 409
    with SessionLocal() as db:
        documents = db.scalars(select(StockDocument).where(
            StockDocument.idempotency_key == original['idempotency_key']
        )).all()
        assert len(documents) == 1
        assert len(documents[0].request_fingerprint) == 64
        balance = db.scalar(select(StockBalance).where(
            StockBalance.item_id == item['id'], StockBalance.location_id == location['id']
        ))
        assert Decimal(balance.quantity) == Decimal('5')


def test_historical_stock_document_replay_checks_original_movements(client):
    from app.db.session import SessionLocal
    from app.models.inventory import StockDocument

    headers = login(client)
    item, location, _ = setup_master(client, headers)
    original = {
        'location_id': location['id'],
        'idempotency_key': 'pre-fingerprint-document',
        'lines': [{'item_id': item['id'], 'quantity': '3', 'unit_cost': '40'}],
    }
    first = client.post('/api/v1/stock/receipts', headers=headers, json=original)
    assert first.status_code == 201
    with SessionLocal() as db:
        document = db.get(StockDocument, first.json()['id'])
        document.request_fingerprint = None
        db.commit()
    identical = client.post('/api/v1/stock/receipts', headers=headers, json=original)
    assert identical.status_code == 201
    assert identical.json()['id'] == first.json()['id']
    altered = client.post('/api/v1/stock/receipts', headers=headers, json={
        **original,
        'lines': [{**original['lines'][0], 'quantity': '4'}],
    })
    assert altered.status_code == 409


def test_legacy_count_rejects_stale_snapshot_and_incomplete_lines(client):
    from decimal import Decimal
    from app.db.session import SessionLocal
    from app.models.inventory import StockBalance
    from sqlalchemy import select

    headers = login(client)
    item, location, _ = setup_master(client, headers)
    assert client.post('/api/v1/stock/receipts', headers=headers, json={
        'location_id': location['id'], 'lines': [{'item_id': item['id'], 'quantity': 5, 'unit_cost': 40}]
    }).status_code == 201
    count = client.post('/api/v1/counts', headers=headers, json={'location_id': location['id']}).json()
    endpoint = f"/api/v1/counts/{count['id']}/post"
    assert client.post(endpoint, headers=headers, json={'lines': [
        {'item_id': item['id'], 'counted_quantity': 4},
        {'item_id': item['id'], 'counted_quantity': 4},
    ]}).status_code == 422
    assert client.post('/api/v1/stock/receipts', headers=headers, json={
        'location_id': location['id'], 'lines': [{'item_id': item['id'], 'quantity': 1, 'unit_cost': 40}]
    }).status_code == 201
    stale = client.post(endpoint, headers=headers, json={
        'lines': [{'item_id': item['id'], 'counted_quantity': 4}]
    })
    assert stale.status_code == 409
    assert 'count' in stale.json()['detail'].lower()
    with SessionLocal() as db:
        row = db.scalar(select(StockBalance).where(
            StockBalance.item_id == item['id'], StockBalance.location_id == location['id']
        ))
        assert Decimal(row.quantity) == Decimal('6')
