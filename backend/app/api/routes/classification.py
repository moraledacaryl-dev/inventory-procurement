from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.classification import ItemWorkspaceAssignment, OperationalDimension
from app.models.inventory import Category, Item, Location
from app.models.user import User
from app.services.controls import add_audit

router = APIRouter(tags=["classification"])

DIMENSION_TYPES = {
    "workspace",
    "business_unit",
    "department",
    "outlet",
    "cost_center",
    "record_class",
    "item_type",
    "location_type",
    "asset_class",
    "depreciation_method",
    "condition_status",
    "movement_reason",
}


class DimensionCreate(BaseModel):
    dimension_type: str
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    behavior_key: str | None = Field(default=None, max_length=80)
    parent_id: str | None = None
    workspace_id: str | None = None
    sort_order: int = 0
    settings: dict[str, Any] = Field(default_factory=dict)


class DimensionUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    behavior_key: str | None = Field(default=None, max_length=80)
    parent_id: str | None = None
    workspace_id: str | None = None
    sort_order: int | None = None
    settings: dict[str, Any] | None = None
    is_active: bool | None = None


class ItemClassificationUpdate(BaseModel):
    primary_workspace_id: str | None = None
    item_type_id: str | None = None
    department_id: str | None = None
    cost_center_id: str | None = None
    default_location_id: str | None = None
    additional_workspace_ids: list[str] = Field(default_factory=list)


class BulkClassificationLine(ItemClassificationUpdate):
    item_id: str


class BulkClassificationRequest(BaseModel):
    lines: list[BulkClassificationLine] = Field(min_length=1, max_length=500)


def fail(status: int, message: str):
    raise HTTPException(status_code=status, detail=message)


