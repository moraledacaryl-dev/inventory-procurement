"""Control fixtures use real services; grading reads committed state only."""
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from app.models import (
    AuditLog, CountLine, CountSession, InventoryLot, Item, Location, LotBalance,
    OperationalAccessScope, StockBalance, StockDocument, StockReservation,
    TransferOrder, TransferOrderLine, User,
)
from app.services.inventory import post_document

TRANSFER_IDS={"dispatch-controlled-transfer","receive-controlled-transfer","transfer-receipt-variance","cancel-draft-transfer","transfer-stock-became-unavailable","transfer-transit-scope-required"}
TRANSIT_ACCESS={"dispatch-controlled-transfer","receive-controlled-transfer","transfer-receipt-variance","transfer-stock-became-unavailable"}
LOT_IDS={"tracked-opening-receipt","issue-specific-lot","expired-lot-writeoff","lot-quantity-shortage"}


def control_values(lesson,mode,q,base):
    opening=lesson.id=="tracked-opening-receipt"
    lot_quantity={"guided":8,"assisted":6,"independent":4}[mode]
    return {"transfer_id":"training-transfer","transit":"training-transit","lot_id":"training-lot",
        "secondary_count":{"guided":12,"assisted":9,"independent":15}[mode],
        "reservation_overage":base-3,"transfer_accepted":max(0,q-2),
        "adjustment_delta":str(-q),"lot_number":"TRAIN-TRACE-"+mode.upper(),
        "lot_action":"receipt" if opening else "issue","lot_action_label":"Receipt" if opening else "Issue",
        "lot_reason":"Approved traced opening" if opening else "Kitchen preparation",
        "lot_quantity":lot_quantity,"lot_overissue":lot_quantity+1}


def prepare_controls(db,lesson,v):
    if not lesson.workflow.startswith("control_"):return
    id=lesson.id
    if id in TRANSFER_IDS:
        db.add(Location(id=v["transit"],code="IN-TRANSIT",name="Inventory In Transit",location_type="transit"))
        if id in TRANSIT_ACCESS and db.get(User,v["actor"]).role!="owner":
            db.add(OperationalAccessScope(user_id=v["actor"],location_id=v["transit"],approval_limit=0,is_active=True))
        transfer=TransferOrder(id=v["transfer_id"],transfer_number="TRAIN-TRANSFER",source_location_id=v["store"],destination_location_id=v["kitchen"],status="draft",created_by_user_id=v["colleague"])
        transfer.lines=[TransferOrderLine(item_id=v["chicken"],quantity=v["quantity"])]
        db.add(transfer)
        if id=="transfer-stock-became-unavailable":
            db.add(StockReservation(reservation_number="TRAIN-LATER-RESERVATION",item_id=v["chicken"],location_id=v["store"],quantity=v["base"]-4,reference_type="event",reference_id="other-later-job",status="active",created_by_user_id=v["colleague"]))
    if id in {"count-multiple-units","save-incomplete-count","request-count-recheck"}:
        count=db.get(CountSession,v["count"])
        count.lines.append(CountLine(item_id=v["amenities"],system_quantity=v["base"],counted_quantity=v["secondary_count"] if id=="request-count-recheck" else None))
        if id=="request-count-recheck":
            count.status="pending_approval"
            count.created_by_user_id=v["colleague"]
            count.lines[0].counted_quantity=v["quantity"]
    if id=="stale-count-snapshot":
        db.get(CountSession,v["count"]).lines[0].counted_quantity=v["quantity"]
    if id=="start-full-count":
        old=db.get(CountSession,v["count"])
        old.status="cancelled"
        old.created_by_user_id=v["colleague"]
        old.lines[0].system_quantity=0
    if id in LOT_IDS:
        db.add(InventoryLot(id=v["lot_id"],item_id=v["chicken"],lot_number="TRAIN-LOT",manufactured_date=date(2026,10,1),expiry_date=date(2026,11,1) if id=="expired-lot-writeoff" else date(2026,12,15),supplier_id=v["supplier"],status="active"))
        db.flush()
        # Scoped staff can select only lots associated with an authorized
        # location. A known zero-balance batch remains selectable for receipt.
        db.add(LotBalance(lot_id=v["lot_id"],location_id=v["store"],quantity=0 if id=="tracked-opening-receipt" else v["lot_quantity"]))


def after_prepare_controls(db,lesson,v):
    if lesson.id in {"receive-controlled-transfer","transfer-receipt-variance"}:
        from app.api.routes.controlled_inventory import dispatch_transfer_controlled
        dispatch_transfer_controlled(v["transfer_id"],db,db.get(User,v["colleague"]))
    if lesson.id=="stale-count-snapshot":
        post_document(db,kind="issue",actor_id=v["colleague"],entries=[{"item_id":v["chicken"],"location_id":v["store"],"quantity":Decimal(-1),"unit_cost":Decimal(200),"reason":"Legitimate stock movement after the count snapshot"}],reference="TRAIN-AFTER-SNAPSHOT")


