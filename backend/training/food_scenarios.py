"""Real food-workflow fixtures and transaction-integrity assertions."""
import json
from decimal import Decimal
from sqlalchemy import select
from app.models.inventory import Item, StockBalance, StockDocument
from app.models.production import Recipe, ProductionBatch, PosProductMapping
from app.models.staff_meals import StaffMeal
from app.models.menu import MenuItem
from app.models.audit_log import AuditLog
from app.services.classification_defaults import DEFAULT_DIMENSIONS


def prepare_food(db,lesson,v):
    if not lesson.workflow.startswith("food_"):return
    dimensions={r["code"]:r["id"] for r in DEFAULT_DIMENSIONS}
    for item_id,type in [(v["chicken"],"ingredient"),(v["alfredo"],"finished-fnb-product")]:
        item=db.get(Item,item_id);item.primary_workspace_id=dimensions["fnb"];item.item_type_id=dimensions[type]
    recipe=db.get(Recipe,v["recipe"])
    if lesson.id in {"approve-colleague-recipe","recipe-self-approval"}:
        recipe.status="draft";recipe.approved_by_user_id=None;recipe.approved_at=None
        if lesson.id=="recipe-self-approval":recipe.created_by_user_id=v["actor"]
    if lesson.id=="disable-stale-pos-mapping":
        recipe.status="retired"
        db.add(PosProductMapping(id="training-pos-map",pos_system="hidden-oasis-pos",external_product_id="TRAIN-POS-PLATE",recipe_id=recipe.id,location_id=v["store"],is_active=True))


def after_prepare_food(db,lesson,v):
    if lesson.id=="reverse-duplicate-staff-meal":
        from app.services.staff_meals import post_staff_meal
        from app.schemas.staff_meals import StaffMealCreate
        post_staff_meal(db,payload=StaffMealCreate(meal_name="TRAIN-DUPLICATE",servings=5,location_id=v["store"],lines=[{"item_id":v["chicken"],"quantity":v["quantity"]}]),actor_id=v["colleague"])


def verify_food(db,lesson,v,actions):
    id=lesson.id
    recipe=db.get(Recipe,v["recipe"])
    docs=list(db.scalars(select(StockDocument).where(StockDocument.posted_by_user_id==v["actor"])))
    balance=db.scalar(select(StockBalance.quantity).where(StockBalance.item_id==v["chicken"],StockBalance.location_id==v["store"]))
    untouched=balance==v["base"] and not docs
    def audited(action,entity):return bool(db.scalar(select(AuditLog.id).where(AuditLog.actor_user_id==v["actor"],AuditLog.action==action,AuditLog.entity_id==entity)))
    ok=False
    if id=="create-governed-recipe":
        row=db.scalar(select(Recipe).where(Recipe.code=="TRAIN-TEST-RECIPE"))
        ok=bool(row and row.created_by_user_id==v["actor"] and row.status=="draft" and not row.approved_by_user_id and row.name=="Training chicken portion" and row.output_item_id==v["alfredo"] and row.yield_quantity==1 and row.notes==v["reference"] and len(row.lines)==1 and row.lines[0].ingredient_item_id==v["chicken"] and row.lines[0].quantity==Decimal("0.25") and row.lines[0].waste_factor==Decimal("0.1") and not row.lines[0].optional)
    elif id=="approve-colleague-recipe":ok=recipe.status=="approved" and recipe.approved_by_user_id==v["actor"] and recipe.created_by_user_id!=v["actor"] and audited("recipe.approved",recipe.id)
    elif id=="recipe-self-approval":ok=recipe.status=="draft" and not recipe.approved_by_user_id and any(a.get("path")=="/api/v1/recipes/training-recipe/approve" and a.get("status")==409 for a in actions)
    elif id=="retire-obsolete-recipe":ok=recipe.status=="retired" and len(recipe.lines)==1 and recipe.lines[0].quantity==Decimal("0.25") and audited("recipe.retired",recipe.id)
    elif id=="plan-production-batch":
        rows=list(db.scalars(select(ProductionBatch).where(ProductionBatch.notes==v["reference"])))
        ok=len(rows)==1 and rows[0].created_by_user_id==v["actor"] and rows[0].recipe_id==recipe.id and rows[0].location_id==v["store"] and rows[0].planned_quantity==v["quantity"] and rows[0].status=="planned" and rows[0].actual_quantity is None and rows[0].stock_document_id is None
    elif id=="reverse-duplicate-staff-meal":
        row=db.scalar(select(StaffMeal).where(StaffMeal.meal_name=="TRAIN-DUPLICATE"))
        original=db.get(StockDocument,row.posted_document_id)
        ok=row.status=="reversed" and row.reversed_by_user_id==v["actor"] and len(docs)==1 and docs[0].id==row.reversal_document_id and docs[0].document_type=="staff_meal_reversal" and original.reversed_document_id==docs[0].id and original.status=="reversed" and len(docs[0].movements)==1 and docs[0].movements[0].quantity==v["quantity"] and docs[0].movements[0].unit_cost==200 and balance==v["base"]
        untouched=True  # The linked reversal is the one permitted stock change.
    elif id=="create-menu-with-modifier":
        row=db.scalar(select(MenuItem).where(MenuItem.name=="Training garden plate"))
        groups=json.loads(row.modifier_groups_json or "[]") if row else []
        ok=bool(row and row.display_name==row.name and row.category=="Training meals" and row.prep_station=="kitchen" and row.is_active and row.pos_visible and len(row.variants)==1 and row.variants[0].name=="Regular" and row.variants[0].price==250 and row.variants[0].recipe_id is None and len(groups)==1 and groups[0]["label"]=="Sauce" and groups[0]["mode"]=="single" and len(groups[0]["options"])==1 and groups[0]["options"][0]["label"]=="Extra sauce" and groups[0]["options"][0]["price_delta"]==20)
    elif id in {"map-pos-product","disable-stale-pos-mapping"}:
        rows=list(db.scalars(select(PosProductMapping)))
        ok=len(rows)==1 and rows[0].pos_system=="hidden-oasis-pos" and rows[0].external_product_id=="TRAIN-POS-PLATE" and rows[0].recipe_id==recipe.id and rows[0].location_id==v["store"] and rows[0].is_active==(id=="map-pos-product") and audited("pos.mapping_created" if id=="map-pos-product" else "pos.mapping_deactivated",rows[0].id)
    passed=bool(ok and untouched)
    return passed,{"workflow":lesson.workflow,"passed":passed,"stock_integrity":bool(untouched),"correction":lesson.situation.format(**v)+" Check the saved status, units and links. Reset this practice if an unintended formula or stock change was posted."}