def dimension_row(row: OperationalDimension) -> dict:
    return {
        "id": row.id,
        "dimension_type": row.dimension_type,
        "code": row.code,
        "name": row.name,
        "description": row.description,
        "behavior_key": row.behavior_key,
        "parent_id": row.parent_id,
        "workspace_id": row.workspace_id,
        "sort_order": row.sort_order,
        "settings": row.settings or {},
        "is_system": row.is_system,
        "is_active": row.is_active,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def get_dimension(db: Session, dimension_id: str | None, expected_type: str | None = None) -> OperationalDimension | None:
    if not dimension_id:
        return None
    row = db.get(OperationalDimension, dimension_id)
    if not row:
        fail(422, "Classification record not found")
    if expected_type and row.dimension_type != expected_type:
        fail(422, f"Expected {expected_type.replace('_', ' ')} classification")
    return row


def validate_links(db: Session, parent_id: str | None, workspace_id: str | None):
    if parent_id:
        get_dimension(db, parent_id)
    if workspace_id:
        get_dimension(db, workspace_id, "workspace")


def classification_row(item: Item, db: Session) -> dict:
    assignments = db.scalars(
        select(ItemWorkspaceAssignment)
        .where(ItemWorkspaceAssignment.item_id == item.id)
        .order_by(ItemWorkspaceAssignment.is_primary.desc(), ItemWorkspaceAssignment.created_at)
    ).all()
    return {
        "item_id": item.id,
        "sku": item.sku,
        "name": item.name,
        "primary_workspace_id": item.primary_workspace_id,
        "record_class_id": item.record_class_id,
        "item_type_id": item.item_type_id,
        "department_id": item.department_id,
        "cost_center_id": item.cost_center_id,
        "default_location_id": item.default_location_id,
        "workspace_ids": [row.workspace_id for row in assignments],
        "is_classified": bool(item.primary_workspace_id and item.item_type_id and item.record_class_id),
    }


def apply_item_classification(item: Item, payload: ItemClassificationUpdate, db: Session):
    workspace = get_dimension(db, payload.primary_workspace_id, "workspace") if payload.primary_workspace_id else None
    item_type = get_dimension(db, payload.item_type_id, "item_type") if payload.item_type_id else None
    department = get_dimension(db, payload.department_id) if payload.department_id else None
    cost_center = get_dimension(db, payload.cost_center_id, "cost_center") if payload.cost_center_id else None
    if payload.default_location_id and not db.get(Location, payload.default_location_id):
        fail(422, "Default location not found")
    if department and department.dimension_type not in {"department", "outlet"}:
        fail(422, "Department selection must be a department or outlet")
    if item_type and item_type.parent_id:
        record_class = get_dimension(db, item_type.parent_id, "record_class")
        item.record_class_id = record_class.id
    elif payload.item_type_id is not None:
        fail(422, "Item type must be connected to a record class")
    if workspace and item_type and item_type.workspace_id and item_type.workspace_id != workspace.id:
        type_workspace = get_dimension(db, item_type.workspace_id, "workspace")
        if not type_workspace or type_workspace.behavior_key != "shared":
            fail(422, "Item type belongs to a different workspace")
    item.primary_workspace_id = workspace.id if workspace else None
    item.item_type_id = item_type.id if item_type else None
    item.department_id = department.id if department else None
    item.cost_center_id = cost_center.id if cost_center else None
    item.default_location_id = payload.default_location_id

    requested = list(dict.fromkeys([x for x in payload.additional_workspace_ids if x]))
    if workspace and workspace.id not in requested:
        requested.insert(0, workspace.id)
    for workspace_id in requested:
        get_dimension(db, workspace_id, "workspace")
    existing = {
        assignment.workspace_id: assignment
        for assignment in db.scalars(select(ItemWorkspaceAssignment).where(ItemWorkspaceAssignment.item_id == item.id)).all()
    }
    for workspace_id, assignment in list(existing.items()):
        if workspace_id not in requested:
            db.delete(assignment)
    for workspace_id in requested:
        assignment = existing.get(workspace_id)
        if not assignment:
            assignment = ItemWorkspaceAssignment(item_id=item.id, workspace_id=workspace_id)
            db.add(assignment)
        assignment.is_primary = bool(workspace and workspace_id == workspace.id)


@router.get("/classification/dimensions")
def list_dimensions(
    dimension_type: str | None = None,
    workspace_id: str | None = None,
    active: bool | None = True,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("items.read")),
):
    stmt = select(OperationalDimension)
    if dimension_type:
        stmt = stmt.where(OperationalDimension.dimension_type == dimension_type)
    if workspace_id:
        stmt = stmt.where(OperationalDimension.workspace_id == workspace_id)
    if active is not None:
        stmt = stmt.where(OperationalDimension.is_active == active)
    rows = db.scalars(stmt.order_by(OperationalDimension.dimension_type, OperationalDimension.sort_order, OperationalDimension.name)).all()
    return [dimension_row(row) for row in rows]


@router.get("/classification/bootstrap")
def classification_bootstrap(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("items.read")),
):
    rows = db.scalars(select(OperationalDimension).order_by(OperationalDimension.dimension_type, OperationalDimension.sort_order, OperationalDimension.name)).all()
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row.dimension_type].append(dimension_row(row))
    unclassified = db.scalar(
        select(func.count()).select_from(Item).where(
            (Item.primary_workspace_id.is_(None)) | (Item.item_type_id.is_(None)) | (Item.record_class_id.is_(None))
        )
    ) or 0
    return {
        "dimensions": grouped,
        "categories": [
            {
                "id": category.id,
                "name": category.name,
                "description": category.description,
                "parent_id": category.parent_id,
                "sort_order": category.sort_order,
                "is_active": category.is_active,
            }
            for category in db.scalars(select(Category).order_by(Category.sort_order, Category.name)).all()
        ],
        "summary": {
            "unclassified_items": unclassified,
            "active_workspaces": sum(1 for row in rows if row.dimension_type == "workspace" and row.is_active),
            "active_item_types": sum(1 for row in rows if row.dimension_type == "item_type" and row.is_active),
        },
    }


