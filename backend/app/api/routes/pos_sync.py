from fastapi import APIRouter, Depends, HTTPException
import json
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.api.integration_auth import require_integration_actor
from app.db.session import get_db
from app.models.menu import MenuItem
from app.models.inventory import StockMovement
from app.models.production import PosProductMapping, PosSaleEvent, Recipe
from app.models.pos_rules import PosModifierTemplate, PosPricingRule
from app.models.user import User
from app.services.controls import add_audit
from app.services.operational_authorization import require_scoped_locations, visible_location_ids

router = APIRouter(tags=["pos-sync"])


def fail(status: int, message: str):
    raise HTTPException(status, message)


@router.get("/integrations/pos/catalog")
def pos_catalog_feed(
    db: Session = Depends(get_db),
    _: User = Depends(require_integration_actor("hidden-oasis-pos")),
):
    """Machine-readable selling catalog owned by Inventory & Procurement."""
    items = db.scalars(
        select(MenuItem)
        .options(selectinload(MenuItem.variants))
        .order_by(MenuItem.category, MenuItem.sort_order, MenuItem.display_name)
    ).unique().all()
    templates = {x.id: x for x in db.scalars(select(PosModifierTemplate).where(PosModifierTemplate.is_active.is_(True))).all()}
    pricing_rules = db.scalars(select(PosPricingRule).where(PosPricingRule.is_active.is_(True)).order_by(PosPricingRule.priority, PosPricingRule.name)).all()
    rows = []
    for item in items:
        inline_groups = json.loads(item.modifier_groups_json or "[]")
        template_groups = []
        for template_id in json.loads(item.modifier_template_ids_json or "[]"):
            template = templates.get(template_id)
            if template:
                template_groups.append(json.loads(template.config_json))
        resolved_groups = template_groups + inline_groups
        for variant in sorted(item.variants, key=lambda row: (row.sort_order, row.name)):
            rows.append({
                "menu_item_id": item.id,
                "variant_id": variant.id,
                "menu_item_name": item.name,
                "display_name": item.display_name or item.name,
                "variant_name": variant.name,
                "category": item.category,
                "prep_station": item.prep_station,
                "pricing_role": item.pricing_role,
                "pricing_tags": json.loads(item.pricing_tags_json or "[]"),
                "modifier_groups": resolved_groups,
                "modifier_template_ids": json.loads(item.modifier_template_ids_json or "[]"),
                "sort_order": item.sort_order,
                "sku": variant.sku,
                "barcode": variant.barcode,
                "price": str(variant.price),
                "with_drink_price": str(variant.with_drink_price) if variant.with_drink_price is not None else None,
                "conditional_prices": json.loads(variant.conditional_prices_json or "[]"),
                "is_active": bool(item.is_active and item.pos_visible and variant.is_active),
                "pos_visible": bool(item.pos_visible),
            })
    return {
        "source": "inventory-procurement",
        "items": rows,
        "count": len(rows),
        "pricing_rules": [
            {"id": x.id, "name": x.name, "qualifier_tag": x.qualifier_tag, "target_tag": x.target_tag, "priority": x.priority}
            for x in pricing_rules
        ],
    }


@router.get("/integrations/pos/workspace")
def pos_workspace(db: Session = Depends(get_db), user: User = Depends(require_permission("integrations.read"))):
    allowed = visible_location_ids(db, user)
    mapping_stmt = select(PosProductMapping).order_by(PosProductMapping.pos_system, PosProductMapping.external_product_id)
    event_stmt = select(PosSaleEvent)
    if allowed is not None:
        mapping_stmt = mapping_stmt.where(PosProductMapping.location_id.in_(allowed))
        # POS sale records lack a trusted location field. Only expose events
        # whose posted stock document has movements entirely within scope.
        # Unposted/failed events and cross-location events remain owner-only.
        visible_docs = (
            select(StockMovement.document_id)
            .group_by(StockMovement.document_id)
            .having(func.sum(case((StockMovement.location_id.in_(allowed), 0), else_=1)) == 0)
        )
        event_stmt = event_stmt.where(PosSaleEvent.stock_document_id.in_(visible_docs))
    mappings = db.scalars(mapping_stmt).all()
    events = db.scalars(event_stmt.order_by(PosSaleEvent.processed_at.desc()).limit(100)).all()
    counts = dict(db.execute(
        select(PosSaleEvent.status, func.count())
        .where(PosSaleEvent.stock_document_id.in_(visible_docs) if allowed is not None else True)
        .group_by(PosSaleEvent.status)
    ).all())
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
    require_scoped_locations(db, user, {row.location_id})
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
    require_scoped_locations(db, user, {row.location_id})
    row.is_active = False
    add_audit(db, actor_user_id=user.id, action="pos.mapping_deactivated", entity_type="pos_product_mapping", entity_id=row.id)
    db.commit()
    return {"id": row.id, "is_active": row.is_active}
