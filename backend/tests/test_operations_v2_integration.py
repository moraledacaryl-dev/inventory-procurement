from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services.integration_worker import OPERATIONS_ENDPOINT, operations_envelope, _operations_url


def event(event_type='stock.low.alert'):
    return SimpleNamespace(
        id='evt-row-1',
        idempotency_key='stock-low:item-1:loc-1:v3',
        event_type=event_type,
        aggregate_type='stock_balance',
        aggregate_id='balance-1',
        payload={
            'title': 'Low stock: Bath towel',
            'summary': '14 remaining; minimum stock is 30.',
            'priority': 'High',
            'item_id': 'item-1',
            'location_id': 'loc-1',
        },
        source_system='inventory',
        created_at=datetime(2026, 9, 1, 8, 30, tzinfo=timezone.utc),
    )


def test_operations_envelope_is_stable_and_contract_compatible():
    body = operations_envelope(event())
    assert body['event_id'] == 'stock-low:item-1:loc-1:v3'
    assert body['event_type'] == 'stock.low.alert'
    assert body['occurred_at'] == '2026-09-01T08:30:00+00:00'
    assert body['priority'] == 'High'
    assert body['subject'] == {'type': 'stock_balance', 'id': 'balance-1'}
    assert body['payload']['item_id'] == 'item-1'


def test_operations_url_accepts_root_api_or_full_endpoint():
    assert _operations_url('https://operations.hiddenoasis.app') == f'https://operations.hiddenoasis.app{OPERATIONS_ENDPOINT}'
    assert _operations_url('https://operations.hiddenoasis.app/api') == f'https://operations.hiddenoasis.app{OPERATIONS_ENDPOINT}'
    full = f'https://operations.hiddenoasis.app{OPERATIONS_ENDPOINT}'
    assert _operations_url(full) == full


def test_unknown_operations_event_is_rejected_before_delivery():
    with pytest.raises(ValueError, match='does not accept'):
        operations_envelope(event('inventory.private.internal_event'))
