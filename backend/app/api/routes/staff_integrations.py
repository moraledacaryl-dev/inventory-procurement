from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.integration_auth import integration_token_header, require_integration_token
from app.db.session import get_db
from app.models.operations import IntegrationEvent

router = APIRouter(tags=["staff-integrations"])

SAFE_FIELDS = {
    "employee_code",
    "display_name",
    "department",
    "position",
    "role",
    "active",
    "primary_department",
    "source_staff_id",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/integrations/staff/employees")
def receive_staff_employees(
    payload: dict[str, Any],
    token: str | None = Depends(integration_token_header),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_integration_token("staff", token)
    if payload.get("external_source") != "hidden_oasis_staff_payroll":
        raise HTTPException(status_code=422, detail="Unsupported integration source")
    if payload.get("event_type") != "employee.sync":
        raise HTTPException(status_code=422, detail="Only employee.sync is supported")
    external_id = str(payload.get("external_id") or "").strip()
    if not external_id:
        raise HTTPException(status_code=400, detail="external_id is required")

    key = f"staff-employee-sync:{external_id}"
    existing = db.scalar(select(IntegrationEvent).where(IntegrationEvent.idempotency_key == key))
    if existing:
        return {"status": "already_applied", "id": existing.id, "external_id": external_id}

    body = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    employees = body.get("employees") if isinstance(body.get("employees"), list) else []
    safe_employees: list[dict[str, Any]] = []
    for raw in employees:
        if not isinstance(raw, dict):
            continue
        employee_code = str(raw.get("employee_code") or "").strip()
        display_name = str(raw.get("display_name") or "").strip()
        if not employee_code or not display_name:
            raise HTTPException(status_code=422, detail="Each employee requires employee_code and display_name")
        safe_employees.append({field: raw.get(field) for field in SAFE_FIELDS if field in raw})

    event = IntegrationEvent(
        direction="inbound",
        source_system="staff",
        destination_system="inventory",
        event_type="employee.sync",
        aggregate_type="staff_employee_reference",
        aggregate_id=str(payload.get("source_record_id") or external_id),
        idempotency_key=key,
        payload={
            "external_source": payload.get("external_source"),
            "external_id": external_id,
            "schema_version": payload.get("schema_version"),
            "generated_at": payload.get("generated_at"),
            "employees": safe_employees,
        },
        status="completed",
        processed_at=utcnow(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return {"status": "accepted", "id": event.id, "external_id": external_id, "applied": len(safe_employees)}
