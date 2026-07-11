from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.api.routes.controlled_inventory import (
    TransferReceiptCreate,
    TransferReceiptLine,
    fail,
    receive_transfer_controlled,
    transfer_row,
)
from app.db.session import get_db
from app.models.user import User

router = APIRouter(tags=["controlled-inventory-compatibility"])


@router.post("/transfer-orders/{transfer_id}/receive")
def receive_transfer_compatible(
    transfer_id: str,
    payload: TransferReceiptCreate | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.*")),
):
    row = transfer_row(db, transfer_id)
    if not row:
        fail(404, "Transfer order not found")
    if payload is None:
        payload = TransferReceiptCreate(
            lines=[
                TransferReceiptLine(
                    item_id=line.item_id,
                    received_quantity=line.quantity,
                    variance_reason=None,
                )
                for line in row.lines
            ]
        )
    result = receive_transfer_controlled(transfer_id, payload, db, user)
    result["stock_document_id"] = result.get("receipt_document_id")
    return result
