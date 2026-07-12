from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.production import PosProductMapping, PosSaleEvent, Recipe
from app.models.user import User
from app.services.controls import add_audit

router = APIRouter(tags=["pos-sync"])


def fail(status: int, message: str):
    raise HTTPException(status, message)


@router.get("/integrations/pos/workspace")
def pos_workspace(db: Session = Depends(get_db), _: User = Depends(require_permission("integrations.read"))):
    mappings = db.scalars(select(PosProductMapping).order_by(PosProductMapping.pos_system, PosProductMapping.external_product_id)).all()
    events = db.scalars(select(PosSaleEvent).order_by(PosSaleEvent.processed_at.desc()).limit(100)).all()
    counts = dict(db.execute(select(PosSaleEvent.status, func.count()).group_by(PosSaleEvent.status)).all())
    inactive = sum(1 for row in mappings if not row.is_active)
    stale = 0
    mapping_rows = []
    for row in mappings:
        recipe = db.get(Recipe, row.recipe_id)
        healthy = bool(row.is_active and recipe and recipe.status == "approved")
        if row.is_active and not healthy:
            stale += 1
        mapping_rows.append({
            "id": row.id,
            "pos_system": row.pos_system,
            "external_product_id": row.external_product_id,
            "recipe_id": row.recipe_id,
            "location_id": row.location_id,
            "is_active": row.is_active,
            "recipe_status": recipe.status if recipe else "missing",
            "healthy": healthy,
        })
    return {
        "summary": {
            "mapping_count": len(mappings),
            "active_mapping_count": len(mappings) - inactive,
            "inactive_mapping_count": inactive,
            "stale_mapping_count": stale,
            "processed_event_count": counts.get("processed", 0),
            "failed_event_count": counts.get("failed", 0),
        },
        "mappings": mapping_rows,
        "events": [{
            "id": row.id,
            "external_event_id": row.external_event_id,
            "external_sale_id": row.external_sale_id,
            "pos_system": row.pos_system,
            "event_type": row.event_type,
            "status": row.status,
            "stock_document_id": row.stock_document_id,
            "reversal_of_event_id": row.reversal_of_event_id,
            "error": row.error,
            "processed_at": row.processed_at,
        } for row in events],
    }


@router.post("/pos-mappings/{mapping_id}/activate")
def activate_mapping(mapping_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission("integrations.*"))):
    row = db.get(PosProductMapping, mapping_id)
    if not row:
        fail(404, "POS mapping not found")
    recipe = db.get(Recipe, row.recipe_id)
    if not recipe or recipe.status != "approved":
        fail(409, "Only mappings to approved recipes can be activated")
    row.is_active = True
    add_audit(db, actor_user_id=user.id, action="pos.mapping_activated", entity_type="pos_product_mapping", entity_id=row.id)
    db.commit()
    return {"id": row.id, "is_active": row.is_active}


@router.post("/pos-mappings/{mapping_id}/deactivate")
def deactivate_mapping(mapping_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission("integrations.*"))):
    row = db.get(PosProductMapping, mapping_id)
    if not row:
        fail(404, "POS mapping not found")
    row.is_active = False
    add_audit(db, actor_user_id=user.id, action="pos.mapping_deactivated", entity_type="pos_product_mapping", entity_id=row.id)
    db.commit()
    return {"id": row.id, "is_active": row.is_active}
