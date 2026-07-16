from types import SimpleNamespace

from app.services.integration_worker import ACCOUNTING_ENDPOINT, accounting_envelope


def event(event_type: str, payload: dict):
    return SimpleNamespace(
        id=f"event-{event_type}",
        event_type=event_type,
        aggregate_type="test_record",
        aggregate_id="record-42",
        attempts=0,
        payload=payload,
        idempotency_key=f"inventory:{event_type}:42",
    )


def test_accounting_endpoint_is_canonical_service_intake():
    assert ACCOUNTING_ENDPOINT == "/api/integration-review/service-intake"


def test_goods_receipt_becomes_payable_with_accepted_value_only():
    result = accounting_envelope(
        event(
            "procurement.goods_received",
            {
                "goods_receipt_number": "GRN-000042",
                "purchase_order_id": "po-42",
                "supplier_id": "supplier-7",
                "lines": [
                    {"accepted_quantity": "3", "rejected_quantity": "1", "unit_cost": "125.50"},
                    {"accepted_quantity": "2", "rejected_quantity": "0", "unit_cost": "50"},
                ],
            },
        )
    )
    assert result["source_app"] == "inventory"
    assert result["financial_effect"] == "payable"
    assert result["amount"] == 476.5
    assert result["proposed_links"]["invoice_number"] == "GRN-000042"


def test_purchase_order_is_reference_only_commitment():
    result = accounting_envelope(
        event(
            "procurement.purchase_order.approved",
            {"purchase_order_id": "po-42", "supplier_id": "supplier-7", "total": "2500"},
        )
    )
    assert result["financial_effect"] == "reference_only"
    assert result["proposed_links"]["commitment_total"] == "2500"


def test_production_and_pos_consumption_are_linked_without_duplicate_cash():
    production = accounting_envelope(
        event("inventory.production.completed", {"batch_id": "batch-1", "total_cost": "900"})
    )
    consumption = accounting_envelope(
        event("inventory.pos_sale_consumed", {"sale_id": "sale-1", "stock_document_id": "doc-1"})
    )
    assert production["financial_effect"] == "reference_only"
    assert consumption["financial_effect"] == "reference_only"
    assert consumption["proposed_links"]["category"] == "Cost of goods sold"


def test_idempotency_key_is_preserved():
    result = accounting_envelope(event("procurement.purchase_return.posted", {"purchase_return_id": "ret-1"}))
    assert result["idempotency_key"] == "inventory:procurement.purchase_return.posted:42"
