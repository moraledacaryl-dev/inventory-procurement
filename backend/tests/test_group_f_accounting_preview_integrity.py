"""Group F: read-only Accounting preview must never fabricate a zero amount.

Uses synthetic rows in isolated CI databases, not live Accounting postings.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.api.routes.accounting_integration import event_amount, journal_lines


def login(client):
    response=client.post("/api/v1/auth/login",json={"email":"owner@example.com","password":"password123"})
    assert response.status_code==200, response.text
    return {"Authorization":f"Bearer {response.json()['access_token']}"}


def create_event(client, headers, key, payload, event_type="inventory.stock_document.posted"):
    response=client.post("/api/v1/integration-events",headers=headers,json={
        "direction":"outbound","source_system":"inventory",
        "destination_system":"accounting","event_type":event_type,
        "aggregate_type":"stock_document","aggregate_id":key,
        "idempotency_key":key,"payload":payload,
    })
    assert response.status_code==201, response.text
    return response.json()


@pytest.mark.parametrize("quantity,cost",[
    ("invalid", "15"), ("NaN", "15"), ("Infinity", "15"),
    (None, "15"), (True, "15"), ("2", None), ("2", False),
    ("2", "not-a-number"), ("2", "-Infinity"),
])
def test_invalid_money_not_coerced_to_zero(quantity, cost):
    event=SimpleNamespace(event_type="inventory.stock_document.posted",
                          payload={"lines":[{"quantity":quantity, "unit_cost":cost}]})
    with pytest.raises(ValueError, match="Financial quantity or amount"):
        event_amount(event)
    with pytest.raises(ValueError, match="Financial quantity or amount"):
        journal_lines(event)


@pytest.mark.parametrize("lines", ["broken", [{"quantity":"2","unit_cost":"15"},None]])
def test_malformed_financial_lines_fail_closed(lines):
    event=SimpleNamespace(event_type="inventory.stock_document.posted",payload={"lines":lines})
    with pytest.raises(ValueError, match="Financial lines|Financial line"):
        event_amount(event)


def test_workspace_keeps_invalid_amount_unknown_without_changing_outbox(client):
    from app.db.session import SessionLocal
    from app.models.operations import IntegrationEvent

    headers=login(client)
    good=create_event(client,headers,"group-f-good",{"lines":[{"quantity":"2","unit_cost":"15"}]})
    bad=create_event(client,headers,"group-f-bad",{"lines":[{"quantity":"oops","unit_cost":"15"}]})
    with SessionLocal() as db:
        before={e.id:(e.status,e.payload.copy(),e.attempts) for e in db.query(IntegrationEvent).all()}
    response=client.get("/api/v1/integrations/accounting/workspace",headers=headers)
    assert response.status_code==200, response.text
    data=response.json()
    rows={row["id"]:row for row in data["events"]}
    assert Decimal(str(rows[good["id"]]["amount"]))==Decimal("30")
    assert rows[good["id"]]["financial_evidence_valid"] is True
    assert rows[bad["id"]]["amount"] is None
    assert rows[bad["id"]]["financial_evidence_valid"] is False
    assert rows[bad["id"]]["financial_evidence_error"]
    assert rows[bad["id"]]["journal_lines"]==[]
    assert rows[bad["id"]]["ledger_posting_confirmed"] is False
    assert data["summary"]["financial_evidence_errors"]==1
    assert Decimal(str(data["summary"]["queued_value"]))==Decimal("30")
    assert data["summary"]["event_metrics_scope"]=="displayed_rows"
    assert data["summary"]["total_events"]==2
    assert data["summary"]["displayed_events"]==2
    assert data["summary"]["has_more"] is False
    with SessionLocal() as db:
        after={e.id:(e.status,e.payload.copy(),e.attempts) for e in db.query(IntegrationEvent).all()}
    assert after==before


def test_workspace_distinguishes_all_event_counts_from_limited_preview(client):
    headers=login(client)
    for n in range(3):
        create_event(client,headers,f"group-f-limit-{n}",{"lines":[{"quantity":"1","unit_cost":"9"}]})
    response=client.get("/api/v1/integrations/accounting/workspace?limit=1",headers=headers)
    assert response.status_code==200, response.text
    summary=response.json()["summary"]
    assert summary["total_events"]==3
    assert summary["displayed_events"]==1
    assert summary["has_more"] is True
    assert summary["pending"]==3 # complete backlog, not 1 displayed row
    assert summary["event_metrics_scope"]=="displayed_rows"
    assert Decimal(str(summary["queued_value"]))==Decimal("9")
    assert len(response.json()["events"])==1


def test_valid_transfer_remains_value_neutral():
    event=SimpleNamespace(event_type="inventory.stock_document.posted",payload={"lines":[
        {"quantity":"-4","unit_cost":"50"},
        {"quantity":"4","unit_cost":"50"},
    ]})
    assert event_amount(event)==Decimal("0")
    assert journal_lines(event)==[]
