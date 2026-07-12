from pathlib import Path
import re


def test_alembic_revision_ids_fit_version_table():
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    for path in versions_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        match = re.search(r"^revision\s*=\s*['\"]([^'\"]+)['\"]", text, re.MULTILINE)
        if match:
            revision = match.group(1)
            assert len(revision) <= 32, f"{path.name}: revision ID exceeds alembic_version VARCHAR(32): {revision}"
