from app.db.session import SessionLocal
from app.models.staff_identity import StaffIdentity


def envelope(*, source_staff_id=3, employee_code="EMP-003", version="2026-09-08T10:00:00", display_name="Test Employee", extra_employee=None):
    employee = {
        "employee_code": employee_code,
        "display_name": display_name,
        "department": "Operations",
        "position": "Staff",
        "role": "Regular",
        "active": True,
        "primary_department": "Operations",
        "source_staff_id": source_staff_id,
    }
    if extra_employee:
        employee.update(extra_employee)
    return {
        "external_source": "hidden_oasis_staff_payroll",
        "external_id": f"employee-sync:{source_staff_id}:{version}",
        "event_type": "employee.sync",
        "source_record_type": "Employee",
        "source_record_id": source_staff_id,
        "generated_at": "2026-09-10 12:00:00",
        "schema_version": "2026-06-v1",
        "payload": {"employees": [employee]},
    }


def headers(token="test-staff-integration-token"):
    return {"X-Integration-Api-Key": token}


def test_staff_employee_sync_requires_staff_api_key(client):
    response = client.post("/api/v1/integrations/staff/employees", json=envelope())
    assert response.status_code == 401


def test_staff_employee_sync_creates_and_updates_safe_projection(client):
    first = client.post("/api/v1/integrations/staff/employees", json=envelope(), headers=headers())
    assert first.status_code == 200
    assert first.json()["applied"] == 1

    second = client.post(
        "/api/v1/integrations/staff/employees",
        json=envelope(version="2026-09-09T10:00:00", display_name="Updated Employee"),
        headers=headers(),
    )
    assert second.status_code == 200
    assert second.json()["applied"] == 1

    with SessionLocal() as db:
        rows = db.query(StaffIdentity).all()
        assert len(rows) == 1
        assert rows[0].source_staff_id == 3
        assert rows[0].employee_code == "EMP-003"
        assert rows[0].display_name == "Updated Employee"
        assert rows[0].is_active is True


def test_staff_employee_sync_is_idempotent_and_ignores_stale_revision(client):
    payload = envelope(version="2026-09-09T10:00:00", display_name="Current")
    assert client.post("/api/v1/integrations/staff/employees", json=payload, headers=headers()).status_code == 200

    duplicate = client.post("/api/v1/integrations/staff/employees", json=payload, headers=headers())
    assert duplicate.status_code == 200
    assert duplicate.json()["ignored_stale"] == 1

    stale = client.post(
        "/api/v1/integrations/staff/employees",
        json=envelope(version="2026-09-08T10:00:00", display_name="Stale"),
        headers=headers(),
    )
    assert stale.status_code == 200
    assert stale.json()["ignored_stale"] == 1

    with SessionLocal() as db:
        row = db.query(StaffIdentity).one()
        assert row.display_name == "Current"


def test_staff_employee_code_collision_is_rejected(client):
    assert client.post("/api/v1/integrations/staff/employees", json=envelope(source_staff_id=3, employee_code="EMP-003"), headers=headers()).status_code == 200

    collision = client.post(
        "/api/v1/integrations/staff/employees",
        json=envelope(source_staff_id=4, employee_code="EMP-003"),
        headers=headers(),
    )
    assert collision.status_code == 409


def test_staff_sync_rejects_private_or_unknown_employee_fields(client):
    response = client.post(
        "/api/v1/integrations/staff/employees",
        json=envelope(extra_employee={"salary": 50000}),
        headers=headers(),
    )
    assert response.status_code == 422


def test_staff_sync_rejects_wrong_source_contract(client):
    payload = envelope()
    payload["event_type"] = "payroll.run.paid"
    response = client.post("/api/v1/integrations/staff/employees", json=payload, headers=headers())
    assert response.status_code == 422
