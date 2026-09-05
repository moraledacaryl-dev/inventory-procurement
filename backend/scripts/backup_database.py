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
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.operations import BackupRecord


def _atomic_write(target: pathlib.Path, payload: bytes) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    tmp_path = pathlib.Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def main():
    backup_dir = pathlib.Path(os.getenv("BACKUP_DIR", "./backups"))
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
        raw = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
        if not raw:
            raise RuntimeError("pg_dump produced an empty backup")
        _atomic_write(target, gzip.compress(raw))

    if not target.exists() or target.stat().st_size <= 0:
        raise RuntimeError("backup artifact is empty")

    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    with SessionLocal() as db:
        db.add(
            BackupRecord(
                filename=target.name,
                size_bytes=target.stat().st_size,
                checksum_sha256=digest,
            )
        )
        db.commit()
    print(target)


if __name__ == "__main__":
    main()
