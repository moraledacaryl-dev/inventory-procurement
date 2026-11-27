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
        assert all(step.outcome_method in {None,"GET","POST","PUT","PATCH","DELETE"} and (step.outcome_method is None or step.outcome) for step in lesson.steps)
        route = lesson.route.split("?")[0]
        import re
        route = re.sub(r"\{[^}]+\}", "[id]", route)
        assert (ROOT / "frontend/app" / route.lstrip("/") / "page.tsx").exists(), lesson.id
        assert all((ROOT / "backend/app/api/routes" / source).exists() for source in lesson.sources)
    for capstone in CAPSTONES:
        assert all(any(lesson.id == ident for lesson in LESSONS) for ident in capstone["lessons"])
        if capstone.get("linked"):
            assert len(capstone["lessons"])==1 and next(lesson for lesson in LESSONS if lesson.id==capstone["lessons"][0]).workflow.startswith("capstone_")
    from training.paths import PATHS
    from training.exams import blueprint,public_blueprint
    exams=0
    for path in PATHS:
        assert all(path.role in next(lesson.roles for lesson in LESSONS if lesson.id==id) for id in path.lessons)
        for module in [None]+sorted({next(lesson.module for lesson in LESSONS if lesson.id==id) for id in path.lessons}):
            row=blueprint(path.id,module)
            assert set(row["practical_lessons"])<=set(path.lessons)
            assert all(question.prompt and question.answer and question.correction for question in row["questions"])
            assert all("answer" not in question for question in public_blueprint(row)["questions"])
            exams+=1
    linked=sum(bool(row.get("linked")) for row in CAPSTONES)
    print(f"Verified {len(LESSONS)} lesson definitions, 26 modules, 6 roles, {len(actual)} operational source contracts, {linked} linked capstones and {len(CAPSTONES)-linked} task sequences, {len(PATHS)} duty courses and {exams} final-check blueprints")


if __name__ == "__main__":
    if "--record-reviewed-baseline" in sys.argv:
        BASELINE.write_text(json.dumps({"inventory_main": "6f6723da5a4f22986a8e0cee53272f8a88efb03e", "operations_main": "63a9e7c011ecfa140f7ae3e75612c2d5d6e4fa86", "files": source_hashes()}, indent=2) + "\n")
    else:
        validate()
