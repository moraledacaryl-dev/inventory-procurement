"""Fixtures and read-only checks; operational rules remain in app services."""
import json
from decimal import Decimal
from sqlalchemy import select
from app.models import Item, UnitOfMeasure, UnitConversion, StockBalance, StockDocument, AuditLog, User, ProductionBatch
from app.models.pos_rules import PosPricingRule, PosModifierTemplate
from app.services.inventory import post_document


def extension_values(lesson,mode):
    return {"service_item":"training-service-item"}


def group(cheese=30):
    return {"id":"choose-pizza-extras","label":"Choose pizza extras","mode":"multi","min_selections":0,"options":[{"id":"extra-cheese","label":"Extra cheese","price_delta":cheese,"is_active":True},{"id":"extra-pepperoni","label":"Extra pepperoni","price_delta":40,"is_active":True}]}


def prepare_extensions(db,lesson,v):
    if lesson.id=="deactivate-conditional-price-rule":
        db.add(PosPricingRule(id="training-rule",name="Training weekend promotion",qualifier_tag="train-drink",target_tag="train-pastry",priority=100,is_active=True))
    if lesson.id=="correct-reusable-add-on-price":
        db.add(PosModifierTemplate(id="training-modifier",name="Training pizza extras",config_json=json.dumps(group()),is_active=True))
    if lesson.id in {"issue-cafe-case","issue-bar-volume"}:
        cans=lesson.id=="issue-cafe-case"
        if not cans:db.add(UnitOfMeasure(id="training-ml",code="TRAIN-ML",name="Millilitre",precision=2))
        db.add(UnitOfMeasure(id="training-package",code="TRAIN-CASE" if cans else "TRAIN-BOTTLE",name="Case" if cans else "Bottle",precision=0))
        db.flush()
        db.add(Item(id=v['service_item'],sku="TRAIN-CANS" if cans else "TRAIN-SYRUP",name="Café canned drink" if cans else "Bar syrup (mL)",category_id=v['category'],base_unit_id=v['each'] if cans else "training-ml",standard_cost=25 if cans else Decimal("0.2")))
        db.flush()
        db.add(UnitConversion(item_id=v['service_item'],from_unit_id="training-package",to_unit_id=v['each'] if cans else "training-ml",multiplier=24 if cans else 750))
        post_document(db,kind="receipt",actor_id=v['colleague'],entries=[{"item_id":v['service_item'],"location_id":v['store'],"quantity":Decimal(120 if cans else 1000),"unit_cost":Decimal(25) if cans else Decimal("0.2")}],reference="Synthetic service supplies",commit=False)


def after_prepare_extensions(db,lesson,v):
    if lesson.id=="cancel-started-production":
        from app.api.routes.production_execution import start_batch
        start_batch(v['batch'],db,db.get(User,v['colleague']))


def verify_extensions(db,lesson,v,actions):
    id=lesson.id
    documents=list(db.scalars(select(StockDocument).where(StockDocument.posted_by_user_id==v['actor'])))
    def audited(action,entity):return db.scalar(select(AuditLog.id).where(AuditLog.actor_user_id==v['actor'],AuditLog.action==action,AuditLog.entity_id==entity)) is not None
    def balance(item):return db.scalar(select(StockBalance.quantity).where(StockBalance.item_id==item,StockBalance.location_id==v['store'])) or Decimal(0)
    untouched=not documents and balance(v['chicken'])==v['base'] and balance(v['amenities'])==v['base'] and balance(v['alfredo'])==0
    ok=False
    if id in {"create-conditional-price-rule","deactivate-conditional-price-rule"}:
        create=id.startswith("create")
        rows=list(db.scalars(select(PosPricingRule)))
        ok=len(rows)==1 and rows[0].name==("Training drink and pastry" if create else "Training weekend promotion") and rows[0].qualifier_tag=="train-drink" and rows[0].target_tag=="train-pastry" and rows[0].priority==100 and rows[0].is_active==create and audited("pos.pricing_rule_created" if create else "pos.pricing_rule_updated",rows[0].id)
    elif id in {"create-reusable-add-ons","correct-reusable-add-on-price"}:
        rows=list(db.scalars(select(PosModifierTemplate)))
        create=id.startswith("create")
        config=json.loads(rows[0].config_json) if len(rows)==1 else {}
        expected=group(30 if create else 35)
        ok=len(rows)==1 and rows[0].name=="Training pizza extras" and rows[0].is_active and config==expected and audited("pos.modifier_template_created" if create else "pos.modifier_template_updated",rows[0].id)
    elif id in {"cancel-unstarted-production","cancel-started-production"}:
        row=db.get(ProductionBatch,v['batch'])
        audit=db.scalar(select(AuditLog).where(AuditLog.actor_user_id==v['actor'],AuditLog.action=="production.cancelled",AuditLog.entity_id==row.id))
        details=audit.details if audit else {}
        ok=row.status=="cancelled" and row.stock_document_id is None and row.actual_quantity is None and details.get("reason")=="Service plan changed" and details.get("previous_status")==("in_progress" if id=="cancel-started-production" else "planned") and details.get("material_disposition")==("No materials issued; ingredients remain in storage" if id=="cancel-started-production" else None)
    elif id in {"issue-cafe-case","issue-bar-volume"}:
        cans=id=="issue-cafe-case";cost=Decimal(25) if cans else Decimal("0.2");opening=120 if cans else 1000
        untouched=balance(v['chicken'])==v['base'] and balance(v['amenities'])==v['base'] and balance(v['alfredo'])==0
        ok=len(documents)==1 and documents[0].document_type=="issue" and len(documents[0].movements)==1 and documents[0].movements[0].item_id==v['service_item'] and documents[0].movements[0].location_id==v['store'] and documents[0].movements[0].quantity==-v['quantity'] and documents[0].movements[0].unit_cost==cost and documents[0].movements[0].reason=="Service replenishment" and balance(v['service_item'])==opening-v['quantity']
    passed=bool(ok and untouched)
    return passed,{"workflow":lesson.workflow,"passed":passed,"stock_integrity":bool(untouched),"correction":lesson.situation.format(**v)+" Check the saved configuration, actual unit and stock outcome. Reset this practice if an unintended transaction was posted."}
