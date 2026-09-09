from types import SimpleNamespace

from app.models.inventory import StockDocument
from app.models.procurement import PurchaseOrder, PurchaseReturn, Supplier
from app.services.integration_worker import _accounting_payload, accounting_envelope


def event(event_type: str, payload: dict, aggregate_id: str = "ret-1"):
    return SimpleNamespace(
        id=f"event-{event_type}",
        event_type=event_type,
        aggregate_type="purchase_return" if "return" in event_type else "goods_receipt",
        aggregate_id=aggregate_id,
        attempts=0,
        payload=payload,
        idempotency_key=f"inventory:{event_type}:{aggregate_id}",
    )


class FakeDb:
    def __init__(self):
        self.purchase_return = SimpleNamespace(
            id="ret-1",
            return_number="PRTN-0001",
            purchase_order_id="po-1",
            stock_document_id="doc-1",
            reason="Damaged",
        )
        self.purchase_order = SimpleNamespace(
            id="po-1",
            supplier_id="sup-1",
            lines=[
                SimpleNamespace(id="pol-1", item_id="item-1"),
                SimpleNamespace(id="pol-2", item_id="item-2"),
            ],
        )
        self.supplier = SimpleNamespace(id="sup-1", name="Supplier One")
        self.stock_document = SimpleNamespace(
            id="doc-1",
            movements=[
                SimpleNamespace(line_number=1, item_id="item-1", quantity="-2", unit_cost="48"),
                SimpleNamespace(line_number=2, item_id="item-2", quantity="-1.5", unit_cost="20"),
            ],
        )

    def get(self, model, key):
        if model is PurchaseReturn and key == "ret-1":
            return self.purchase_return
        if model is PurchaseOrder and key == "po-1":
            return self.purchase_order
        if model is Supplier and key == "sup-1":
            return self.supplier
        if model is StockDocument and key == "doc-1":
            return self.stock_document
        return None


def test_purchase_return_is_enriched_with_supplier_and_exact_costed_lines():
    row = event(
        "procurement.purchase_return.posted",
        {"purchase_return_id": "ret-1", "purchase_order_id": "po-1", "reason": "Damaged"},
    )
    payload = _accounting_payload(FakeDb(), row)

    assert payload["supplier_id"] == "sup-1"
    assert payload["supplier_name"] == "Supplier One"
    assert payload["stock_document_id"] == "doc-1"
    assert payload["total"] == "126.0"
    assert payload["lines"] == [
        {
            "purchase_order_line_id": "pol-1",
            "item_id": "item-1",
            "quantity": "2",
            "unit_cost": "48",
            "line_total": "96",
        },
        {
            "purchase_order_line_id": "pol-2",
            "item_id": "item-2",
            "quantity": "1.5",
            "unit_cost": "20",
            "line_total": "30.0",
        },
    ]

    envelope = accounting_envelope(row, payload)
    assert envelope["financial_effect"] == "payable_adjustment"
    assert envelope["amount"] == 126.0
    assert envelope["proposed_links"]["purchase_order_id"] == "po-1"
    assert envelope["proposed_links"]["supplier_name"] == "Supplier One"
    assert envelope["payload"]["data"]["lines"] == payload["lines"]


def test_goods_receipt_prefers_human_supplier_name_when_available():
    row = event(
        "procurement.goods_received",
        {
            "goods_receipt_number": "GRN-1",
            "purchase_order_id": "po-1",
            "supplier_id": "sup-1",
            "supplier_name": "Supplier One",
            "lines": [{"accepted_quantity": "2", "unit_cost": "50"}],
        },
        aggregate_id="grn-1",
    )
    envelope = accounting_envelope(row)
    assert envelope["financial_effect"] == "payable"
    assert envelope["amount"] == 100.0
    assert envelope["proposed_links"]["supplier_name"] == "Supplier One"
