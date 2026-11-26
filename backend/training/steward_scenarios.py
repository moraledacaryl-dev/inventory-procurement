"""Real maintenance state and narrowly captured read-only calculation inputs."""
import json
from decimal import Decimal
from sqlalchemy import select
from app.models import Item, Location, Supplier, SupplierItem, PurchaseOrder, StockBalance, StockDocument, AuditLog, OperationalDimension
from app.models.production import PosProductMapping, Recipe
from app.models.operations import IntegrationEvent
from app.models.menu import MenuItem, MenuVariant
from app.models.pos_rules import PosPricingRule, PosModifierTemplate
from app.services.classification_defaults import DEFAULT_DIMENSIONS


def steward_values(mode,quantity):
    return {'margin_price':{'guided':250,'assisted':275,'independent':300}[mode],'correction_delta':str(-quantity)}


def prepare_steward(db,lesson,v):
    if not lesson.workflow.startswith('steward_'):return
    if lesson.id in {'assign-menu-selling-controls','activate-verified-pos-mapping','retry-eligible-inbound-event'}:
        dimensions={row['code']:row['id'] for row in DEFAULT_DIMENSIONS}
        for item_id,type_id in ((v['chicken'],v['ingredient']),(v['alfredo'],dimensions['finished-fnb-product'])):
            # Use the seeded source classification, retaining its derived class.
            type=db.get(OperationalDimension,type_id)
            row=db.get(Item,item_id);row.primary_workspace_id=v['fnb'];row.item_type_id=type.id;row.record_class_id=type.parent_id
    if lesson.id=='assign-menu-selling-controls':
        menu=MenuItem(id='training-review-menu',name='Training Chicken Alfredo',display_name='Training Chicken Alfredo',category='Training meals',prep_station='kitchen',pricing_tags_json='[]',is_active=True,pos_visible=True)
        menu.variants=[MenuVariant(id='training-review-variant',name='Regular',sku='TRAIN-MENU-REVIEW',barcode='9000000000099',price=250,recipe_id=v['recipe'],inventory_item_id=v['alfredo'])]
        coffee=MenuItem(id='training-qualifying-drink',name='Training iced coffee',display_name='Training iced coffee',category='Training drinks',prep_station='bar',pricing_tags_json='["train-drink"]',is_active=True,pos_visible=True)
        coffee.variants=[MenuVariant(name='Regular',sku='TRAIN-COFFEE',barcode='9000000000098',price=120)]
        db.add_all([menu,coffee,PosPricingRule(id='training-menu-rule',name='Training drink and main',qualifier_tag='train-drink',target_tag='train-main',priority=100,is_active=True),PosModifierTemplate(id='training-menu-extras',name='Training plate extras',is_active=True,config_json=json.dumps({'id':'training-plate-extras','label':'Choose plate extras','mode':'multi','min_selections':0,'options':[{'id':'extra-cheese','label':'Extra cheese','price_delta':30,'is_active':True},{'id':'extra-sauce','label':'Extra sauce','price_delta':20,'is_active':True}]}))])
    if lesson.id in {'activate-verified-pos-mapping','retry-eligible-inbound-event'}:
        db.add(PosProductMapping(id='training-pos-map',pos_system='hidden-oasis-pos',external_product_id='TRAIN-POS-PLATE',recipe_id=v['recipe'],location_id=v['store'],is_active=lesson.id=='retry-eligible-inbound-event'))
    if lesson.id=='retry-eligible-inbound-event':
        db.add(IntegrationEvent(id='training-pos-retry',direction='inbound',source_system='hidden-oasis-pos',destination_system='inventory',event_type='pos.sale_completed',aggregate_type='pos_sale',aggregate_id='TRAIN-POS-RETRY',idempotency_key='training-pos-retry-original',status='failed',attempts=3,last_error='Product mapping was missing; steward has verified the correction',payload={'sale_id':'TRAIN-POS-RETRY','external_product_id':'TRAIN-POS-PLATE','quantity':1}))


