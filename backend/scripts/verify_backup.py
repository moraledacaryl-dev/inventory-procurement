"""Verify complete PostgreSQL gzip backups and SQLite database backups.

A gzip header or an intact first page is not proof the full dump is restorable.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import pathlib
import sqlite3
import sys
import zlib

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_CHUNK = 1024 * 1024
_POSTGRES_HEADERS = (
    b"postgresql database dump",
    b"create table",
    b"set statement_timeout",
)


def verify_backup(path: pathlib.Path, expected_sha256: str | None = None) -> str:
    if not path.is_file():
        raise ValueError("Backup file does not exist")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(_CHUNK):
            digest.update(block)
    actual = digest.hexdigest()
    if expected_sha256 is not None and actual.lower() != expected_sha256.lower():
        raise ValueError("Checksum mismatch")

    if path.suffix == ".gz":
        try:
            with gzip.open(path, "rb") as handle:
                head = handle.read(4096).lower()
                if not any(marker in head for marker in _POSTGRES_HEADERS):
                    raise ValueError("Compressed backup does not resemble a PostgreSQL dump")
                # Read to EOF to verify every compressed member, gzip CRC and
                # size trailer. This is bounded-memory even for large backups.
                while handle.read(_CHUNK):
                    pass
        except (OSError, EOFError, zlib.error) as exc:
            raise ValueError("Compressed backup is incomplete or corrupt") from exc
    elif path.suffix == ".db":
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            result = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok":
                raise ValueError(f"SQLite integrity check failed: {result}")
        finally:
            connection.close()
    else:
        raise ValueError("Unsupported backup format")
    return actual


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--sha256")
    args = parser.parse_args()
    path = pathlib.Path(args.path)
    try:
        digest = verify_backup(path, args.sha256)
    except (OSError, sqlite3.DatabaseError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Backup verification passed: {path.name} sha256={digest}")


if __name__ == "__main__":
    main()