def quantity(db,item,location):
    row=db.scalar(select(StockBalance).where(StockBalance.item_id==item,StockBalance.location_id==location))
    return Decimal(row.quantity) if row else Decimal(0)


def verify_controls(db,lesson,v,actions):
    id=lesson.id;q=Decimal(v["quantity"]);base=Decimal(v["base"])
    source=quantity(db,v["chicken"],v["store"])
    dest=quantity(db,v["chicken"],v["kitchen"])
    transit=quantity(db,v["chicken"],v["transit"])
    documents=list(db.scalars(select(StockDocument).where(StockDocument.posted_by_user_id==v["actor"])).all())
    unchanged=source==base and dest==0 and transit==0 and not documents
    def refused(path,status):return any(event.get("path")=="/api/v1"+path and event.get("status")==status for event in actions)
    def audited(action,entity=None):
        query=select(AuditLog).where(AuditLog.actor_user_id==v["actor"],AuditLog.action==action)
        if entity:query=query.where(AuditLog.entity_id==entity)
        return db.scalar(query)
    def one_document(kind,reference):
        return len(documents)==1 and documents[0].document_type==kind and documents[0].reference==reference and all(m.item_id==v["chicken"] and Decimal(m.unit_cost)==200 for m in documents[0].movements)
    ok=False;evidence={"workflow":lesson.workflow}
    if id in {"reserve-event-stock","reservation-shortage"}:
        rows=list(db.scalars(select(StockReservation).where(StockReservation.item_id==v["chicken"],StockReservation.location_id==v["store"],StockReservation.status=="active")).all())
        own=[row for row in rows if row.created_by_user_id==v["actor"]]
        if id=="reserve-event-stock":
            ok=unchanged and len(own)==1 and own[0].quantity==q and own[0].reference_type=="event" and own[0].reference_id==v["reference"] and sum(Decimal(row.quantity) for row in rows)==4+q
        else:ok=unchanged and not own and sum(Decimal(row.quantity) for row in rows)==4 and refused("/reservations",409)
    elif id in {"create-controlled-transfer","correct-transfer-destination"}:
        rows=list(db.scalars(select(TransferOrder).where(TransferOrder.created_by_user_id==v["actor"])).all())
        ok=unchanged and len(rows)==1 and rows[0].notes==v["reference"] and rows[0].status=="draft" and rows[0].source_location_id==v["store"] and rows[0].destination_location_id==v["kitchen"] and len(rows[0].lines)==1 and rows[0].lines[0].item_id==v["chicken"] and rows[0].lines[0].quantity==q
        if id=="correct-transfer-destination":ok=ok and refused("/transfer-orders",422)
    elif id in TRANSFER_IDS:
        row=db.get(TransferOrder,v["transfer_id"])
        if id=="dispatch-controlled-transfer":
            ok=row.status=="dispatched" and row.dispatched_by_user_id==v["actor"] and source==base-q and transit==q and dest==0 and one_document("transfer_dispatch","TRAIN-TRANSFER") and len(documents[0].movements)==2
        elif id in {"receive-controlled-transfer","transfer-receipt-variance"}:
            accepted=q if id=="receive-controlled-transfer" else Decimal(v["transfer_accepted"])
            ok=row.status==("received" if accepted==q else "received_with_variance") and row.received_by_user_id==v["actor"] and source==base-q and transit==0 and dest==accepted and one_document("transfer_receipt","TRAIN-TRANSFER") and row.stock_document_id==documents[0].id
            if accepted<q:
                audit=audited("transfer_order.received",row.id)
                ok=ok and audit and audit.details["lines"][0]["variance_reason"]=="damaged in transit" and Decimal(audit.details["total_variance"])==q-accepted
        elif id=="cancel-draft-transfer":ok=unchanged and row.status=="cancelled" and bool(audited("transfer_order.cancelled",row.id))
        else:
            status=403 if id=="transfer-transit-scope-required" else 409
            ok=unchanged and row.status=="draft" and refused("/transfer-orders/training-transfer/dispatch",status)
        evidence["transfer_status"]=row.status
    elif id.startswith("count-") or id in {"start-full-count","save-incomplete-count","request-count-recheck","stale-count-snapshot","cancel-unused-count"}:
        count=db.get(CountSession,v["count"])
        lines={line.item_id:line for line in count.lines}
        if id=="count-multiple-units":
            ok=unchanged and count.status=="pending_approval" and len(lines)==2 and lines[v["chicken"]].counted_quantity==q and lines[v["amenities"]].counted_quantity==v["secondary_count"]
        elif id=="start-full-count":
            rows=list(db.scalars(select(CountSession).where(CountSession.created_by_user_id==v["actor"],CountSession.notes==v["reference"])).all())
            if len(rows)==1:
                count=rows[0];lines={line.item_id:line for line in count.lines}
                ok=unchanged and count.location_id==v["store"] and count.blind_count and count.approval_threshold==0 and count.status=="pending_approval" and len(lines)==3 and lines[v["chicken"]].counted_quantity==q and lines[v["amenities"]].counted_quantity==v["secondary_count"] and lines[v["alfredo"]].counted_quantity==0
        elif id=="save-incomplete-count":ok=unchanged and count.status=="open" and lines[v["chicken"]].counted_quantity==q and lines[v["amenities"]].counted_quantity is None and bool(audited("count.entries_saved",count.id))
        elif id=="request-count-recheck":
            audit=audited("count.recount_requested",count.id)
            ok=unchanged and count.status=="open" and lines[v["chicken"]].counted_quantity is None and lines[v["amenities"]].counted_quantity==v["secondary_count"] and audit and audit.details.get("item_ids")==[v["chicken"]] and audit.details.get("reason")=="verify scale and units"
        elif id=="stale-count-snapshot":ok=source==base-1 and not documents and count.status=="open" and lines[v["chicken"]].counted_quantity==q and refused("/counts/training-count/submit",409)
        elif id=="cancel-unused-count":ok=unchanged and count.status=="cancelled" and bool(audited("count.cancelled",count.id))
        # Never serialize physical/snapshot quantities in active blind exercises.
        evidence.update(count_status=count.status,count_id=count.id)
    elif id=="approved-opening-correction":
        ok=source==base-q and one_document("adjustment",v["reference"]) and len(documents[0].movements)==1 and documents[0].movements[0].quantity==-q and documents[0].movements[0].reason=="correction"
    elif id=="create-traceable-lot":
        rows=list(db.scalars(select(InventoryLot).where(InventoryLot.lot_number==v["lot_number"])).all())
        ok=unchanged and len(rows)==1 and rows[0].item_id==v["chicken"] and rows[0].supplier_id==v["supplier"] and rows[0].manufactured_date==date(2026,11,1) and rows[0].expiry_date==date(2026,12,15) and not db.scalar(select(LotBalance.id).where(LotBalance.lot_id==rows[0].id))
    elif id in LOT_IDS:
        lot_balance=db.scalar(select(LotBalance).where(LotBalance.lot_id==v["lot_id"],LotBalance.location_id==v["store"]))
        lot_quantity=Decimal(lot_balance.quantity) if lot_balance else Decimal(0)
        if id=="tracked-opening-receipt":ok=source==base+q and lot_quantity==q and one_document("receipt","TRAIN-LOT") and len(documents[0].movements)==1 and documents[0].movements[0].quantity==q
        elif id=="lot-quantity-shortage":ok=unchanged and lot_quantity==v["lot_quantity"] and refused("/lot-transactions",409)
        else:
            kind="waste" if id=="expired-lot-writeoff" else "issue"
            ok=source==base-q and lot_quantity==Decimal(v["lot_quantity"])-q and one_document(kind,"TRAIN-LOT") and len(documents[0].movements)==1 and documents[0].movements[0].quantity==-q
            if id=="expired-lot-writeoff":
                audit=audited("inventory.waste_recorded")
                ok=ok and documents[0].movements[0].reason=="expired" and audit and audit.details.get("lot_id")==v["lot_id"]
        evidence["lot_balance_matches_task"]=bool(ok)
    passed=bool(ok)
    evidence.update(passed=passed,correction=lesson.situation.format(**v)+" Keep the original evidence. Correct unposted fields, or reset this attempt if an unintended transaction was already posted.")
    return passed,evidence


