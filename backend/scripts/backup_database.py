import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gzip
import hashlib
import os
import pathlib
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import delete

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.operations import BackupRecord


def _sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _stream_postgres_backup(target: pathlib.Path, cmd: list[str], env: dict[str, str]) -> None:
    """Bounded-memory pg_dump -> gzip, atomic only after successful exit.

    Keep stderr off the pipe so a verbose failing pg_dump cannot block while
    stdout is drained. Never replace a valid backup with a failed dump.
    """
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent,
    )
    temp_path = pathlib.Path(temp_name)
    try:
        with tempfile.TemporaryFile(mode="w+b") as errors, os.fdopen(fd, "wb") as output:
            process = subprocess.Popen(
                cmd, env=env, stdout=subprocess.PIPE, stderr=errors,
            )
            try:
                if process.stdout is None:
                    raise RuntimeError("pg_dump did not provide a data stream")
                total_bytes = 0
                with process.stdout, gzip.GzipFile(fileobj=output, mode="wb") as compressed:
                    while block := process.stdout.read(1024 * 1024):
                        compressed.write(block)
                        total_bytes += len(block)
                return_code = process.wait()
                if return_code != 0:
                    errors.seek(0)
                    diagnostic = errors.read(2000).decode("utf-8", errors="replace").strip()
                    raise RuntimeError(f"pg_dump failed with exit code {return_code}: {diagnostic}")
                if not total_bytes:
                    raise RuntimeError("pg_dump produced an empty backup")
                output.flush()
                os.fsync(output.fileno())
            except BaseException:
                if process.poll() is None:
                    process.kill()
                process.wait()
                raise
        os.replace(temp_path, target)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def _prune_backups(
    backup_dir: pathlib.Path,
    *,
    retention_days: int,
    keep: pathlib.Path,
    now: datetime | None = None,
) -> list[str]:
    if retention_days <= 0:
        return []

    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=retention_days)
    removed: list[str] = []
    for candidate in backup_dir.glob("inventory-*"):
        if not candidate.is_file() or candidate == keep:
            continue
        modified_at = datetime.fromtimestamp(candidate.stat().st_mtime, tz=timezone.utc)
        if modified_at >= cutoff:
            continue
        candidate.unlink()
        removed.append(candidate.name)
    return removed


def main():
    backup_dir = pathlib.Path(os.getenv("BACKUP_DIR", "./backups"))
    retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "14"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")

    if settings.database_url.startswith("sqlite"):
        source = pathlib.Path(settings.database_url.replace("sqlite:///", "", 1))
        target = backup_dir / f"inventory-{stamp}.db"
        fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        os.close(fd)
        tmp_path = pathlib.Path(tmp_name)
        try:
            shutil.copy2(source, tmp_path)
            os.replace(tmp_path, target)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
    else:
        target = backup_dir / f"inventory-{stamp}.sql.gz"
        parsed = urlparse(settings.database_url.replace("postgresql+psycopg", "postgresql"))
        env = {**os.environ, "PGPASSWORD": parsed.password or ""}
        cmd = [
            "pg_dump",
            "-h",
            parsed.hostname or "localhost",
            "-p",
            str(parsed.port or 5432),
            "-U",
            parsed.username or "inventory",
            "-d",
            (parsed.path or "/inventory").lstrip("/"),
            "--no-owner",
            "--no-privileges",
        ]
        _stream_postgres_backup(target, cmd, env)

    if not target.exists() or target.stat().st_size <= 0:
        raise RuntimeError("backup artifact is empty")

    digest = _sha256_file(target)
    # The new backup must be durably catalogued before retention is touched.
    # If database cataloguing fails, preserve all prior recovery points.
    with SessionLocal() as db:
        db.add(
            BackupRecord(
                filename=target.name,
                size_bytes=target.stat().st_size,
                checksum_sha256=digest,
            )
        )
        db.commit()

    removed = _prune_backups(backup_dir, retention_days=retention_days, keep=target)
    if removed:
        with SessionLocal() as db:
            db.execute(delete(BackupRecord).where(BackupRecord.filename.in_(removed)))
            db.commit()
    print(target)
    if removed:
        print(f"Pruned {len(removed)} expired backup(s).")


if __name__ == "__main__":
    main()
