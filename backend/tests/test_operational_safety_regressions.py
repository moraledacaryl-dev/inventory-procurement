"""Financial events, reservations and rejected deliveries retain their evidence."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Barrier

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal, engine
from app.models.inventory import StockBalance, StockDocument
from app.models.inventory_operations import StockReservation
from app.models.operations import IntegrationEvent
from app.models.procurement import PurchaseOrder
from app.models.user import User
from app.schemas.staff_meals import StaffMealCreate
from app.services.staff_meals import post_staff_meal
from tests.test_pos_sync import auth_headers, pos_headers, seed_mapping
from tests.test_receiving_workspace import seed_receiving
from tests.test_staff_meals import setup_master, meal_payload


@pytest.mark.parametrize('event_type', ['sale_refunded', 'sale_voided'])
def test_financial_event_keeps_consumption_and_allows_physical_waste_record(client, event_type):
    headers = auth_headers(client)
    location, ingredient, _, _ = seed_mapping(client, headers)
    service = pos_headers()
    sale = dict(external_event_id='original', external_sale_id='sale-safe',
                event_type='sale_completed', lines=[dict(external_product_id='CAFE-001', quantity=2)])
    original = client.post('/api/v1/integrations/pos/events', headers=service, json=sale)
    assert original.status_code == 201
    with SessionLocal() as db:
        docs_before = db.query(StockDocument).count()
        events_before = db.query(IntegrationEvent).count()
    financial = {**sale, 'external_event_id': 'financial', 'event_type': event_type}
    for _ in range(2):
        response = client.post('/api/v1/integrations/pos/events', headers=service, json=financial)
        assert response.status_code == 201, response.text
        assert response.json()['stock_document_id'] is None
        assert response.json()['reversal_of_event_id'] == original.json()['id']
    # A financial refund does not consume the physical return allowance.
    waste = {**sale, 'external_event_id': 'physical', 'event_type': 'sale_returned',
             'lines': [dict(external_product_id='CAFE-001', quantity=2, inventory_disposition='waste')]}
    assert client.post('/api/v1/integrations/pos/events', headers=service, json=waste).status_code == 201
    assert client.post('/api/v1/integrations/pos/events', headers=service,
                       json={**waste, 'external_event_id': 'extra-physical'}).status_code == 409
    with SessionLocal() as db:
        assert db.query(StockDocument).count() == docs_before
        assert db.query(IntegrationEvent).count() == events_before
        balance = db.scalar(select(StockBalance).where(StockBalance.item_id == ingredient['id'], StockBalance.location_id == location['id']))
        assert balance.quantity == Decimal('96')


@pytest.mark.parametrize('event_type', ['sale_refunded', 'sale_voided'])
@pytest.mark.parametrize('lines', [
    [dict(external_product_id='CAFE-001', quantity=1, inventory_disposition='restore_stock')],
    [dict(external_product_id='CAFE-001', quantity=3)],
    [dict(external_product_id='unknown', quantity=1)],
    [dict(external_product_id='CAFE-001', quantity=2), dict(external_product_id='CAFE-001', quantity=1)],
])
def test_invalid_financial_stock_claims_leave_sale_unchanged(client, event_type, lines):
    headers = auth_headers(client)
    seed_mapping(client, headers)
    service = pos_headers()
    sale = dict(external_event_id='original', external_sale_id='safe-sale', event_type='sale_completed',
                lines=[dict(external_product_id='CAFE-001', quantity=2)])
    assert client.post('/api/v1/integrations/pos/events', headers=service, json=sale).status_code == 201
    response = client.post('/api/v1/integrations/pos/events', headers=service,
                           json={**sale, 'external_event_id': 'invalid', 'event_type': event_type, 'lines': lines})
    assert response.status_code == 409
    # Refused request does not occupy the lifecycle identity.
    assert client.post('/api/v1/integrations/pos/events', headers=service,
                       json={**sale, 'external_event_id': 'valid', 'event_type': event_type}).status_code == 201


@pytest.mark.parametrize('endpoint', ['generic', 'accounting'])
@pytest.mark.parametrize('status,payload,allowed', [
    ('completed', {}, False), ('pending', {}, False), ('processing', {}, False),
    ('failed', {'accounting_receipt': {'accepted': True}}, False),
    ('dead_letter', {'accounting_intake': {'status': 'accepted'}}, False),
    ('failed', {'accounting_intake': {'status': 'ready_for_review'}}, False),
    ('failed', {'accounting_reconciliation': {'journal_status': 'posted'}}, False),
    ('dead_letter', {'accounting_reconciliation': {'ledger_posting_confirmed': True}}, False),
    ('failed', {}, True), ('dead_letter', {}, True),
])
def test_both_retry_routes_protect_delivered_obligations(client, endpoint, status, payload, allowed):
    headers = auth_headers(client)
    with SessionLocal() as db:
        event = IntegrationEvent(direction='outbound', source_system='inventory', destination_system='accounting',
            event_type='inventory.stock_document.posted', aggregate_type='stock_document', aggregate_id='original-doc',
            idempotency_key='same-obligation', status=status, attempts=3,
            payload={'total_cost': '12', **payload}, last_error='original-error')
        db.add(event); db.commit(); event_id = event.id
    path = f'/api/v1/integration-events/{event_id}/retry' if endpoint == 'generic' else f'/api/v1/integrations/accounting/events/{event_id}/requeue'
    response = client.post(path, headers=headers)
    assert response.status_code == (200 if allowed else 409), response.text
    with SessionLocal() as db:
        event = db.get(IntegrationEvent, event_id)
        assert event.status == ('pending' if allowed else status)
        assert event.attempts == (0 if allowed else 3)
        assert event.idempotency_key == 'same-obligation'
        assert event.aggregate_id == 'original-doc'
        assert event.payload == {'total_cost': '12', **payload}


def test_staff_meal_preview_and_post_protect_reservation_and_replay(client):
    headers = auth_headers(client)
    location, chicken, rice = setup_master(client, headers)
    payload = meal_payload(location, chicken, rice)
    preview = client.post('/api/v1/staff-meals/preview', headers=headers, json=payload)
    assert preview.status_code == 200
    # Reservation created after preview must still block the actual posting.
    reservation = client.post('/api/v1/reservations', headers=headers,
        json={'item_id': chicken['id'], 'location_id': location['id'], 'quantity': '9', 'reference_type': 'event', 'reference_id': 'reserved-party'})
    assert reservation.status_code == 201, reservation.text
    for endpoint in ['/api/v1/staff-meals/preview', '/api/v1/staff-meals']:
        blocked = client.post(endpoint, headers=headers, json=payload)
        assert blocked.status_code == 409, blocked.text
        assert 'reserved' in blocked.text
    with SessionLocal() as db:
        assert db.scalar(select(StockBalance.quantity).where(StockBalance.item_id == chicken['id'], StockBalance.location_id == location['id'])) == Decimal('10')
        reserved = db.get(StockReservation, reservation.json()['id'])
        reserved.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    payload['lines'] = [{'item_id': chicken['id'], 'quantity': '10'}]
    first = client.post('/api/v1/staff-meals', headers=headers, json=payload)
    assert first.status_code == 201, first.text
    # Retry after the meal used all stock must return original, not fail availability.
    replay = client.post('/api/v1/staff-meals', headers=headers, json=payload)
    assert replay.status_code == 201 and replay.json()['id'] == first.json()['id']


@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('accepted', [0, 4])
def test_rejected_delivery_remains_open_until_accepted_replacement(client, legacy, accepted):
    headers = auth_headers(client)
    location, item, _, po = seed_receiving(client, headers)
    path = f"/api/v1/purchase-orders/{po['id']}/receipts" if legacy else f"/api/v1/receiving/purchase-orders/{po['id']}"
    payload = {'delivery_reference': 'rejected-delivery', 'idempotency_key': 'rejected-delivery', 'lines': [{
        'purchase_order_line_id': po['lines'][0]['id'], 'received_quantity': 5,
        'accepted_quantity': accepted, 'rejected_quantity': 5 - accepted, 'discrepancy_reason': 'damaged'}]}
    assert client.post(path, headers=headers, json=payload).status_code == 201
    workspace = client.get('/api/v1/receiving/workspace', headers=headers).json()
    order = next(x for x in workspace['purchase_orders'] if x['id'] == po['id'])
    assert order['status'] == 'partially_received'
    assert order['replacement_required'] is True
    assert Decimal(order['outstanding_quantity']) == 5 - accepted
    assert Decimal(order['received_quantity']) == 5
    assert workspace['summary']['receivable_orders'] == 1
    detail = client.get(f"/api/v1/purchase-orders/{po['id']}/detail", headers=headers)
    assert detail.status_code == 200, detail.text
    assert Decimal(detail.json()['summary']['outstanding_value']) == (5 - accepted) * 20
    # Replay does not double rejected quantity or reduce the replacement need.
    assert client.post(path, headers=headers, json=payload).status_code == 201
    replacement = {'delivery_reference': 'replacement', 'idempotency_key': 'replacement', 'lines': [{
        'purchase_order_line_id': po['lines'][0]['id'], 'received_quantity': 5 - accepted,
        'accepted_quantity': 5 - accepted, 'rejected_quantity': 0}]}
    assert client.post(path, headers=headers, json=replacement).status_code == 201
    assert client.post(path, headers=headers, json=replacement).status_code == 201
    workspace = client.get('/api/v1/receiving/workspace', headers=headers).json()
    order = next(x for x in workspace['purchase_orders'] if x['id'] == po['id'])
    assert order['status'] == 'received' and not order['replacement_required']
    assert Decimal(order['outstanding_quantity']) == 0
    assert Decimal(order['lines'][0]['accepted_quantity']) == 5
    assert Decimal(order['received_quantity']) == 10 - accepted
    balance = client.get(f"/api/v1/stock/balances?item_id={item['id']}&location_id={location['id']}", headers=headers).json()[0]
    assert Decimal(balance['quantity']) == 5


def test_concurrent_staff_meals_cannot_take_reserved_stock(client):
    if engine.dialect.name != 'postgresql':
        pytest.skip('Real row-lock concurrency requires PostgreSQL')
    headers = auth_headers(client)
    location, chicken, rice = setup_master(client, headers)
    reserved = client.post('/api/v1/reservations', headers=headers, json={
        'item_id': chicken['id'], 'location_id': location['id'], 'quantity': 7,
        'reference_type': 'event', 'reference_id': 'party'})
    assert reserved.status_code == 201
    with SessionLocal() as db:
        actor = db.scalar(select(User.id).where(User.email == 'owner@example.com'))
    barrier = Barrier(2)
    def post(key):
        payload = meal_payload(location, chicken, rice, key=key)
        payload['lines'] = [{'item_id': chicken['id'], 'quantity': 2}]
        barrier.wait(timeout=10)
        with SessionLocal() as db:
            try:
                post_staff_meal(db, payload=StaffMealCreate.model_validate(payload), actor_id=actor)
                return True
            except ValueError:
                return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(post, 'one'); b = pool.submit(post, 'two')
        assert sorted([a.result(timeout=20), b.result(timeout=20)]) == [False, True]
    with SessionLocal() as db:
        assert db.scalar(select(StockBalance.quantity).where(StockBalance.item_id == chicken['id'], StockBalance.location_id == location['id'])) == Decimal('8')


def test_generic_retry_cannot_bypass_accounting_role(client):
    from app.core.security import hash_password
    headers = auth_headers(client)
    with SessionLocal() as db:
        db.add(User(email='buyer@example.com', full_name='Buyer', role='procurement_officer', password_hash=hash_password('password123')))
        event = IntegrationEvent(direction='outbound', source_system='inventory', destination_system='accounting',
            event_type='inventory.stock_document.posted', aggregate_type='stock_document', aggregate_id='doc',
            idempotency_key='buyer-retry', status='failed', payload={})
        db.add(event); db.commit(); event_id = event.id
    login = client.post('/api/v1/auth/login', json={'email': 'buyer@example.com', 'password': 'password123'})
    buyer = {'Authorization': f"Bearer {login.json()['access_token']}"}
    assert client.post(f'/api/v1/integration-events/{event_id}/retry', headers=buyer).status_code == 403
    assert client.post(f'/api/v1/integration-events/{event_id}/retry', headers=headers).status_code == 200


def test_existing_rejected_order_migration_preserves_history_and_only_reopens_unfulfilled(client, monkeypatch):
    import importlib.util
    from pathlib import Path
    headers = auth_headers(client)
    _, _, _, po = seed_receiving(client, headers)
    path = f"/api/v1/receiving/purchase-orders/{po['id']}"
    response = client.post(path, headers=headers, json={
        'delivery_reference': 'historical-rejected', 'lines': [{
            'purchase_order_line_id': po['lines'][0]['id'], 'received_quantity': 5,
            'accepted_quantity': 0, 'rejected_quantity': 5, 'discrepancy_reason': 'damaged'}]})
    assert response.status_code == 201
    spec = importlib.util.spec_from_file_location('rejected_followup', Path(__file__).parents[1] / 'alembic/versions/0025_rejected_delivery_followup.py')
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    with SessionLocal() as db:
        order = db.get(PurchaseOrder, po['id']); order.status = 'received'; db.commit()
        doc_count = db.query(StockDocument).count()
        monkeypatch.setattr(migration.op, 'create_index', lambda *args, **kwargs: None)
        monkeypatch.setattr(migration.op, 'execute', db.execute)
        migration.upgrade(); db.commit(); db.expire_all()
        order = db.get(PurchaseOrder, po['id'])
        assert order.status == 'partially_received'
        assert order.lines[0].received_quantity == 5
        assert order.lines[0].outstanding_quantity == 5
        assert db.query(StockDocument).count() == doc_count
        # Cancellation must remain an explicit business decision.
        order.status = 'cancelled'; db.commit()
        migration.upgrade(); db.commit(); db.expire_all()
        assert db.get(PurchaseOrder, po['id']).status == 'cancelled'