def resolve_control_route(db,lesson,v):
    if lesson.id=="start-full-count":
        row=db.scalar(select(CountSession).where(CountSession.created_by_user_id==v["actor"],CountSession.notes==v["reference"]))
        if row:return f"/counts/{row.id}"
    return lesson.route.format(**v)


def recover_control_checkpoint(db,lesson,v,checkpoint,actions):
    passed,_=verify_controls(db,lesson,v,actions)
    if passed:return len(lesson.steps)
    if lesson.id in {"count-multiple-units","start-full-count"}:
        if lesson.id=="start-full-count":
            count=db.scalar(select(CountSession).where(CountSession.created_by_user_id==v["actor"],CountSession.notes==v["reference"]))
        else:count=db.get(CountSession,v["count"])
        if count and count.status=="open":
            expected={"Chicken (kg)":Decimal(v["quantity"]),"Guest amenity kit":Decimal(v["secondary_count"])}
            if lesson.id=="start-full-count":expected["Training Chicken Alfredo"]=Decimal(0)
            entries={db.get(Item,line.item_id).name:line.counted_quantity for line in count.lines}
            for index,step in enumerate(lesson.steps):
                for name,value in expected.items():
                    if step.target==f'[aria-label="Counted quantity for {name}"]' and entries.get(name)!=value:return index
            return next(index for index,step in enumerate(lesson.steps) if step.target=='[data-training="count-submit"]')
    return 0
