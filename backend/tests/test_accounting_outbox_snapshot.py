import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.operations import IntegrationEvent

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_accounting_outbox_snapshot.py"
spec = importlib.util.spec_from_file_location("inventory_outbox_export", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    IntegrationEvent.__table__.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def event(i, *, dest="accounting", direction="outbound", status="pending"):
    return IntegrationEvent(
        id=f"source-event-{i}",
        direction=direction,
        source_system="inventory",
        destination_system=dest,
        event_type="procurement.goods_received",
        aggregate_type="goods_receipt",
        aggregate_id=f"private-aggregate-{i}",
        idempotency_key=f"private-unique-{i}",
        payload={
            "supplier_name": "SECRET SUPPLIER",
            "account_number": "SECRET ACCOUNT NUMBER",
            "total": 999999,
        },
        status=status,
    )


def test_inventory_accounting_uuid_is_exact_identity_without_payload_or_financial_fields(db):
    db.add_all([
        event(1, status="completed"),
        event(2, status="failed"),
        event(3, dest="operations", status="completed"),
        event(4, direction="inbound", status="completed"),
    ])
    db.commit()
    result = module.export_inventory_outbox(db)
    assert result["source"] == "inventory"
    assert result["complete_for_window"] is False
    assert result["full_source_scan"] is True
    assert result["events"] == [
        {"id": "source-event-1", "destination_system": "accounting", "status": "completed"},
        {"id": "source-event-2", "destination_system": "accounting", "status": "failed"},
    ]
    data = json.dumps(result)
    for hidden in ("SECRET SUPPLIER", "SECRET ACCOUNT", "999999", "private-aggregate",
                   "private-unique"):
        assert hidden not in data


def test_scan_has_no_workspace_limit_and_preserves_failures(db):
    db.add_all([event(i, status="dead_letter" if i % 2 else "processing")
                for i in range(1, 520)])
    db.commit()
    result = module.export_inventory_outbox(db)
    assert len(result["events"]) == 519
    assert any(e["status"] == "dead_letter" for e in result["events"])
    assert all("source-event-" in e["id"] for e in result["events"])


def test_missing_uuid_fails_closed(db):
    row = event(1)
    row.id = " "
    db.add(row)
    db.commit()
    with pytest.raises(ValueError, match="stable Accounting source"):
        module.export_inventory_outbox(db)


def test_export_does_not_mutate_integration_events(db):
    db.add(event(1))
    db.commit()
    result = module.export_inventory_outbox(db)
    assert len(result["events"]) == 1
    assert not db.new and not db.dirty and not db.deleted
    assert db.get(IntegrationEvent, "source-event-1").status == "pending"


def test_confidential_output_created_0600_without_clobber_or_symlink(tmp_path):
    path = tmp_path / "protected.json"
    result = {"events": []}
    module.write_private(path, result)
    assert json.loads(path.read_text()) == result
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        module.write_private(path, {"events": [1]})
    alias = tmp_path / "alias.json"
    alias.symlink_to(path)
    with pytest.raises(OSError):
        module.write_private(alias, {"events": []})
    assert json.loads(path.read_text()) == result
