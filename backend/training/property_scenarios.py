"""Property and asset fixtures use the same circulation and financial models."""
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select
from app.models.inventory import Item, Location, StockBalance, StockDocument
from app.models.classification import OperationalDimension
from app.models.property import PropertyBalance, PropertyMovement, HotelParProfile, HotelParLine
from app.models.assets import FixedAsset, DepreciationRun, DepreciationLine
from app.models.pass5 import MaintenancePlan, WorkOrder
from app.models.audit_log import AuditLog
from app.models.operations import IntegrationEvent
from app.models.user import User
from app.services.classification_defaults import DEFAULT_DIMENSIONS


def property_values(lesson,mode):
    dims={r["code"]:r["id"] for r in DEFAULT_DIMENSIONS}
    cost={"guided":12000,"assisted":15000,"independent":18000}[mode]
    issue=lesson.id=="issue-clean-linen";laundry=lesson.id=="send-used-linen-to-laundry"
    return {"linen":"training-linen","asset":"training-asset","asset_item":"training-asset-item","asset_class":"training-asset-class","asset_method":"training-asset-method",
        "property_source":"training-kitchen" if laundry else "training-store","property_destination":"training-kitchen" if issue else "training-store",
        "property_from_condition":dims["available" if issue or lesson.id=="configure-room-par" else "in-use" if laundry else "in-laundry"],
        "property_to_condition":dims["in-use" if issue else "in-laundry" if laundry else "available"],"property_reason":dims["issue" if issue else "laundry"],"asset_cost":cost,"asset_monthly":cost//60}


def prepare_property(db,lesson,v):
    if not lesson.workflow.startswith("property_"):return
    dims={r["code"]:r["id"] for r in DEFAULT_DIMENSIONS}
    if lesson.module=="U":
        floor=db.get(Location,v["kitchen"]);floor.code="TRAIN-FLOOR";floor.name="Training room floor"
        db.add(Item(id=v["linen"],sku="TRAIN-TOWEL",name="Training bath towel",category_id=v["category"],base_unit_id="training-each",primary_workspace_id=dims["hotel"],item_type_id=dims["linen"],track_stock=False))
        db.flush()
        db.add(PropertyBalance(item_id=v["linen"],location_id=v["property_source"],condition_id=v["property_from_condition"],quantity=12))
        return
    db.add_all([
        OperationalDimension(id=v["asset_class"],dimension_type="asset_class",code="TRAIN-EQUIPMENT",name="Training equipment",behavior_key="equipment"),
        OperationalDimension(id=v["asset_method"],dimension_type="depreciation_method",code="TRAIN-STRAIGHT",name="Training straight line",behavior_key="straight_line"),
        Item(id=v["asset_item"],sku="TRAIN-FAN",name="Training ventilation fan",category_id=v["category"],base_unit_id="training-each",primary_workspace_id=dims["assets-property"],item_type_id=dims["equipment"],track_stock=False),
    ])
    db.flush()
    db.add(FixedAsset(id=v["asset"],asset_tag="TRAIN-FAN-01",item_id=v["asset_item"],asset_class_id=v["asset_class"],depreciation_method_id=v["asset_method"],location_id=v["store"],acquisition_date=date(2026,11,1),placed_in_service_date=date(2026,11,1),acquisition_cost=v["asset_cost"],useful_life_months=60,status="active",created_by_user_id=v["colleague"]))
    db.flush()
    if lesson.id=="complete-maintenance-work":
        db.add(MaintenancePlan(id="training-plan",code="TRAIN-FAN-CARE",name="Fan safety check",asset_id=v["asset"],interval_days=30,next_due_date=date(2026,11,1)))
        db.flush()
    if lesson.id in {"start-maintenance-work","complete-maintenance-work"}:
        db.add(WorkOrder(id="training-work",work_order_number="TRAIN-WORK",asset_id=v["asset"],plan_id="training-plan" if lesson.id=="complete-maintenance-work" else None,title="Inspect fan guard",status="in_progress" if lesson.id=="complete-maintenance-work" else "open",created_by_user_id=v["colleague"]))


def after_prepare_property(db,lesson,v):
    if lesson.id=="post-reviewed-depreciation":
        from app.api.routes.assets import create_run, RunIn
        create_run(RunIn(period="2026-11"),db,db.get(User,v["colleague"]))


def verify_property(db,lesson,v,actions):
    id=lesson.id
    docs=list(db.scalars(select(StockDocument).where(StockDocument.posted_by_user_id==v["actor"])))
    stock=db.scalar(select(StockBalance.quantity).where(StockBalance.item_id==v["chicken"],StockBalance.location_id==v["store"]))
    untouched=not docs and stock==v["base"]
    def audited(action,entity):return bool(db.scalar(select(AuditLog.id).where(AuditLog.actor_user_id==v["actor"],AuditLog.action==action,AuditLog.entity_id==entity)))
    def event(type,entity):
        row=db.scalar(select(IntegrationEvent).where(IntegrationEvent.event_type==type,IntegrationEvent.aggregate_id==entity))
        return bool(row and row.status=="pending")
    ok=False
    if id in {"issue-clean-linen","send-used-linen-to-laundry","return-clean-linen"}:
        moves=list(db.scalars(select(PropertyMovement)))
        def bucket(location,condition):return db.scalar(select(PropertyBalance.quantity).where(PropertyBalance.item_id==v["linen"],PropertyBalance.location_id==location,PropertyBalance.condition_id==condition)) or Decimal(0)
        ok=len(moves)==1 and moves[0].created_by_user_id==v["actor"] and moves[0].item_id==v["linen"] and moves[0].quantity==v["quantity"] and moves[0].source_location_id==v["property_source"] and moves[0].destination_location_id==v["property_destination"] and moves[0].source_condition_id==v["property_from_condition"] and moves[0].destination_condition_id==v["property_to_condition"] and moves[0].movement_reason_id==v["property_reason"] and moves[0].reference==v["reference"] and bucket(v["property_source"],v["property_from_condition"])==12-v["quantity"] and bucket(v["property_destination"],v["property_to_condition"])==v["quantity"] and sum(db.scalars(select(PropertyBalance.quantity)))==12
    elif id=="configure-room-par":
        rows=list(db.scalars(select(HotelParProfile)));lines=list(db.scalars(select(HotelParLine)))
        ok=len(rows)==1 and rows[0].code=="TRAIN-ROOM-PAR" and rows[0].name=="Training standard room" and rows[0].profile_type=="room_type" and rows[0].location_id==v["kitchen"] and len(lines)==1 and lines[0].profile_id==rows[0].id and lines[0].item_id==v["linen"] and lines[0].par_quantity==v["quantity"] and not db.scalar(select(PropertyMovement.id)) and sum(db.scalars(select(PropertyBalance.quantity)))==12
    elif id=="register-fixed-asset":
        row=db.scalar(select(FixedAsset).where(FixedAsset.asset_tag=="TRAIN-FAN-02"))
        ok=bool(row and row.item_id==v["asset_item"] and row.asset_class_id==v["asset_class"] and row.depreciation_method_id==v["asset_method"] and row.location_id==v["store"] and row.acquisition_cost==6000 and row.capitalized_cost==0 and row.residual_value==0 and row.accumulated_depreciation==0 and row.acquisition_date==date(2026,11,1) and row.placed_in_service_date==date(2026,11,1) and row.useful_life_months==60 and row.status=="active" and row.created_by_user_id==v["actor"])
    elif id=="create-maintenance-plan":
        rows=list(db.scalars(select(MaintenancePlan)))
        ok=len(rows)==1 and rows[0].code=="TRAIN-FAN-CARE" and rows[0].name=="Fan safety check" and rows[0].asset_id==v["asset"] and rows[0].interval_days==30 and rows[0].next_due_date==date(2026,12,1) and rows[0].checklist=="Check guard and clean filter" and audited("maintenance.plan_created",rows[0].id)
    elif id=="create-maintenance-work-order":
        rows=list(db.scalars(select(WorkOrder)))
        ok=len(rows)==1 and rows[0].asset_id==v["asset"] and rows[0].title=="Inspect fan guard" and rows[0].priority=="high" and rows[0].description==v["reference"] and rows[0].scheduled_date==date(2026,12,1) and rows[0].status=="open" and rows[0].plan_id is None and not rows[0].parts and audited("maintenance.work_order_created",rows[0].id)
    elif id=="start-maintenance-work":
        row=db.get(WorkOrder,"training-work")
        ok=row.status=="in_progress" and row.started_at is not None and row.completed_at is None and any(a.get("path")=="/api/v1/maintenance/work-orders/training-work/start" and a.get("status")==200 for a in actions)
    elif id=="complete-maintenance-work":
        row=db.get(WorkOrder,"training-work");plan=db.get(MaintenancePlan,"training-plan")
        ok=row.status=="completed" and row.completed_at is not None and row.labor_cost==row.external_cost==row.downtime_hours==0 and not row.parts and plan.next_due_date==date.today()+timedelta(days=30) and audited("maintenance.work_order_completed",row.id) and event("inventory.maintenance.completed",row.id)
    elif id in {"prepare-depreciation-run","post-reviewed-depreciation"}:
        rows=list(db.scalars(select(DepreciationRun)));lines=list(db.scalars(select(DepreciationLine)));asset=db.get(FixedAsset,v["asset"])
        posted=id=="post-reviewed-depreciation"
        ok=len(rows)==len(lines)==1 and rows[0].period=="2026-11" and rows[0].status==("posted" if posted else "draft") and rows[0].total_amount==v["asset_monthly"] and lines[0].run_id==rows[0].id and lines[0].asset_id==asset.id and lines[0].amount==v["asset_monthly"] and asset.accumulated_depreciation==(v["asset_monthly"] if posted else 0) and audited("depreciation.run_posted" if posted else "depreciation.run_created",rows[0].id)
        if posted:ok=ok and rows[0].posted_by_user_id==v["actor"] and event("inventory.asset.depreciation_posted",rows[0].id)
    passed=bool(ok and untouched)
    return passed,{"workflow":lesson.workflow,"passed":passed,"stock_unchanged":bool(untouched),"correction":lesson.situation.format(**v)+" Check the saved asset, location, condition, status and amount. Reset this practice if an unintended transaction was posted."}
