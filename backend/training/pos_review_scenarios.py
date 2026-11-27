"""Use typed source POS lifecycle handlers with no outbound integration transport."""
from decimal import Decimal
from sqlalchemy import select
from fastapi import HTTPException
from app.models import Item,UnitOfMeasure,Recipe,RecipeLine,PosProductMapping,PosSaleEvent,StockBalance,StockDocument,User,AuditLog,IntegrationEvent
from app.services.inventory import post_document
from app.services.controls import add_audit
from app.schemas.production import PosSaleEventIn

INGREDIENTS=(("spaghetti","kg","0.1",100,10),("chicken","kg","0.25",200,None),("cream","litre","0.05",300,5),("sauce","litre","0.05",200,5))

def after_prepare_pos_reviews(db,lesson,v):
    if lesson.workflow!="read_pos":return
    db.add(UnitOfMeasure(id="training-litre",code="TRAIN-L",name="Litre",precision=4));db.flush()
    recipe=db.get(Recipe,v["recipe"])
    recipe.lines.clear();db.flush()
    for key,unit,quantity,cost,opening in INGREDIENTS:
        if key!="chicken":
            db.add(Item(id="training-"+key,sku="TRAIN-"+key.upper(),name="Training "+key,category_id=v["category"],base_unit_id="training-"+unit,standard_cost=cost));db.flush()
            post_document(db,kind="receipt",actor_id=v["colleague"],entries=[{"item_id":"training-"+key,"location_id":v["store"],"quantity":opening,"unit_cost":cost}],reference="Synthetic POS ingredients")
        recipe.lines.append(RecipeLine(ingredient_item_id="training-"+key,quantity=Decimal(quantity),waste_factor=0))
    db.add(PosProductMapping(id="training-pos-map",pos_system="hidden-oasis-pos",external_product_id="TRAIN-POS-ALFREDO",recipe_id=recipe.id,location_id=v["store"],is_active=True));db.commit()
    from app.api.routes.production import process_pos_event
    colleague=db.get(User,v["colleague"])
    def event(id,type,product="TRAIN-POS-ALFREDO",quantity=None,disposition=None):
        return PosSaleEventIn(external_event_id=id,external_sale_id="TRAIN-SALE",event_type=type,lines=[{"external_product_id":product,"quantity":v["quantity"] if quantity is None else quantity,"inventory_disposition":disposition}])
    if lesson.id=="inspect-unmapped-pos-refusal":
        payload=event("TRAIN-SALE-UNMAPPED","sale_completed","TRAIN-UNMAPPED")
        try:process_pos_event(payload,db,colleague)
        except HTTPException as exc:
            db.rollback()
            if exc.status_code!=422 or "not mapped" not in str(exc.detail):raise
            # This is explicitly a training diagnostic of the real refused call,
            # not a fabricated PosSaleEvent or successful stock posting.
            add_audit(db,actor_user_id=colleague.id,action="training.pos_intake_refused",entity_type="training_diagnostic",entity_id=payload.external_event_id,details={"status":exc.status_code,"detail":str(exc.detail),"sale_id":payload.external_sale_id,"product":"TRAIN-UNMAPPED"});db.commit()
        else:raise RuntimeError("Expected the real source unmapped-product refusal")
        return
    original=process_pos_event(event("TRAIN-SALE-COMPLETED","sale_completed"),db,colleague)
    if lesson.id=="inspect-pos-duplicate-delivery":
        again=process_pos_event(event("TRAIN-SALE-COMPLETED","sale_completed"),db,colleague)
        if again.id!=original.id or again.stock_document_id!=original.stock_document_id:raise RuntimeError("Source POS retry lost idempotency")
    elif lesson.id=="inspect-cooked-sale-return":
        process_pos_event(event("TRAIN-SALE-REFUNDED","sale_refunded"),db,colleague)
        process_pos_event(event("TRAIN-SALE-RETURNED","sale_returned",quantity=1,disposition="waste"),db,colleague)
    elif lesson.id=="inspect-unused-sale-void":process_pos_event(event("TRAIN-SALE-VOIDED","sale_voided"),db,colleague)