def verify_steward(db,lesson,v,actions):
    id=lesson.id
    docs=list(db.scalars(select(StockDocument).where(StockDocument.posted_by_user_id==v['actor'])))
    def balance(item):return db.scalar(select(StockBalance.quantity).where(StockBalance.item_id==item,StockBalance.location_id==v['store'])) or Decimal(0)
    unchanged=not docs and balance(v['chicken'])==v['base'] and balance(v['amenities'])==v['base'] and balance(v['alfredo'])==0
    def audit(action,entity=None):
        stmt=select(AuditLog).where(AuditLog.actor_user_id==v['actor'],AuditLog.action==action)
        if entity:stmt=stmt.where(AuditLog.entity_id==entity)
        return db.scalar(stmt)
    ok=False;evidence={'workflow':lesson.workflow}
    if id=='unlink-obsolete-supplier-item':
        row=audit('supplier.item_unlinked');po=db.get(PurchaseOrder,v['po'])
        ok=not db.scalar(select(SupplierItem.id).where(SupplierItem.item_id==v['chicken'],SupplierItem.supplier_id==v['supplier'])) and row and row.details.get('item_id')==v['chicken'] and row.details.get('supplier_id')==v['supplier'] and db.get(Supplier,v['supplier']).is_active and po.supplier_id==v['supplier'] and po.status=='approved' and len(po.lines)==1 and po.lines[0].ordered_quantity==10 and len(list(db.scalars(select(Supplier))))==1 and len(list(db.scalars(select(PurchaseOrder))))==1
    elif id=='create-authorized-storage-location':
        row=db.scalar(select(Location).where(Location.code=='TRAIN-CAFE-STORE'))
        ok=row and row.name=='Training café supplies' and row.location_type=='storeroom' and row.parent_id==v['store'] and row.is_active and not db.scalar(select(StockBalance.id).where(StockBalance.location_id==row.id)) and len(list(db.scalars(select(Location))))==4 and any(action.get('path')=='/api/v1/locations' and action.get('method')=='POST' and action.get('status')==201 for action in actions)
    elif id=='correct-storage-location-label':
        row=db.get(Location,v['kitchen'])
        ok=row.code=='TRAIN-KITCHEN' and row.name=='Training kitchen dry store' and row.location_type=='storeroom' and row.parent_id is None and row.is_active and audit('location.updated',row.id)
    elif id=='stock-screen-signed-correction':
        unchanged=balance(v['amenities'])==v['base'] and balance(v['alfredo'])==0
        ok=len(docs)==1 and docs[0].document_type=='adjustment' and docs[0].reference==v['reference'] and len(docs[0].movements)==1 and docs[0].movements[0].item_id==v['chicken'] and docs[0].movements[0].location_id==v['store'] and docs[0].movements[0].quantity==-v['quantity'] and docs[0].movements[0].unit_cost==200 and docs[0].movements[0].reason=='Verified opening correction' and balance(v['chicken'])==v['base']-v['quantity']
    elif id=='assign-menu-selling-controls':
        row=db.get(MenuItem,'training-review-menu');variant=db.get(MenuVariant,'training-review-variant');coffee=db.get(MenuItem,'training-qualifying-drink')
        prices=json.loads(variant.conditional_prices_json or '[]')
        ok=row.name==row.display_name=='Training Chicken Alfredo' and row.is_active and row.pos_visible and row.prep_station=='kitchen' and json.loads(row.pricing_tags_json or '[]')==['train-main'] and json.loads(row.modifier_template_ids_json or '[]')==['training-menu-extras'] and variant.sku=='TRAIN-MENU-REVIEW' and variant.price==250 and variant.recipe_id==v['recipe'] and variant.inventory_item_id==v['alfredo'] and variant.is_active and len(prices)==1 and prices[0]['rule_id']=='training-menu-rule' and Decimal(str(prices[0]['price']))==220 and json.loads(coffee.pricing_tags_json or '[]')==['train-drink'] and len(row.variants)==1 and len(list(db.scalars(select(MenuItem))))==2 and audit('menu.item_updated',row.id)
    elif id=='retry-eligible-inbound-event':
        row=db.get(IntegrationEvent,'training-pos-retry');mapping=db.get(PosProductMapping,'training-pos-map')
        ok=mapping.is_active and mapping.recipe_id==v['recipe'] and mapping.location_id==v['store'] and db.get(Recipe,v['recipe']).status=='approved' and row.status=='pending' and row.attempts==0 and row.last_error is None and row.locked_at is None and row.locked_by is None and row.idempotency_key=='training-pos-retry-original' and row.aggregate_id=='TRAIN-POS-RETRY' and row.payload=={'sale_id':'TRAIN-POS-RETRY','external_product_id':'TRAIN-POS-PLATE','quantity':1} and audit('integration.manual_retry',row.id)
    elif id=='activate-verified-pos-mapping':
        row=db.get(PosProductMapping,'training-pos-map')
        ok=row.is_active and row.external_product_id=='TRAIN-POS-PLATE' and row.recipe_id==v['recipe'] and row.location_id==v['store'] and db.get(Recipe,v['recipe']).status=='approved' and audit('pos.mapping_activated',row.id)
    elif id=='calculate-food-margin':
        calls=[action for action in actions if action.get('path')=='/api/v1/recipes/training-recipe/margin-scenario' and action.get('method')=='POST']
        latest=calls[-1] if calls else {}
        calculation=latest.get('calculation') or {}
        from app.api.routes.recipe_costing import load_recipe,costing_payload
        cost=Decimal(costing_payload(db,load_recipe(db,v['recipe']),v['store'])['summary']['cost_per_output_unit'])
        try:price=Decimal(str(calculation.get('selling_price',0)))
        except Exception:price=Decimal(0)
        ok=latest.get('status')==200 and calculation.get('location_id')==v['store'] and price==v['margin_price'] and cost==50  and not db.scalar(select(AuditLog.id).where(AuditLog.actor_user_id==v['actor']))
        if ok:evidence.update(recipe_cost=str(cost),selling_price=str(price),gross_profit_per_unit=str(price-cost),food_cost_percent=str((cost/price*100).quantize(Decimal('0.01'))),gross_margin_percent=str(((price-cost)/price*100).quantize(Decimal('0.01'))))
    passed=bool(ok and unchanged)
    evidence.update(passed=passed,stock_integrity=bool(unchanged),correction=lesson.situation.format(**v)+' Check the exact original record, approved values and unchanged unrelated stock. Reset practice if an unintended stock or configuration change was made.')
    return passed,evidence