@router.post("/classification/dimensions", status_code=201)
def create_dimension(
    payload: DimensionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("items.*")),
):
    if payload.dimension_type not in DIMENSION_TYPES:
        fail(422, "Unsupported classification master")
    validate_links(db, payload.parent_id, payload.workspace_id)
    row = OperationalDimension(
        dimension_type=payload.dimension_type,
        code=payload.code.strip().lower().replace(" ", "-"),
        name=payload.name.strip(),
        description=payload.description,
        behavior_key=payload.behavior_key.strip() if payload.behavior_key else None,
        parent_id=payload.parent_id,
        workspace_id=payload.workspace_id,
        sort_order=payload.sort_order,
        settings=payload.settings,
        is_system=False,
    )
    db.add(row)
    try:
        db.flush()
        add_audit(db, actor_user_id=user.id, action="classification.dimension_created", entity_type="operational_dimension", entity_id=row.id, details={"dimension_type": row.dimension_type, "code": row.code})
        db.commit(); db.refresh(row)
        return dimension_row(row)
    except IntegrityError:
        db.rollback(); fail(409, "A classification with this code already exists")


@router.patch("/classification/dimensions/{dimension_id}")
def update_dimension(
    dimension_id: str,
    payload: DimensionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("items.*")),
):
    row = db.get(OperationalDimension, dimension_id)
    if not row:
        fail(404, "Classification record not found")
    data = payload.model_dump(exclude_unset=True)
    validate_links(db, data.get("parent_id"), data.get("workspace_id"))
    if data.get("parent_id") == row.id or data.get("workspace_id") == row.id:
        fail(422, "A classification cannot reference itself")
    if row.is_system and "behavior_key" in data and data["behavior_key"] != row.behavior_key:
        fail(409, "System behavior cannot be changed; rename the visible record instead")
    if "code" in data:
        data["code"] = data["code"].strip().lower().replace(" ", "-")
    if "name" in data:
        data["name"] = data["name"].strip()
    changes = {key: {"from": getattr(row, key), "to": value} for key, value in data.items() if getattr(row, key) != value}
    for key, value in data.items():
        setattr(row, key, value)
    try:
        add_audit(db, actor_user_id=user.id, action="classification.dimension_updated", entity_type="operational_dimension", entity_id=row.id, details={"changes": changes})
        db.commit(); db.refresh(row)
        return dimension_row(row)
    except IntegrityError:
        db.rollback(); fail(409, "Classification update conflicts with an existing record")


@router.get("/classification/items")
def list_item_classifications(
    unclassified: bool | None = None,
    workspace_id: str | None = None,
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("items.read")),
):
    stmt = select(Item).order_by(Item.sku)
    if unclassified is True:
        stmt = stmt.where((Item.primary_workspace_id.is_(None)) | (Item.item_type_id.is_(None)) | (Item.record_class_id.is_(None)))
    if workspace_id:
        stmt = stmt.where(Item.primary_workspace_id == workspace_id)
    return [classification_row(item, db) for item in db.scalars(stmt.limit(limit)).all()]


@router.patch("/classification/items/{item_id}")
def update_item_classification(
    item_id: str,
    payload: ItemClassificationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("items.*")),
):
    item = db.get(Item, item_id)
    if not item:
        fail(404, "Item not found")
    apply_item_classification(item, payload, db)
    add_audit(db, actor_user_id=user.id, action="item.classification_updated", entity_type="item", entity_id=item.id, details=payload.model_dump())
    db.commit(); db.refresh(item)
    return classification_row(item, db)


@router.post("/classification/items/bulk-assign")
def bulk_assign_items(
    payload: BulkClassificationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("items.*")),
):
    changed = []
    for line in payload.lines:
        item = db.get(Item, line.item_id)
        if not item:
            fail(404, f"Item not found: {line.item_id}")
        apply_item_classification(item, ItemClassificationUpdate(**line.model_dump(exclude={"item_id"})), db)
        changed.append(item.id)
    add_audit(db, actor_user_id=user.id, action="item.classification_bulk_updated", entity_type="item", entity_id="bulk", details={"item_ids": changed})
    db.commit()
    return {"updated": len(changed), "item_ids": changed}
