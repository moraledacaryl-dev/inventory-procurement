from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.integration_auth import require_integration_token
from app.db.session import get_db
from app.models.staff_identity import StaffIdentity

router = APIRouter(tags=["staff-identity-integration"])


class StaffEmployee(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_code: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=200)
    department: str | None = Field(default=None, max_length=120)
    position: str | None = Field(default=None, max_length=120)
    role: str | None = Field(default=None, max_length=80)
    active: bool
    primary_department: str | None = Field(default=None, max_length=120)
    source_staff_id: int = Field(gt=0)


class StaffPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employees: list[StaffEmployee] = Field(min_length=1, max_length=100)


class StaffEmployeeSyncEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_source: str
    external_id: str = Field(min_length=1, max_length=255)
    event_type: str
    source_record_type: str
    source_record_id: int
    generated_at: str
    schema_version: str
    payload: StaffPayload


def _source_version(external_id: str, source_staff_id: int) -> str:
    prefix = f"employee-sync:{source_staff_id}:"
    return external_id[len(prefix):] if external_id.startswith(prefix) else external_id


def _auth_staff(
    x_integration_api_key: str | None = Header(default=None, alias="X-Integration-Api-Key"),
) -> None:
    require_integration_token("staff", x_integration_api_key)


@router.post("/integrations/staff/employees")
def receive_staff_employees(
    envelope: StaffEmployeeSyncEnvelope,
    db: Session = Depends(get_db),
    _: None = Depends(_auth_staff),
):
    if envelope.external_source != "hidden_oasis_staff_payroll":
        raise HTTPException(422, "Unsupported Staff integration source")
    if envelope.event_type != "employee.sync":
        raise HTTPException(422, "Inventory only accepts employee.sync from Staff")
    if envelope.source_record_type != "Employee":
        raise HTTPException(422, "Staff source record type must be Employee")

    applied = 0
    ignored_stale = 0

    for employee in envelope.payload.employees:
        if envelope.source_record_id != employee.source_staff_id:
            raise HTTPException(422, "Envelope source_record_id does not match employee source_staff_id")

        by_source = db.scalar(
            select(StaffIdentity).where(StaffIdentity.source_staff_id == employee.source_staff_id)
        )
        by_code = db.scalar(
            select(StaffIdentity).where(StaffIdentity.employee_code == employee.employee_code)
        )

        if by_source and by_code and by_source.id != by_code.id:
            raise HTTPException(409, "Staff identity collision between source ID and employee code")
        if by_source and by_source.employee_code != employee.employee_code:
            raise HTTPException(409, "Staff source ID is already linked to another employee code")
        if by_code and by_code.source_staff_id != employee.source_staff_id:
            raise HTTPException(409, "Employee code is already linked to another Staff source ID")

        row = by_source or by_code
        version = _source_version(envelope.external_id, employee.source_staff_id)

        if row and row.source_version and version <= row.source_version:
            ignored_stale += 1
            continue

        if row is None:
            row = StaffIdentity(
                source_staff_id=employee.source_staff_id,
                employee_code=employee.employee_code,
            )
            db.add(row)

        row.display_name = employee.display_name
        row.department = employee.department
        row.position = employee.position
        row.role = employee.role
        row.primary_department = employee.primary_department
        row.is_active = employee.active
        row.source_version = version
        row.last_external_id = envelope.external_id
        applied += 1

    db.commit()

    return {
        "ok": True,
        "received": len(envelope.payload.employees),
        "applied": applied,
        "ignored_stale": ignored_stale,
    }
