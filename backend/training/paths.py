"""Duty courses are subsets of source-authorized lessons, never new roles."""
from dataclasses import dataclass
from training.curriculum import LESSONS, BY_ID, ROLES, ROLE_NAMES


@dataclass(frozen=True)
class DutyPath:
    id: str
    title: str
    role: str
    description: str
    lessons: tuple[str, ...]
    final_tasks: tuple[str, ...]


def ids(role,modules=None,include=(),exclude=()):
    return tuple(lesson.id for lesson in LESSONS if role in lesson.roles and (modules is None or lesson.module in modules or lesson.id in include) and lesson.id not in exclude)


def duty(id,title,description,lessons,final_tasks,role="inventory_manager"):
    return DutyPath(id,title,role,description,tuple(lessons),tuple(final_tasks))


FINAL_TASKS={
    "inventory_manager":("cap-monthly-count","cap-restaurant-service","reservation-shortage"),
    "procurement_officer":("cap-busy-weekend","request-self-approval","purchase-approval-limit"),
    "receiver":("cap-delivery-recovery","check-order"),
    "counter":("cap-monthly-count","count-zero","stale-count-snapshot"),
    "viewer":("available-stock","management-review"),
    "owner":("cap-owner-review","cap-busy-weekend","cap-monthly-count"),
}
# Preserve all source-role curricula for existing participants and trainers.
PATHS=[duty("role-"+role,ROLE_NAMES[role],"The complete course for these source-supported training responsibilities. Use only your authorized production locations and approval limits.",ids(role),FINAL_TASKS[role],role) for role in ROLES]
PATHS += [
    duty("stockroom","Stockroom and inventory","Receive responsibility for accurate stock, units, controlled handovers, counts and traceability. Ask purchasing colleagues to create supplier commitments.",ids("inventory_manager","ABCDEFGHO",exclude=("catalogue-scope-required",)),("cap-monthly-count","transfer-receipt-variance","reservation-shortage")),
    duty("kitchen","Kitchen preparation","Read approved formulas, record actual preparation and waste, and use prepared stock correctly. Formula approval and supplier commitments belong to authorized colleagues.",ids("inventory_manager","ABDEHOPQT",exclude=("approved-opening-correction","create-governed-recipe","approve-colleague-recipe","recipe-self-approval","retire-obsolete-recipe","create-traceable-lot","tracked-opening-receipt","lot-quantity-shortage")),("cap-restaurant-service","record-waste")),
    duty("cafe","Cafe supplies and service","Track service supplies, transfers, waste and actual staff consumption. Check base units before use; do not change menu prices or supplier commitments without that separate assignment.",ids("inventory_manager","ABDEHT",include=("catalogue-units","transfer-stock","receive-controlled-transfer","transfer-receipt-variance","expiry-rotation","recipe-cost","menu-mapping"),exclude=("approved-opening-correction","expired-lot-writeoff")),("transfer-receipt-variance","staff-meal","available-stock")),
    duty("bar","Bar supplies and service","Record actual issues and handovers and inspect usable stock and expiry. Bottle, case and volume units must be checked against the item's configured base unit; production access remains separately assigned.",ids("inventory_manager","ABDEHT",include=("catalogue-units","transfer-stock","receive-controlled-transfer","transfer-receipt-variance","expiry-rotation","menu-mapping"),exclude=("approved-opening-correction","expired-lot-writeoff")),("transfer-receipt-variance","record-waste","available-stock")),
    duty("housekeeping","Housekeeping and linen","Issue individual amenities and count reusable linen at each custody and condition handover. A room standard does not prove delivery or cleanliness.",ids("inventory_manager","ABU",include=("catalogue-units",)),("cap-housekeeping","available-stock")),
    duty("maintenance","Maintenance and assets","Identify the actual asset, plan preventive work, start the assigned job and complete verified zero-charge work. Charged repairs require the supported authorized cost process.",ids("inventory_manager","ABV",exclude=("prepare-depreciation-run","post-reviewed-depreciation")),("create-maintenance-work-order","complete-maintenance-work","asset-maintenance")),
    duty("department-supervisor","Department supervision","Review saved differences and formulas independently. Do not approve your own work or change observed quantities to avoid review.",ids("inventory_manager","ABGP",exclude=("create-governed-recipe","retire-obsolete-recipe")),("cap-monthly-count","recipe-self-approval","request-count-recheck")),
    duty("accounting-review","Accounting-related inventory review","Read permitted stock and purchasing evidence. This viewer course grants no journal posting, event retry, stock adjustment or production Accounting access.",ids("viewer"),("available-stock","management-review"),"viewer"),
]
BY_PATH={path.id:path for path in PATHS}
assert len(BY_PATH)==len(PATHS)
for path in PATHS:
    assert path.lessons and set(path.final_tasks)<=set(path.lessons),path.id
    assert all(path.role in BY_ID[id].roles for id in path.lessons),path.id


def default_path(role):return "role-"+role


def public_paths():
    from dataclasses import asdict
    return [asdict(path) for path in PATHS]
