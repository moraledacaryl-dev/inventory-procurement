"""Duty courses are subsets of source-authorized lessons, never new roles."""
from dataclasses import dataclass, replace
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
PATHS=[duty("role-"+role,ROLE_NAMES[role],"Practise the tasks assigned to this role.",ids(role),FINAL_TASKS[role],role) for role in ROLES]
PATHS += [
    duty("stockroom","Stockroom and inventory","Practise receiving, stock movements, counts and batch tracking.",ids("inventory_manager","ABCDEFGHO",exclude=("catalogue-scope-required",)),("cap-monthly-count","transfer-receipt-variance","reservation-shortage")),
    duty("kitchen","Kitchen preparation","Use approved recipes and record preparation, meals and waste.",ids("inventory_manager","ABDEHOPQT",exclude=("stock-screen-signed-correction","issue-cafe-case","issue-bar-volume","approved-opening-correction","create-governed-recipe","approve-colleague-recipe","recipe-self-approval","retire-obsolete-recipe","create-traceable-lot","tracked-opening-receipt","lot-quantity-shortage")),("cap-restaurant-service","record-waste")),
    duty("cafe","Cafe supplies and service","Track cafe supplies, transfers, staff meals and waste. Check item units before use.",ids("inventory_manager","ABDEHT",include=("catalogue-units","transfer-stock","receive-controlled-transfer","transfer-receipt-variance","expiry-rotation","recipe-cost","menu-mapping"),exclude=("stock-screen-signed-correction","issue-bar-volume","approved-opening-correction","expired-lot-writeoff")),("transfer-receipt-variance","staff-meal","available-stock")),
    duty("bar","Bar supplies and service","Record bar supplies and transfers. Check units, available stock and expiry.",ids("inventory_manager","ABDEHT",include=("catalogue-units","transfer-stock","receive-controlled-transfer","transfer-receipt-variance","expiry-rotation","menu-mapping"),exclude=("stock-screen-signed-correction","issue-cafe-case","approved-opening-correction","expired-lot-writeoff")),("transfer-receipt-variance","record-waste","available-stock")),
    duty("housekeeping","Housekeeping and linen","Issue guest amenities and track linen through use, laundry and clean return.",ids("inventory_manager","ABU",include=("catalogue-units",)),("cap-housekeeping","available-stock")),
    duty("maintenance","Maintenance and assets","Register equipment, schedule maintenance and record completed work.",ids("inventory_manager","ABV",exclude=("prepare-depreciation-run","post-reviewed-depreciation")),("create-maintenance-work-order","complete-costed-maintenance","asset-maintenance")),
    duty("department-supervisor","Department supervision","Review stock differences and recipes. Do not approve your own work.",ids("inventory_manager","ABGP",exclude=("create-governed-recipe","retire-obsolete-recipe")),("cap-monthly-count","recipe-self-approval","request-count-recheck")),
    duty("accounting-review","Accounting-related inventory review","Review stock and purchasing reports without changing records.",ids("viewer"),("available-stock","management-review"),"viewer"),
]
# All stock/department staff can read their alerts and submit specific feedback.
COMMON_STOCK={"acknowledge-operational-alert","submit-workflow-feedback"}
PATHS=[replace(path,lessons=tuple(lesson.id for lesson in LESSONS if lesson.id in set(path.lessons)|COMMON_STOCK)) if path.role=="inventory_manager" else path for path in PATHS]
BY_PATH={path.id:path for path in PATHS}
assert len(BY_PATH)==len(PATHS)
for path in PATHS:
    assert path.lessons and set(path.final_tasks)<=set(path.lessons),path.id
    assert all(path.role in BY_ID[id].roles for id in path.lessons),path.id


def default_path(role):return "role-"+role


def public_paths():
    from dataclasses import asdict
    return [asdict(path) for path in PATHS]
