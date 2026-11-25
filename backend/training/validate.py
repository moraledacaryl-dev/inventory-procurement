"""CI drift gate. Updating the baseline requires reviewing lesson fidelity."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "docs/training/source-contract.json"


def source_hashes():
    paths = sorted(set((ROOT / "backend/app").rglob("*.py")))
    paths += sorted(path for path in (ROOT / "frontend/app").rglob("page.tsx") if "training" not in path.parts)
    paths += sorted(path for path in (ROOT / "frontend/app").rglob("*.css") if "training" not in path.parts)
    paths.append(ROOT / "frontend/app/layout.tsx")
    paths += sorted(path for path in (ROOT / "frontend/components").glob("*.tsx") if path.name != "InventoryTrainingCoach.tsx")
    paths.append(ROOT / "frontend/lib/api.ts")
    paths.append(ROOT / "frontend/hooks/useFormDraft.ts")
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def validate():
    baseline = json.loads(BASELINE.read_text())
    actual = source_hashes()
    changed = sorted(key for key in actual.keys() | baseline["files"].keys() if actual.get(key) != baseline["files"].get(key))
    if changed:
        raise SystemExit("Inventory source changed; review training contracts and fixtures before refreshing the baseline:\n" + "\n".join(changed))
    from training.curriculum import LESSONS, ROLES, CAPSTONES
    from training.scenarios import public_lesson
    modules = {lesson.module for lesson in LESSONS}
    assert modules == set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    from app.core.roles import Role
    assert set(ROLES) == {role.value for role in Role}
    for lesson in LESSONS:
        for mode in ("guided","assisted","independent"):
            public_lesson(lesson,mode)
        assert set(lesson.roles).issubset(ROLES)
        assert lesson.steps or lesson.workflow.startswith("read_")
        assert lesson.question and lesson.answer and lesson.correction
        route = lesson.route.split("?")[0]
        import re
        route = re.sub(r"\{[^}]+\}", "[id]", route)
        assert (ROOT / "frontend/app" / route.lstrip("/") / "page.tsx").exists(), lesson.id
        assert all((ROOT / "backend/app/api/routes" / source).exists() for source in lesson.sources)
    for capstone in CAPSTONES:
        assert all(any(lesson.id == ident for lesson in LESSONS) for ident in capstone["lessons"])
    print(f"Verified {len(LESSONS)} lesson definitions, 26 modules, 6 roles, {len(actual)} operational source contracts and {len(CAPSTONES)} task sequences")


if __name__ == "__main__":
    if "--record-reviewed-baseline" in sys.argv:
        BASELINE.write_text(json.dumps({"inventory_main": "07c651d0111be2840cac81b66bb1d7b97fd4c616", "operations_main": "63a9e7c011ecfa140f7ae3e75612c2d5d6e4fa86", "files": source_hashes()}, indent=2) + "\n")
    else:
        validate()
