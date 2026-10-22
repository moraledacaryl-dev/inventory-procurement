"""Recovery safety and bounded-memory tests; synthetic data only."""
import gzip
import hashlib
import io
import os
import pathlib
import sqlite3
from types import SimpleNamespace

import pytest

from scripts import backup_database, run_resilience_checks
from scripts.verify_backup import verify_backup


def _dump_data():
    return b"-- PostgreSQL database dump\nSET statement_timeout = 0;\n" + os.urandom(150_000)


def test_complete_gzip_backup_verification_rejects_trailing_corruption_and_truncation(tmp_path):
    payload = _dump_data()
    raw = gzip.compress(payload, compresslevel=0)
    valid = tmp_path / "inventory-valid.sql.gz"
    valid.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    assert verify_backup(valid, digest) == digest

    truncated = tmp_path / "inventory-truncated.sql.gz"
    truncated.write_bytes(raw[:-11])
    with pytest.raises(ValueError, match="incomplete or corrupt"):
        verify_backup(truncated)

    corrupted = tmp_path / "inventory-corrupt.sql.gz"
    broken = bytearray(raw)
    broken[-15] ^= 0x34  # Previously invisible to first-4KB-only checking
    corrupted.write_bytes(broken)
    with pytest.raises(ValueError, match="incomplete or corrupt"):
        verify_backup(corrupted)

    with pytest.raises(ValueError, match="Checksum mismatch"):
        verify_backup(valid, "0" * 64)


def test_backup_verifier_refuses_empty_and_unrelated_gzip(tmp_path):
    unrelated = tmp_path / "inventory-garbage.sql.gz"
    unrelated.write_bytes(gzip.compress(b"not a postgres SQL backup"))
    with pytest.raises(ValueError, match="does not resemble"):
        verify_backup(unrelated)
    with pytest.raises(ValueError, match="does not exist"):
        verify_backup(tmp_path / "nonexistent.sql.gz")


def test_sqlite_backup_integrity_check(tmp_path):
    path = tmp_path / "inventory-db.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE example (value TEXT)")
        db.execute("INSERT INTO example (value) VALUES ('safe')")
    assert len(verify_backup(path)) == 64


class _LimitedReader(io.BytesIO):
    def read(self, size=-1):
        assert 0 < size <= 1024 * 1024, "Unexpected unbounded pg_dump read"
        return super().read(size)


def test_postgres_backup_streams_in_bounded_chunks_and_only_publishes_success(tmp_path, monkeypatch):
    payload = b"-- PostgreSQL database dump\n" + os.urandom(3 * 1024 * 1024)

    class FakeProcess:
        def __init__(self, _cmd, *, env, stdout, stderr):
            self.stdout = _LimitedReader(payload)
            self.finished = False
            self.return_code = 0

        def wait(self):
            self.finished = True
            return self.return_code

        def poll(self):
            return self.return_code if self.finished else None

        def kill(self):
            self.finished = True
            self.return_code = -9

    monkeypatch.setattr(backup_database.subprocess, "Popen", FakeProcess)
    target = tmp_path / "inventory-success.sql.gz"
    backup_database._stream_postgres_backup(target, ["pg_dump"], {})
    with gzip.open(target, "rb") as handle:
        assert handle.read() == payload
    assert not list(tmp_path.glob("*.tmp"))


def test_failed_and_empty_pg_dump_never_replace_a_prior_backup(tmp_path, monkeypatch):
    target = tmp_path / "inventory-existing.sql.gz"
    target.write_bytes(b"previous verified backup")

    class FakeProcess:
        def __init__(self, _cmd, *, env, stdout, stderr):
            self.stdout = _LimitedReader(b"-- PostgreSQL database dump\n" if should_fail[0] else b"")
            self.stderr = stderr
            self.stderr.write(b"pg_dump: connection failed")
            self.finished = False

        def wait(self):
            self.finished = True
            return 1 if should_fail[0] else 0

        def poll(self):
            return (1 if should_fail[0] else 0) if self.finished else None

        def kill(self):
            self.finished = True

    monkeypatch.setattr(backup_database.subprocess, "Popen", FakeProcess)
    for should_fail in ([True], [False]):
        with pytest.raises(RuntimeError, match="pg_dump failed|empty backup"):
            backup_database._stream_postgres_backup(target, ["pg_dump"], {})
        assert target.read_bytes() == b"previous verified backup"
        assert not any(tmp_path.glob("*.tmp"))


def test_destructive_resilience_harness_requires_nonproduction_isolated_database(monkeypatch):
    monkeypatch.setattr(
        run_resilience_checks, "engine",
        SimpleNamespace(
            dialect=SimpleNamespace(name="postgresql"),
            url=SimpleNamespace(database="hiddenoasis_inventory_live"),
        ),
    )
    monkeypatch.setenv("INVENTORY_ALLOW_DESTRUCTIVE_RESILIENCE_TESTS", "1")
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(SystemExit, match="isolated test database"):
        run_resilience_checks.assert_postgres()

    monkeypatch.setattr(
        run_resilience_checks.engine, "url",
        SimpleNamespace(database="inventory_resilience"),
    )
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(SystemExit, match="forbidden in production"):
        run_resilience_checks.assert_postgres()

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("INVENTORY_ALLOW_DESTRUCTIVE_RESILIENCE_TESTS")
    with pytest.raises(SystemExit, match="explicit opt-in"):
        run_resilience_checks.assert_postgres()

    monkeypatch.setenv("INVENTORY_ALLOW_DESTRUCTIVE_RESILIENCE_TESTS", "1")
    run_resilience_checks.assert_postgres()


def test_backup_retention_cannot_run_if_new_backup_catalogue_commit_fails(tmp_path, monkeypatch):
    original = tmp_path / "live.db"
    with sqlite3.connect(original) as db:
        db.execute("CREATE TABLE evidence (id INTEGER)")
    prior = tmp_path / "inventory-prior.db"
    prior.write_bytes(b"retain previous restore point")

    class FailureDatabase:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def add(self, *_args): pass
        def commit(self): raise RuntimeError("backup catalog unavailable")

    monkeypatch.setattr(
        backup_database, "settings",
        SimpleNamespace(database_url=f"sqlite:///{original}"),
    )
    monkeypatch.setattr(backup_database, "SessionLocal", lambda: FailureDatabase())
    monkeypatch.setattr(
        backup_database, "_prune_backups",
        lambda *_args, **_kwargs: pytest.fail("Retention before durable catalogue"),
    )
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path))
    monkeypatch.setenv("BACKUP_RETENTION_DAYS", "14")
    with pytest.raises(RuntimeError, match="backup catalog unavailable"):
        backup_database.main()
    assert prior.read_bytes() == b"retain previous restore point"
