from datetime import datetime, timezone

from fastapi import HTTPException


def reset_failed_event(event):
    """Caller must hold the event row lock through commit."""
    if event.status not in {"failed", "dead_letter"}:
        raise HTTPException(409, "Only failed or dead-letter events can be retried")
    if event.direction != "outbound":
        raise HTTPException(409, "Only outbound events can be retried")
    payload = event.payload if isinstance(event.payload, dict) else {}
    for field in ("accounting_receipt", "accounting_intake", "accounting_reconciliation"):
        evidence = payload.get(field)
        if isinstance(evidence, dict) and (
            evidence.get("accepted") is True
            or evidence.get("status") in {"accepted", "ready_for_review"}
            or evidence.get("review_status") in {"accepted", "ready_for_review"}
            or evidence.get("ledger_posting_confirmed") is True
            or evidence.get("journal_status") == "posted"
        ):
            raise HTTPException(409, "Accounting already received or accepted this event; reconcile its existing receipt")
    event.status = "pending"
    event.last_error = None
    event.locked_at = None
    event.locked_by = None
    event.attempts = 0
    event.available_at = datetime.now(timezone.utc)
