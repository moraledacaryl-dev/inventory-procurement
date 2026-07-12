from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.inventory import Item, Location
from app.models.procurement import Supplier
from app.models.user import User
from app.services.controls import add_audit, enqueue_event

router = APIRouter(tags=["shared-master-data"])


class PublishMasterData(BaseModel):
    destinations: list[str] = ["staff", "command-center", "accounting"]


def identity_row(user: User) -> dict:
    return {
        "canonical_user_id": user.id,
        "employee_identity_key": user.email.lower().strip(),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


@router.get("/shared-identities")
def shared_identities(db: Session = Depends(get_db), _: User = Depends(require_permission("users.read"))):
    rows = db.scalars(select(User).order_by(User.full_name, User.email)).all()
    return {"identities": [identity_row(row) for row in rows], "count": len(rows)}


@router.get("/shared-identities/resolve")
def resolve_identity(email: str, db: Session = Depends(get_db), _: User = Depends(require_permission("users.read"))):
    normalized = email.lower().strip()
    row = db.scalar(select(User).where(User.email == normalized))
    if not row:
        raise HTTPException(404, "Shared identity not found")
    return identity_row(row)


@router.get("/master-data/workspace")
def master_data_workspace(db: Session = Depends(get_db), _: User = Depends(require_permission("integrations.read"))):
    users = db.scalars(select(User).order_by(User.full_name)).all()
    items = db.scalars(select(Item).order_by(Item.sku)).all()
    locations = db.scalars(select(Location).order_by(Location.code)).all()
    suppliers = db.scalars(select(Supplier).order_by(Supplier.code)).all()
    return {
        "summary": {
            "identity_count": len(users),
            "active_identity_count": sum(1 for row in users if row.is_active),
            "item_count": len(items),
            "active_item_count": sum(1 for row in items if row.is_active),
            "location_count": len(locations),
            "active_location_count": sum(1 for row in locations if row.is_active),
            "supplier_count": len(suppliers),
            "active_supplier_count": sum(1 for row in suppliers if row.is_active),
        },
        "identities": [identity_row(row) for row in users],
        "items": [{"canonical_id": row.id, "code": row.sku, "name": row.name, "is_active": row.is_active} for row in items],
        "locations": [{"canonical_id": row.id, "code": row.code, "name": row.name, "is_active": row.is_active} for row in locations],
        "suppliers": [{"canonical_id": row.id, "code": row.code, "name": row.name, "is_active": row.is_active} for row in suppliers],
    }


@router.post("/master-data/publish")
def publish_master_data(payload: PublishMasterData, db: Session = Depends(get_db), user: User = Depends(require_permission("integrations.*"))):
    allowed = {"staff", "command-center", "accounting"}
    destinations = list(dict.fromkeys(payload.destinations))
    invalid = set(destinations) - allowed
    if invalid:
        raise HTTPException(422, f"Unsupported destination: {', '.join(sorted(invalid))}")
    workspace = master_data_workspace(db, user)
    published = []
    for destination in destinations:
        event = enqueue_event(
            db,
            destination_system=destination,
            event_type="inventory.master_data.snapshot",
            aggregate_type="master_data",
            aggregate_id="canonical",
            idempotency_key=f"master-data:{destination}:{workspace['summary']['identity_count']}:{workspace['summary']['item_count']}:{workspace['summary']['location_count']}:{workspace['summary']['supplier_count']}",
            payload=workspace,
        )
        published.append({"destination": destination, "event_id": event.id})
    add_audit(db, actor_user_id=user.id, action="master_data.published", entity_type="master_data", entity_id="canonical", details={"destinations": destinations})
    db.commit()
    return {"published": published, "summary": workspace["summary"]}
