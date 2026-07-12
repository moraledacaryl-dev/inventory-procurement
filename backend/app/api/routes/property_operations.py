from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.classification import OperationalDimension
from app.models.inventory import Item, Location
from app.models.property import HotelParLine, HotelParProfile, PropertyBalance, PropertyMovement
from app.models.user import User
from app.services.controls import add_audit, next_document_number

router = APIRouter(tags=["property-operations"])


class PropertyMoveIn(BaseModel):
    item_id: str
    quantity: Decimal = Field(gt=0)
    source_location_id: str | None = None
    destination_location_id: str | None = None
    source_condition_id: str | None = None
    destination_condition_id: str | None = None
    movement_reason_id: str | None = None
    assignee_user_id: str | None = None
    reference: str | None = Field(default=None, max_length=160)
    notes: str | None = None


class ParLineIn(BaseModel):
    item_id: str
    par_quantity: Decimal = Field(gt=0)
    notes: str | None = None


class ParProfileIn(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    profile_type: str = Field(default="room_type", pattern="^(room_type|floor|pantry|department)$")
    location_id: str | None = None
    lines: list[ParLineIn] = Field(default_factory=list)


def fail(code: int, message: str):
    raise HTTPException(code, message)


def dimension(db: Session, dimension_id: str | None, expected: str) -> OperationalDimension | None:
    if not dimension_id:
        return None
    row = db.get(OperationalDimension, dimension_id)
    if not row or row.dimension_type != expected or not row.is_active:
        fail(422, f"Active {expected.replace('_', ' ')} not found")
    return row


def reusable_item(db: Session, item_id: str) -> Item:
    item = db.get(Item, item_id)
    if not item or not item.is_active or not item.item_type_id:
        fail(422, "Active reusable-property item not found")
    item_type = db.get(OperationalDimension, item.item_type_id)
    if not item_type or item_type.dimension_type != "item_type" or item_type.behavior_key != "reusable_property":
        fail(422, "Item is not configured as reusable operating property")
    return item


def bucket(db: Session, item_id: str, location_id: str, condition_id: str, lock: bool = False) -> PropertyBalance | None:
    stmt = select(PropertyBalance).where(
        PropertyBalance.item_id == item_id,
        PropertyBalance.location_id == location_id,
        PropertyBalance.condition_id == condition_id,
    )
    if lock:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def apply_bucket(db: Session, item_id: str, location_id: str, condition_id: str, delta: Decimal):
    row = bucket(db, item_id, location_id, condition_id, lock=True)
    if not row:
        if delta < 0:
            fail(409, "Reusable-property source balance is insufficient")
        row = PropertyBalance(item_id=item_id, location_id=location_id, condition_id=condition_id, quantity=0)
        db.add(row)
        db.flush()
    next_quantity = Decimal(row.quantity) + delta
    if next_quantity < 0:
        fail(409, "Reusable-property source balance is insufficient")
    row.quantity = next_quantity


@router.get("/property/balances")
def list_balances(
    item_id: str | None = None,
    location_id: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.read")),
):
    stmt = select(PropertyBalance).order_by(PropertyBalance.location_id, PropertyBalance.item_id, PropertyBalance.condition_id)
    if item_id:
        stmt = stmt.where(PropertyBalance.item_id == item_id)
    if location_id:
        stmt = stmt.where(PropertyBalance.location_id == location_id)
    return db.scalars(stmt).all()


@router.get("/property/movements")
def list_movements(
    item_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory.read")),
):
    stmt = select(PropertyMovement).order_by(PropertyMovement.created_at.desc()).limit(limit)
    if item_id:
        stmt = stmt.where(PropertyMovement.item_id == item_id)
    return db.scalars(stmt).all()


@router.post("/property/movements", status_code=201)
def move_property(
    payload: PropertyMoveIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.*")),
):
    reusable_item(db, payload.item_id)
    source_condition = dimension(db, payload.source_condition_id, "condition_status")
    destination_condition = dimension(db, payload.destination_condition_id, "condition_status")
    dimension(db, payload.movement_reason_id, "movement_reason")
    if payload.source_location_id and not db.get(Location, payload.source_location_id):
        fail(422, "Source location not found")
    if payload.destination_location_id and not db.get(Location, payload.destination_location_id):
        fail(422, "Destination location not found")
    if bool(payload.source_location_id) != bool(source_condition):
        fail(422, "Source location and condition must be supplied together")
    if bool(payload.destination_location_id) != bool(destination_condition):
        fail(422, "Destination location and condition must be supplied together")
    if not payload.source_location_id and not payload.destination_location_id:
        fail(422, "A source or destination bucket is required")
    if payload.source_location_id:
        apply_bucket(db, payload.item_id, payload.source_location_id, source_condition.id, -payload.quantity)
    if payload.destination_location_id:
        apply_bucket(db, payload.item_id, payload.destination_location_id, destination_condition.id, payload.quantity)
    row = PropertyMovement(
        movement_number=next_document_number(db, "PROP"),
        **payload.model_dump(),
        created_by_user_id=user.id,
    )
    db.add(row)
    add_audit(
        db,
        actor_user_id=user.id,
        action="property.moved",
        entity_type="property_movement",
        entity_id=row.id,
        details={"item_id": payload.item_id, "quantity": str(payload.quantity)},
    )
    db.commit()
    db.refresh(row)
    return row


@router.get("/hotel/par-profiles")
def list_par_profiles(db: Session = Depends(get_db), _: User = Depends(require_permission("inventory.read"))):
    profiles = db.scalars(select(HotelParProfile).order_by(HotelParProfile.code)).all()
    lines = db.scalars(select(HotelParLine).order_by(HotelParLine.profile_id, HotelParLine.item_id)).all()
    grouped: dict[str, list[HotelParLine]] = {}
    for line in lines:
        grouped.setdefault(line.profile_id, []).append(line)
    return [{"profile": row, "lines": grouped.get(row.id, [])} for row in profiles]


@router.post("/hotel/par-profiles", status_code=201)
def create_par_profile(
    payload: ParProfileIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.*")),
):
    if payload.location_id and not db.get(Location, payload.location_id):
        fail(422, "Par-profile location not found")
    item_ids = [line.item_id for line in payload.lines]
    if len(item_ids) != len(set(item_ids)):
        fail(422, "Each item may appear only once in a par profile")
    for item_id in item_ids:
        reusable_item(db, item_id)
    row = HotelParProfile(
        code=payload.code.upper().strip(),
        name=payload.name.strip(),
        profile_type=payload.profile_type,
        location_id=payload.location_id,
    )
    db.add(row)
    try:
        db.flush()
        for line in payload.lines:
            db.add(HotelParLine(profile_id=row.id, **line.model_dump()))
        add_audit(db, actor_user_id=user.id, action="hotel_par.created", entity_type="hotel_par_profile", entity_id=row.id)
        db.commit()
        return {"profile": row, "lines": db.scalars(select(HotelParLine).where(HotelParLine.profile_id == row.id)).all()}
    except IntegrityError:
        db.rollback()
        fail(409, "Par profile code or item line already exists")
