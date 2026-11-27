"""Deterministic catalogue fixtures and read-only database outcome checks."""
from decimal import Decimal
from sqlalchemy import delete, select
from app.models.inventory import Item, StockBalance, StockDocument, UnitOfMeasure
from app.models.inventory_operations import ItemBarcode, ItemLocationSetting, UnitConversion
from app.models.procurement import PurchaseOrder, Supplier, SupplierItem
from app.models.audit_log import AuditLog
from app.services.classification_defaults import DEFAULT_DIMENSIONS


def catalogue_values(mode):
    dimensions={row["code"]:row["id"] for row in DEFAULT_DIMENSIONS}
    reverse=mode=="independent"
    return {"fnb":dimensions["fnb"],"ingredient":dimensions["ingredient"],
        "litre":"training-litre","ml":"training-ml","retired":"training-retired",
        "unused_supplier":"training-unused-supplier","terms":{"guided":14,"assisted":7,"independent":21}[mode],
        "barcode":"TRAIN-SCAN-"+mode.upper(),
        "conversion_from":"training-gram" if reverse else "training-kg",
        "conversion_to":"training-kg" if reverse else "training-gram",
        "conversion_from_name":"TRAIN-G" if reverse else "TRAIN-KG",
        "conversion_to_name":"TRAIN-KG" if reverse else "TRAIN-G",
        "conversion_multiplier":"0.001" if reverse else "1000",
        "conversion_description":"1 gram = 0.001 kilogram" if reverse else "1 kilogram = 1,000 grams"}


def prepare_catalogue(db,lesson,v):
    if not lesson.workflow.startswith("catalogue_"): return
    db.add_all([
        UnitOfMeasure(id=v["litre"],code="TRAIN-L",name="Litre",precision=4),
        UnitOfMeasure(id=v["ml"],code="TRAIN-ML",name="Millilitre",precision=4),
        Item(id=v["retired"],sku="TRAIN-RETIRED",name="Training retired supply",category_id=v["category"],base_unit_id=v["portion"],standard_cost=25,is_active=lesson.id!="reactivate-item"),
        Supplier(id=v["unused_supplier"],code="TRAIN-OLD-SUPPLIER",name="Training former supplier",payment_terms_days=7,is_active=lesson.id!="reactivate-supplier"),
    ])
    if lesson.id=="define-unit-conversion":
        db.execute(delete(UnitConversion).where(UnitConversion.item_id==v["chicken"]))
    if lesson.id=="remove-item-barcode":
        db.add(ItemBarcode(id="training-old-barcode",item_id=v["chicken"],barcode="TRAIN-OLD-SCAN",barcode_type="INTERNAL",is_primary=False))

    if lesson.id=="edit-item-barcode":
        db.add(ItemBarcode(id="training-edit-barcode",item_id=v["chicken"],barcode="TRAIN-OLD-SCAN",barcode_type="INTERNAL",is_primary=False))
    if lesson.id=="edit-unit-conversion":
        db.execute(delete(UnitConversion).where(UnitConversion.item_id==v["chicken"]))
        db.add(UnitConversion(id="training-edit-conversion",item_id=v["chicken"],from_unit_id=v["conversion_from"],to_unit_id=v["conversion_to"],multiplier=800))
    if lesson.id=="edit-location-policy":
        db.add(ItemLocationSetting(id="training-edit-policy",item_id=v["chicken"],location_id=v["store"],minimum_stock=3,reorder_quantity=5,maximum_stock=10,cycle_count_days=30))
    if lesson.id=="edit-supplier-item-terms":
        row=db.scalar(select(SupplierItem).where(SupplierItem.item_id==v["chicken"],SupplierItem.supplier_id==v["supplier"]))
        row.id="training-edit-supplier"


