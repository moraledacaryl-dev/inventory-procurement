from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg


def normalize_url(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def json_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return format(value, ".17g")
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (dict, list)):
        return value
    return str(value)


def application_tables(connection: psycopg.Connection[Any]) -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            select tablename
            from pg_catalog.pg_tables
            where schemaname = 'public'
              and tablename <> 'alembic_version'
            order by tablename
            """
        )
        return [row[0] for row in cursor.fetchall()]


def table_digest(connection: psycopg.Connection[Any], table: str) -> tuple[int, str]:
    quoted = connection.adapters.quote_identifier(table)
    with connection.cursor() as cursor:
        cursor.execute(f"select * from {quoted}")
        columns = [column.name for column in cursor.description or []]
        rows = []
        for record in cursor.fetchall():
            row = {column: json_value(value) for column, value in zip(columns, record, strict=True)}
            rows.append(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    rows.sort()
    payload = "\n".join(rows).encode("utf-8")
    return len(rows), hashlib.sha256(payload).hexdigest()


def snapshot(url: str) -> dict[str, dict[str, Any]]:
    with psycopg.connect(normalize_url(url)) as connection:
        return {
            table: {"rows": row_count, "sha256": digest}
            for table in application_tables(connection)
            for row_count, digest in [table_digest(connection, table)]
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two restored PostgreSQL databases table-by-table.")
    parser.add_argument("source_url")
    parser.add_argument("restored_url")
    args = parser.parse_args()

    source = snapshot(args.source_url)
    restored = snapshot(args.restored_url)
    if source != restored:
        source_tables = set(source)
        restored_tables = set(restored)
        differences = {
            "missing_from_restore": sorted(source_tables - restored_tables),
            "unexpected_in_restore": sorted(restored_tables - source_tables),
            "changed": {
                table: {"source": source.get(table), "restored": restored.get(table)}
                for table in sorted(source_tables & restored_tables)
                if source[table] != restored[table]
            },
        }
        raise SystemExit("Database restore mismatch:\n" + json.dumps(differences, indent=2, sort_keys=True))

    total_rows = sum(item["rows"] for item in source.values())
    print(json.dumps({"tables_verified": len(source), "rows_verified": total_rows}, sort_keys=True))


if __name__ == "__main__":
    main()
