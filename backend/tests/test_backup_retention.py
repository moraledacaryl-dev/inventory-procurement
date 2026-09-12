from datetime import datetime, timedelta, timezone
import os

from scripts.backup_database import _prune_backups


def _set_mtime(path, when: datetime) -> None:
    timestamp = when.timestamp()
    os.utime(path, (timestamp, timestamp))


def test_prune_backups_removes_only_expired_inventory_backups(tmp_path):
    now = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
    keep = tmp_path / "inventory-current.sql.gz"
    expired = tmp_path / "inventory-expired.sql.gz"
    recent = tmp_path / "inventory-recent.sql.gz"
    unrelated = tmp_path / "other-expired.sql.gz"

    for path in (keep, expired, recent, unrelated):
        path.write_bytes(b"backup")

    _set_mtime(keep, now - timedelta(days=30))
    _set_mtime(expired, now - timedelta(days=15))
    _set_mtime(recent, now - timedelta(days=13))
    _set_mtime(unrelated, now - timedelta(days=30))

    removed = _prune_backups(tmp_path, retention_days=14, keep=keep, now=now)

    assert removed == [expired.name]
    assert keep.exists()
    assert not expired.exists()
    assert recent.exists()
    assert unrelated.exists()


def test_prune_backups_can_be_disabled(tmp_path):
    now = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
    keep = tmp_path / "inventory-current.sql.gz"
    old = tmp_path / "inventory-old.sql.gz"
    keep.write_bytes(b"backup")
    old.write_bytes(b"backup")
    _set_mtime(old, now - timedelta(days=365))

    removed = _prune_backups(tmp_path, retention_days=0, keep=keep, now=now)

    assert removed == []
    assert old.exists()