def verify_catalogue(db,lesson,v,actions):
    id=lesson.id
    chicken=db.get(Item,v["chicken"])
    stock=db.scalar(select(StockBalance).where(StockBalance.item_id==v["chicken"],StockBalance.location_id==v["store"]))
    untouched=Decimal(stock.quantity)==Decimal(v["base"]) and chicken.name=="Chicken (kg)" and chicken.category_id==v["category"] and not db.scalar(select(StockDocument.id).where(StockDocument.posted_by_user_id==v["actor"]))
    evidence={"workflow":lesson.workflow,"stock_unchanged":bool(untouched)}
    ok=False
    if id=="create-item":
        row=db.scalar(select(Item).where(Item.sku=="TRAIN-OIL"))
        ok=bool(row and row.name=="Training cooking oil" and row.base_unit_id==v["litre"] and row.category_id==v["category"] and row.primary_workspace_id==v["fnb"] and row.item_type_id==v["ingredient"] and row.default_location_id==v["store"] and row.minimum_stock==v["quantity"] and row.standard_cost==150 and row.track_stock and not row.allow_negative_stock and row.is_active)
        if row:
            ok=ok and not db.scalar(select(StockBalance.id).where(StockBalance.item_id==row.id))
            evidence["item_id"]=row.id
    elif id=="edit-item-reorder":
        ok=chicken.minimum_stock==v["quantity"] and chicken.standard_cost==200 and chicken.base_unit_id==v["kg"] and chicken.track_stock and not chicken.allow_negative_stock and chicken.is_active
    elif id=="add-item-barcode":
        rows=db.scalars(select(ItemBarcode).where(ItemBarcode.item_id==v["chicken"])).all()
        ok=len(rows)==1 and rows[0].barcode==v["barcode"] and rows[0].barcode_type=="INTERNAL"
    elif id=="remove-item-barcode":
        ok=db.get(ItemBarcode,"training-old-barcode") is None and bool(db.scalar(select(AuditLog.id).where(AuditLog.actor_user_id==v["actor"],AuditLog.action=="item.barcode_removed")))
    elif id=="define-unit-conversion":
        rows=db.scalars(select(UnitConversion).where(UnitConversion.item_id==v["chicken"])).all()
        ok=len(rows)==1 and rows[0].from_unit_id==v["conversion_from"] and rows[0].to_unit_id==v["conversion_to"] and rows[0].multiplier==Decimal(v["conversion_multiplier"]) and rows[0].is_active
    elif id=="edit-item-barcode":
        row=db.get(ItemBarcode,"training-edit-barcode")
        ok=bool(row and row.item_id==v["chicken"] and row.barcode==v["barcode"] and row.barcode_type=="INTERNAL" and not row.is_primary)
    elif id=="edit-unit-conversion":
        row=db.get(UnitConversion,"training-edit-conversion")
        ok=bool(row and row.item_id==v["chicken"] and row.from_unit_id==v["conversion_from"] and row.to_unit_id==v["conversion_to"] and row.multiplier==Decimal(v["conversion_multiplier"]) and row.is_active)
    elif id=="edit-location-policy":
        row=db.get(ItemLocationSetting,"training-edit-policy")
        ok=bool(row and row.item_id==v["chicken"] and row.location_id==v["store"] and row.minimum_stock==v["quantity"] and row.reorder_quantity==20 and row.maximum_stock==60 and row.cycle_count_days==7 and row.preferred_supplier_id is None and row.is_active)
    elif id=="edit-supplier-item-terms":
        row=db.get(SupplierItem,"training-edit-supplier");po=db.get(PurchaseOrder,v["po"])
        ok=bool(row and row.item_id==v["chicken"] and row.supplier_id==v["supplier"] and row.supplier_sku=="TRAIN-CHICKEN" and row.last_price==210 and row.lead_time_days==4 and row.minimum_order_quantity==2 and row.is_preferred and po.status=="approved" and po.lines[0].received_quantity==0)
    elif id=="set-location-policy":
        rows=db.scalars(select(ItemLocationSetting).where(ItemLocationSetting.item_id==v["chicken"])).all()
        ok=len(rows)==1 and rows[0].location_id==v["store"] and rows[0].minimum_stock==v["quantity"] and rows[0].reorder_quantity==20 and rows[0].maximum_stock==60 and rows[0].cycle_count_days==7 and rows[0].preferred_supplier_id is None and rows[0].is_active
    elif id in {"deactivate-empty-item","reactivate-item"}:
        row=db.get(Item,v["retired"])
        ok=row.is_active==(id=="reactivate-item") and bool(db.scalar(select(AuditLog.id).where(AuditLog.actor_user_id==v["actor"],AuditLog.entity_id==row.id,AuditLog.action=="item.updated")))
    elif id in {"stock-blocks-deactivation","catalogue-scope-required","open-orders-block-deactivation"}:
        status=403 if id=="catalogue-scope-required" else 409
        path="/api/v1/suppliers/training-supplier" if id=="open-orders-block-deactivation" else "/api/v1/items/training-chicken"
        refused=any(event.get("path")==path and event.get("status")==status for event in actions)
        po=db.get(PurchaseOrder,v["po"])
        ok=refused and chicken.is_active and chicken.minimum_stock==40 and db.get(Supplier,v["supplier"]).is_active and po.status=="approved" and po.lines[0].received_quantity==0
        evidence.update(expected_refusal_observed=refused,expected_status=status)
    elif id=="create-supplier":
        row=db.scalar(select(Supplier).where(Supplier.code=="TRAIN-GARDEN"))
        ok=bool(row and row.name=="Training Garden Supplies" and row.contact_name=="Training contact" and row.email=="garden@example.com" and row.payment_terms_days==v["terms"] and row.is_active)
    elif id=="edit-supplier-terms":
        row=db.get(Supplier,v["supplier"])
        ok=row.code=="TRAIN-VALLEY" and row.name=="Training Valley Foods" and row.contact_name=="Training purchasing contact" and row.payment_terms_days==v["terms"] and row.is_active
    elif id=="link-supplier-item":
        rows=db.scalars(select(SupplierItem).where(SupplierItem.item_id==v["amenities"])).all()
        ok=len(rows)==1 and rows[0].supplier_id==v["supplier"] and rows[0].supplier_sku=="TRAIN-KIT" and rows[0].last_price==50 and rows[0].lead_time_days==3 and rows[0].minimum_order_quantity==2 and rows[0].is_preferred
    elif id in {"deactivate-unused-supplier","reactivate-supplier"}:
        row=db.get(Supplier,v["unused_supplier"])
        ok=row.is_active==(id=="reactivate-supplier") and bool(db.scalar(select(AuditLog.id).where(AuditLog.actor_user_id==v["actor"],AuditLog.entity_id==row.id,AuditLog.action=="supplier.updated")))
    passed=bool(ok and untouched)
    evidence.update(passed=passed,correction=lesson.situation.format(**v)+" Keep stock and existing transaction history unchanged. Reset this practice if you saved an unintended master-data change.")
    return passed,evidence
