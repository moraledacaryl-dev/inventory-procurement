"""Source-backed report evidence prepared by explicitly fictional colleagues."""
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select
from app.models import StockDocument, StockMovement, StockBalance, CountSession, ProductionBatch, User, GoodsReceipt, BackupRecord
from app.services.inventory import post_document


def after_prepare_reports(db,lesson,v):
    if lesson.workflow!="read_report":return
    colleague=db.get(User,v["colleague"])
    if lesson.id=="interpret-period-issues":
        # Only these historical synthetic records are dated; learners cannot backdate.
        for doc in db.scalars(select(StockDocument)):
            doc.posted_at=datetime(2026,11,17,tzinfo=timezone.utc)
            for movement in doc.movements:movement.created_at=doc.posted_at
        db.commit()
        for quantity,day,ref in [(2,18,"TRAIN-EARLIER-ISSUE"),(v["quantity"],25,"TRAIN-PERIOD-ISSUE")]:
            doc=post_document(db,kind="issue",actor_id=colleague.id,entries=[{"item_id":v["chicken"],"location_id":v["store"],"quantity":-quantity}],reference=ref)
            doc.posted_at=datetime(2026,11,day,12,tzinfo=timezone.utc)
            for movement in doc.movements:movement.created_at=doc.posted_at
            db.commit()
    elif lesson.id=="interpret-waste-value":
        from app.api.routes.controlled_inventory import WasteCreate,create_waste_event
        create_waste_event(WasteCreate(item_id=v["chicken"],location_id=v["store"],quantity=v["quantity"],reason_code="spoilage",reference="TRAIN-WASTE"),db,colleague)
    elif lesson.id=="interpret-posted-count":
        from app.api.routes.guided_counts import save_count_entries,CountEntriesUpdate,submit_count,approve_guided_count
        row=db.get(CountSession,v["count"]);row.created_by_user_id=colleague.id;db.commit()
        save_count_entries(row.id,CountEntriesUpdate(lines=[{"item_id":v["chicken"],"counted_quantity":v["quantity"]}]),db,colleague)
        submit_count(row.id,db,colleague)
        approve_guided_count(row.id,db,db.get(User,v["reviewer"]))
    elif lesson.id=="interpret-supplier-acceptance":
        from app.api.routes.receiving_workspace import post_controlled_receipt,ControlledReceiptCreate
        post_controlled_receipt(v["po"],ControlledReceiptCreate(delivery_reference="TRAIN-QUALITY-DR",lines=[{"purchase_order_line_id":v["po-line"],"received_quantity":v["quantity"],"accepted_quantity":v["quantity"]-2,"rejected_quantity":2,"discrepancy_reason":"Spoilage found during inspection"}]),db,colleague)
    elif lesson.id=="interpret-actual-yield-cost":
        from app.api.routes.production_execution import start_batch,execute_batch,ExecuteProduction
        row=db.get(ProductionBatch,v["batch"]);row.created_by_user_id=colleague.id;db.commit()
        start_batch(row.id,db,colleague)
        execute_batch(row.id,ExecuteProduction(actual_output_quantity=v["quantity"],output_waste_quantity=0,materials=[{"item_id":v["chicken"],"actual_quantity":3}]),db,colleague)


def report_question(lesson,mode,v):
    answers={"interpret-stock-valuation":str(v["base"]*250),"interpret-period-issues":str(-v["quantity"]),"interpret-waste-value":str(-v["quantity"]*200),"interpret-posted-count":str(v["quantity"]-v["base"]),"interpret-supplier-acceptance":str(round(100*(v["quantity"]-2)/v["quantity"],2)),"interpret-actual-yield-cost":str(round(600/v["quantity"],2)),"interpret-assurance-evidence":"failed"}
    questions={"interpret-stock-valuation":"What total Inventory value is shown in pesos?","interpret-period-issues":"With the requested ledger filters applied, what signed Net quantity is shown in kg?","interpret-waste-value":"What signed Line value is shown for TRAIN-WASTE in pesos?","interpret-posted-count":"What signed Variance is shown for Chicken on this posted count in kg?","interpret-supplier-acceptance":"What Acceptance % is shown for Training Valley Foods? Enter the number without the percent sign.","interpret-actual-yield-cost":"In the stock document, what Unit cost is shown for TRAIN-ALFREDO in pesos?","interpret-assurance-evidence":"What Status is shown for Completed backup is within freshness limit?"}
    return questions[lesson.id],answers[lesson.id],lesson.route.format(**v)


def report_endpoint(lesson,db=None):
    if lesson.id=="interpret-actual-yield-cost" and db is not None:
        row=db.get(ProductionBatch,"training-batch")
        return f"/api/v1/stock/documents/{row.stock_document_id}"
    return {"interpret-stock-valuation":"/api/v1/reports/valuation","interpret-period-issues":"/api/v1/stock/ledger","interpret-waste-value":"/api/v1/stock/ledger","interpret-posted-count":"/api/v1/counts/training-count/detail","interpret-supplier-acceptance":"/api/v1/supplier-performance","interpret-actual-yield-cost":"/api/v1/production-batches/training-batch/execution-detail","interpret-assurance-evidence":"/api/v1/reports/final-assurance"}[lesson.id]


PERIOD_FILTERS={"item_id":"training-chicken","location_id":"training-store","document_type":"issue","date_from":"2026-11-24T00:00:00Z","date_to":"2026-11-26T23:59:59Z"}

def record_read_allowed(lesson,path,params):
    if lesson.id=="recipe-cost" and path=="/api/v1/recipes/training-recipe/costing-detail":return params.get("location_id")=="training-store"
    return not(lesson.id=="interpret-period-issues" and path=="/api/v1/stock/ledger") or all(params.get(key)==value for key,value in PERIOD_FILTERS.items())


def verify_report(db,lesson,v):
    quantity=db.scalar(select(StockBalance.quantity).where(StockBalance.item_id==v["chicken"],StockBalance.location_id==v["store"]))
    expected=v["base"]
    if lesson.id=="interpret-period-issues":expected-=2+v["quantity"]
    if lesson.id=="interpret-waste-value":expected-=v["quantity"]
    if lesson.id=="interpret-posted-count":expected=v["quantity"]
    if lesson.id=="interpret-supplier-acceptance":expected+=v["quantity"]-2
    if lesson.id=="interpret-actual-yield-cost":expected-=3
    ok=quantity==expected
    if lesson.id=="interpret-stock-valuation":
        balances=list(db.scalars(select(StockBalance)))
        ok=ok and len(balances)==2 and sum(row.quantity*row.average_cost for row in balances)==v["base"]*250
    if lesson.id=="interpret-posted-count":
        count=db.get(CountSession,v["count"])
        ok=ok and count.status=="posted" and count.created_by_user_id!=count.approved_by_user_id and bool(count.posted_document_id)
    if lesson.id=="interpret-actual-yield-cost":
        batch=db.get(ProductionBatch,v["batch"]);document=db.get(StockDocument,batch.stock_document_id)
        output=next((row for row in document.movements if row.item_id==v["alfredo"]),None)
        ok=ok and batch.status=="completed" and batch.actual_quantity==v["quantity"] and output is not None and output.quantity==v["quantity"] and abs(output.unit_cost-Decimal(600)/v["quantity"])<Decimal("0.0001")
    if lesson.id=="interpret-assurance-evidence":ok=ok and db.scalar(select(BackupRecord.id)) is None
    return bool(ok),{"source_evidence_intact":bool(ok),"correction":"Read the requested original evidence and keep its records unchanged. Reset the practice if a business record was changed."}