def pos_question(lesson,mode,v):
    answers={"sale-consumption":str(-85*v["quantity"]),"inspect-pos-duplicate-delivery":"1","inspect-unmapped-pos-refusal":"0","inspect-cooked-sale-return":"3","inspect-unused-sale-void":str(-85*v["quantity"])}
    question="In the opened stock document, what signed Net value is shown in pesos?" if lesson.id in {"sale-consumption","inspect-unused-sale-void"} else "How many Failed events are shown?" if lesson.id=="inspect-unmapped-pos-refusal" else "How many Processed events are shown?"
    return question,answers[lesson.id],lesson.route


def pos_endpoint(lesson,db=None):
    if db is not None and lesson.id in {"sale-consumption","inspect-unused-sale-void"}:
        identity="TRAIN-SALE-COMPLETED"
        row=db.scalar(select(PosSaleEvent).where(PosSaleEvent.external_event_id==identity))
        return f"/api/v1/stock/documents/{row.stock_document_id}"
    return "/api/v1/integrations/pos/workspace"


def verify_pos_review(db,lesson,v):
    events=list(db.scalars(select(PosSaleEvent)));docs=list(db.scalars(select(StockDocument).where(StockDocument.document_type.in_(["pos_sale_consumption","pos_sale_reversal"]))))
    original=next((row for row in events if row.external_event_id=="TRAIN-SALE-COMPLETED"),None)
    unused=lesson.id=="inspect-unused-sale-void";unmapped=lesson.id=="inspect-unmapped-pos-refusal";returned=lesson.id=="inspect-cooked-sale-return"
    expected_events=0 if unmapped else 3 if returned else 2 if unused else 1
    ok=len(events)==expected_events and len(docs)==(0 if unmapped else 1) and all(row.status=="processed" for row in events)
    for key,unit,quantity,cost,opening in INGREDIENTS:
        balance=db.scalar(select(StockBalance).where(StockBalance.item_id=="training-"+key,StockBalance.location_id==v["store"]))
        expected=Decimal(v["base"] if key=="chicken" else opening)-(0 if unmapped else Decimal(quantity)*v["quantity"])
        ok=ok and balance is not None and balance.quantity==expected
    if original:
        source=db.get(StockDocument,original.stock_document_id)
        expected_lines={"training-"+key:(-Decimal(quantity)*v["quantity"],Decimal(cost)) for key,unit,quantity,cost,opening in INGREDIENTS}
        ok=ok and source.document_type=="pos_sale_consumption" and len(source.movements)==4 and {row.item_id:(row.quantity,row.unit_cost) for row in source.movements}==expected_lines and sum(row.quantity*row.unit_cost for row in source.movements)==-85*v["quantity"]
        mapping=db.get(PosProductMapping,"training-pos-map")
        ok=ok and mapping is not None and mapping.is_active and mapping.recipe_id==v["recipe"] and mapping.location_id==v["store"] and db.get(Recipe,mapping.recipe_id).status=="approved"
        if unused or returned:
            follows=[row for row in events if row.id!=original.id]
            ok=ok and all(row.reversal_of_event_id==original.id and row.stock_document_id is None for row in follows)
            if unused:ok=ok and follows[0].event_type=="sale_voided"
            if returned:
                waste=next((row for row in follows if row.event_type=="sale_returned"),None)
                refund=next((row for row in follows if row.event_type=="sale_refunded"),None)
                ok=ok and refund is not None and waste is not None and waste.payload["lines"][0]["inventory_disposition"]=="waste" and Decimal(waste.payload["lines"][0]["quantity"])==1
    if unmapped:
        audit=db.scalar(select(AuditLog).where(AuditLog.action=="training.pos_intake_refused"))
        ok=ok and audit is not None and audit.details.get("status")==422
    pending=list(db.scalars(select(IntegrationEvent).where(IntegrationEvent.event_type.in_(["inventory.pos_sale_consumed","inventory.pos_sale_reversed"]))))
    ok=ok and len(pending)==(0 if unmapped else 1) and all(row.status=="pending" for row in pending)
    return bool(ok),{"source_pos_evidence_intact":bool(ok),"pos_event_count":len(events),"pos_document_count":len(docs),"accounting_transport_disabled":all(row.status=="pending" for row in pending),"correction":"Inspect the original local POS evidence and preserve its stock, mapping and event identities. Reset if an unintended business change was posted."}
