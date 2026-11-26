"""One evolving database per linked capstone, with explicit counterpart actors.

Counterpart actions are idempotent source-service calls, never learner role
changes. Outcome validators below remain read-only.
"""
from decimal import Decimal
from sqlalchemy import select
from app.core.roles import has_permission
from app.models.user import User
from app.models.inventory import CountSession, CountLine, StockDocument, StockBalance
from app.models.procurement import PurchaseRequisition, PurchaseRequisitionLine, SupplierQuotation, SupplierQuotationLine, PurchaseOrder, GoodsReceipt, PurchaseReturn
from app.models.operations import IntegrationEvent
from app.models.audit_log import AuditLog


def capstone_values(lesson,mode):
    if not lesson.workflow.startswith("capstone_"):return {}
    kits={"guided":12,"assisted":10,"independent":8}[mode]
    from app.services.classification_defaults import DEFAULT_DIMENSIONS
    dims={r["code"]:r["id"] for r in DEFAULT_DIMENSIONS}
    q=lesson.quantity-(0 if mode=="guided" else 1 if mode=="assisted" else 2)
    return {"cap_material":str(Decimal(q)/4),"cap_sale":{"guided":4,"assisted":3,"independent":2}[mode],"cap_arrived":q-2,"cap_accepted":q-4,"cap_kit_count":kits,"secondary_count":kits,"prop_clean":dims["available"],"prop_in_use":dims["in-use"],"prop_laundry":dims["in-laundry"],"prop_issue":dims["issue"],"prop_wash":dims["laundry"]}


def prepare_capstone(db,lesson,v):
    if lesson.id=="cap-busy-weekend":
        from dataclasses import replace
        from training.procurement_scenarios import prepare_procurement
        prepare_procurement(db,replace(lesson,id="award-timely-quotation",workflow="procurement_award-timely-quotation"),v)
        db.flush()
        db.delete(db.get(SupplierQuotation,"training-quote-fast"))
        db.get(PurchaseRequisition,"training-requisition").status="submitted"
        db.get(PurchaseRequisition,"training-requisition").approved_by_user_id=None
        db.delete(db.get(PurchaseOrder,v["po"]))
    elif lesson.id=="cap-restaurant-service":
        from app.models.inventory import Item
        from app.models.production import Recipe, RecipeLine, PosProductMapping
        db.add(Item(id="training-plated",sku="TRAIN-PLATED",name="Training served plate",category_id=v["category"],base_unit_id=v["portion"],standard_cost=50))
        db.flush()
        recipe=Recipe(id="training-serve-recipe",code="TRAIN-SERVE",name="Serve one prepared portion",output_item_id="training-plated",yield_quantity=1,status="approved",created_by_user_id=v["colleague"],approved_by_user_id=v["reviewer"])
        recipe.lines=[RecipeLine(ingredient_item_id=v["alfredo"],quantity=1,waste_factor=0)]
        db.add(recipe);db.flush()
        db.add(PosProductMapping(id="training-serve-map",external_product_id="TRAIN-SERVED-PLATE",recipe_id=recipe.id,location_id=v["store"]))
    elif lesson.id=="cap-housekeeping":
        from dataclasses import replace
        from training.property_scenarios import prepare_property, property_values
        prepare_property(db,replace(lesson,id="issue-clean-linen",workflow="property_issue-clean-linen"),{**v,**property_values(replace(lesson,id="issue-clean-linen"),"guided")})
        from app.models.property import HotelParProfile, HotelParLine
        db.add(HotelParProfile(id="training-room-par",code="TRAIN-ROOM-PAR",name="Training standard room",profile_type="room_type",location_id=v["kitchen"]))
        db.flush();db.add(HotelParLine(profile_id="training-room-par",item_id=v["linen"],par_quantity=2))
    elif lesson.id=="cap-owner-review":
        from dataclasses import replace
        from training.connected_scenarios import prepare_connected
        prepare_connected(db,replace(lesson,workflow="connected_owner",module="X"),v)
        prepare_connected(db,replace(lesson,workflow="connected_owner",module="W"),v)
    elif lesson.id=="cap-monthly-count":
        count=db.get(CountSession,v["count"])
        count.approval_threshold=1
        count.notes=v["reference"]
        count.lines.append(CountLine(item_id=v["amenities"],system_quantity=v["base"]))
    elif lesson.id=="cap-delivery-recovery":
        req=PurchaseRequisition(id="training-cap-requisition",requisition_number="TRAIN-WEEKEND-REQUEST",department="Kitchen",location_id=v["store"],status="submitted",requested_by_user_id=v["colleague"],justification="Verified supplemental weekend demand")
        req.lines=[PurchaseRequisitionLine(item_id=v["chicken"],quantity=10,estimated_unit_cost=200)]
        db.add(req);db.flush()
        quote=SupplierQuotation(id="training-cap-quote",quotation_number="TRAIN-WEEKEND-OFFER",requisition_id=req.id,supplier_id=v["supplier"],delivery_days=1,payment_terms_days=7,status="awarded")
        quote.lines=[SupplierQuotationLine(item_id=v["chicken"],quantity=10,unit_price=200)]
        db.add(quote);db.flush()
        po=db.get(PurchaseOrder,v["po"])
        po.requisition_id=req.id;po.quotation_id=quote.id;po.status="draft";po.approved_by_user_id=None;po.approved_at=None


def authorized_counterpart(db,v,permission):
    reviewer=db.get(User,v["reviewer"])
    if not reviewer or not reviewer.is_active or not has_permission(reviewer.role,permission):
        raise RuntimeError("The deterministic colleague lacks the required source permission")
    if reviewer.id==v["actor"]:raise RuntimeError("A training colleague must be a different person")
    return reviewer


def after_prepare_capstone(db,lesson,v):
    if lesson.id=="cap-busy-weekend":
        from app.api.routes.procurement import approve_requisition
        approve_requisition("training-requisition",db,authorized_counterpart(db,v,"procurement.*"))
    if lesson.id=="cap-delivery-recovery":
        from app.api.routes.procurement import approve_requisition, approve_po
        reviewer=authorized_counterpart(db,v,"procurement.*")
        approve_requisition("training-cap-requisition",db,reviewer)
        approve_po(v["po"],db,reviewer)


def run_capstone_counterparts(db,lesson,v):
    if lesson.id=="cap-busy-weekend":
        po=db.scalar(select(PurchaseOrder).where(PurchaseOrder.requisition_id=="training-requisition"))
        if po:
            from app.api.routes.procurement import approve_po
            from app.api.routes.receiving_workspace import post_controlled_receipt, ControlledReceiptCreate
            from app.services.inventory import post_document
            from app.api.routes.production import avg_cost
            reviewer=authorized_counterpart(db,v,"procurement.*")
            colleague=db.get(User,v["colleague"])
            if not colleague or not colleague.is_active or not has_permission(colleague.role,"receiving.*") or not has_permission(colleague.role,"inventory.*") or colleague.id==v["actor"]:raise RuntimeError("Invalid receiving and issue counterpart")
            if po.status=="draft":approve_po(po.id,db,reviewer)
            receipt=db.scalar(select(GoodsReceipt).where(GoodsReceipt.purchase_order_id==po.id))
            if not receipt:
                post_controlled_receipt(po.id,ControlledReceiptCreate(delivery_reference="TRAIN-WEEKEND-DR",lines=[{"purchase_order_line_id":po.lines[0].id,"received_quantity":v["cap_arrived"],"accepted_quantity":v["cap_accepted"],"rejected_quantity":2,"discrepancy_reason":"damaged or unusable goods"}]),db,colleague)
                receipt=db.scalar(select(GoodsReceipt).where(GoodsReceipt.purchase_order_id==po.id))
            issue=db.scalar(select(StockDocument).where(StockDocument.idempotency_key=="training-weekend-handover"))
            if not issue:
                post_document(db,kind="issue",actor_id=colleague.id,entries=[{"item_id":v["chicken"],"location_id":v["store"],"quantity":-Decimal(v["cap_accepted"]),"unit_cost":avg_cost(db,v["chicken"],v["store"])}],reference=receipt.goods_receipt_number,idempotency_key="training-weekend-handover")
    elif lesson.id=="cap-restaurant-service":
        from app.models.production import ProductionBatch, PosSaleEvent
        batch=db.get(ProductionBatch,v["batch"])
        if batch.status=="completed" and not db.scalar(select(PosSaleEvent.id).where(PosSaleEvent.external_event_id=="TRAIN-SERVICE-SALE")):
            # Local adapter calls the unchanged typed POS business handler. The
            # HTTP intake, production tokens, transport and worker remain blocked.
            from app.api.routes.production import process_pos_event
            from app.schemas.production import PosSaleEventIn
            actor=authorized_counterpart(db,v,"integrations.*")
            process_pos_event(PosSaleEventIn(external_event_id="TRAIN-SERVICE-SALE",external_sale_id="TRAIN-SERVICE",event_type="sale_completed",lines=[{"external_product_id":"TRAIN-SERVED-PLATE","quantity":v["cap_sale"]}]),db,actor)
    elif lesson.id=="cap-owner-review":
        row=db.get(IntegrationEvent,"training-connected-request")
        if row.payload.get("workflow_status")=="accepted" and not row.payload.get("related_entity_id"):
            from app.services.inventory import post_document
            colleague=authorized_counterpart(db,v,"inventory.*")
            document=post_document(db,kind="issue",actor_id=colleague.id,entries=[{"item_id":v["chicken"],"location_id":v["store"],"quantity":-Decimal(v["quantity"]),"unit_cost":200}],reference="TRAIN-WEEKEND-DUTY",commit=False)
            row.payload={**row.payload,"description":f"Confirmed handover of {v['quantity']} kg chicken; follow the linked movement.","related_entity_type":"stock_document","related_entity_id":document.id}
            db.commit()
    elif lesson.id=="cap-monthly-count":
        count=db.get(CountSession,v["count"])
        if count.status=="pending_approval":
            from app.api.routes.guided_counts import approve_guided_count
            reviewer=authorized_counterpart(db,v,"counts.approve")
            approve_guided_count(count.id,db,reviewer)


def record_read_after(actions,read_path,write_path):
    writes=[i for i,a in enumerate(actions) if a.get("path")==write_path and a.get("method")!="GET" and 200<=a.get("status",0)<300]
    return bool(writes and any(i>writes[-1] and a.get("path")==read_path and a.get("method")=="GET" for i,a in enumerate(actions)))


def verify_capstone(db,lesson,v,actions):
    def balance(item):return db.scalar(select(StockBalance.quantity).where(StockBalance.item_id==v[item],StockBalance.location_id==v["store"])) or Decimal(0)
    actor_docs=list(db.scalars(select(StockDocument).where(StockDocument.posted_by_user_id==v["actor"])))
    audits=set(db.scalars(select(AuditLog.action).where(AuditLog.actor_user_id==v["actor"])))
    objectives=[]
    def objective(id,title,passed,critical=True):objectives.append({"id":id,"title":title,"passed":bool(passed),"critical":critical})
    if lesson.id=="cap-busy-weekend":
        req=db.get(PurchaseRequisition,"training-requisition")
        orders=list(db.scalars(select(PurchaseOrder)))
        po=orders[0] if len(orders)==1 else None
        quote=db.get(SupplierQuotation,po.quotation_id) if po else None
        receipts=list(db.scalars(select(GoodsReceipt)))
        receipt=receipts[0] if len(receipts)==1 else None
        issues=list(db.scalars(select(StockDocument).where(StockDocument.document_type=="issue")))
        issue=issues[0] if len(issues)==1 else None
        objective("demand","The independently approved demand remains linked",req.status=="approved" and req.requested_by_user_id==v["colleague"] and req.approved_by_user_id==v["reviewer"] and bool(po and po.requisition_id==req.id))
        objective("timely_offer","The learner recorded and chose the actual timely supplier offer",bool(quote and quote.supplier_id==v["supplier"] and quote.delivery_days==1 and quote.payment_terms_days==v["terms"] and quote.notes==v["reference"] and quote.valid_until is None and quote.status=="awarded" and len(quote.lines)==1 and quote.lines[0].quantity==v["quantity"] and quote.lines[0].unit_price==220 and "quotation.recorded" in audits and "quotation.awarded" in audits))
        objective("independent_order","One linked PO has separate approval and correct commercial terms",bool(po and po.created_by_user_id==v["actor"] and po.approved_by_user_id==v["reviewer"] and po.supplier_id==v["supplier"] and po.delivery_location_id==v["store"] and po.status=="partially_received" and len(po.lines)==1 and po.lines[0].ordered_quantity==v["quantity"] and po.lines[0].unit_price==220 and po.lines[0].received_quantity==v["cap_arrived"]))
        line=receipt.lines[0] if receipt and len(receipt.lines)==1 else None
        objective("partial_receipt","The receiving colleague records actual acceptance and rejection",bool(po and receipt and line and receipt.purchase_order_id==po.id and receipt.received_by_user_id==v["colleague"] and line.received_quantity==v["cap_arrived"] and line.accepted_quantity==v["cap_accepted"] and line.rejected_quantity==2 and line.unit_cost==220))
        objective("handover","The accepted stock has one receipt-referenced kitchen issue",bool(receipt and issue and issue.reference==receipt.goods_receipt_number and issue.posted_by_user_id==v["colleague"] and len(issue.movements)==1 and issue.movements[0].item_id==v["chicken"] and issue.movements[0].quantity==-v["cap_accepted"]))
        receipt_doc=db.get(StockDocument,receipt.stock_document_id) if receipt else None
        stock=db.scalar(select(StockBalance).where(StockBalance.item_id==v["chicken"],StockBalance.location_id==v["store"]))
        objective("valuation","Receipt and issue retain the true purchase and weighted stock costs",bool(receipt_doc and issue and stock and len(receipt_doc.movements)==1 and receipt_doc.movements[0].quantity==v["cap_accepted"] and receipt_doc.movements[0].unit_cost==220 and issue.movements[0].unit_cost==stock.average_cost))
        objective("no_shortcut","The purchaser made no stock adjustment or duplicate purchase",not actor_docs and balance("chicken")==v["base"] and len(orders)==1)
        objective("inspect_order","The learner opened this order after award",bool(po and record_read_after(actions,f"/api/v1/purchase-orders/{po.id}/detail","/api/v1/requisitions/training-requisition/award-quotation")),False)
    elif lesson.id=="cap-restaurant-service":
        from app.models.production import ProductionBatch, PosSaleEvent, Recipe
        from app.models.staff_meals import StaffMeal
        batch=db.get(ProductionBatch,v["batch"])
        production=db.get(StockDocument,batch.stock_document_id) if batch.stock_document_id else None
        sale=db.scalar(select(PosSaleEvent).where(PosSaleEvent.external_event_id=="TRAIN-SERVICE-SALE"))
        sale_doc=db.get(StockDocument,sale.stock_document_id) if sale and sale.stock_document_id else None
        meals=list(db.scalars(select(StaffMeal).where(StaffMeal.created_by_user_id==v["actor"])))
        meal=meals[0] if len(meals)==1 else None
        movements={m.item_id:m for m in production.movements} if production else {}
        objective("actual_batch","Actual raw use and usable output were posted once",batch.status=="completed" and batch.actual_quantity==v["quantity"] and batch.completed_by_user_id==v["actor"] and len(movements)==2 and movements[v["chicken"]].quantity==-Decimal(v["cap_material"]) and movements[v["alfredo"]].quantity==v["quantity"] and movements[v["alfredo"]].unit_cost==50)
        objective("serving_sale","The faithful local sale consumed prepared portions at actual cost",bool(sale and sale.status=="processed" and sale_doc and sale_doc.posted_by_user_id==v["reviewer"] and len(sale_doc.movements)==1 and sale_doc.movements[0].item_id==v["alfredo"] and sale_doc.movements[0].quantity==-v["cap_sale"] and sale_doc.movements[0].unit_cost==50))
        objective("staff_meal","One actual staff lunch consumed two prepared portions",bool(meal and meal.status=="posted" and meal.meal_name=="Training staff lunch" and meal.location_id==v["store"] and len(meal.lines)==1 and meal.lines[0].item_id==v["alfredo"] and meal.lines[0].quantity==2 and meal.lines[0].unit_cost==50))
        objective("no_double_consumption","Raw ingredients were deducted only during preparation",balance("chicken")==v["base"]-Decimal(v["cap_material"]) and balance("alfredo")==v["quantity"]-v["cap_sale"]-2 and len(actor_docs)==2)
        ids=[id for id in [batch.id,batch.stock_document_id,sale.id if sale else None,sale.stock_document_id if sale else None,meal.posted_document_id if meal else None] if id]
        events=list(db.scalars(select(IntegrationEvent).where(IntegrationEvent.destination_system=="accounting",IntegrationEvent.aggregate_id.in_(ids))))
        objective("local_accounting","Preparation, sale and staff meal retain pending local Accounting evidence",len(ids)==5 and len(events)==5 and all(e.status=="pending" and e.processed_at is None for e in events))
    elif lesson.id=="cap-housekeeping":
        from app.models.property import PropertyBalance, PropertyMovement, HotelParLine
        rows=list(db.scalars(select(PropertyMovement)))
        def bucket(location,condition):return db.scalar(select(PropertyBalance.quantity).where(PropertyBalance.item_id==v["linen"],PropertyBalance.location_id==location,PropertyBalance.condition_id==condition)) or Decimal(0)
        objective("consumables","Only the actual amenity kits were consumed",balance("amenities")==v["base"]-v["quantity"] and balance("chicken")==v["base"] and len(actor_docs)==1 and actor_docs[0].document_type=="issue" and len(actor_docs[0].movements)==1 and actor_docs[0].movements[0].item_id==v["amenities"] and actor_docs[0].movements[0].quantity==-v["quantity"] and actor_docs[0].movements[0].unit_cost==50)
        expected={"TRAIN-ROOM-ISSUE":(4,v["store"],v["prop_clean"],v["kitchen"],v["prop_in_use"],v["prop_issue"]),"TRAIN-LAUNDRY":(2,v["kitchen"],v["prop_in_use"],v["store"],v["prop_laundry"],v["prop_wash"]),"TRAIN-CLEAN":(1,v["store"],v["prop_laundry"],v["store"],v["prop_clean"],v["prop_wash"])}
        for ref,want in expected.items():
            matches=[row for row in rows if row.reference==ref]
            objective(ref,"Correct reusable handover "+ref,len(matches)==1 and matches[0].created_by_user_id==v["actor"] and matches[0].item_id==v["linen"] and (matches[0].quantity,matches[0].source_location_id,matches[0].source_condition_id,matches[0].destination_location_id,matches[0].destination_condition_id,matches[0].movement_reason_id)==want)
        objective("conservation","All 12 towels remain accounted for in their real conditions",len(rows)==3 and bucket(v["store"],v["prop_clean"])==9 and bucket(v["kitchen"],v["prop_in_use"])==2 and bucket(v["store"],v["prop_laundry"])==1 and sum(db.scalars(select(PropertyBalance.quantity)))==12)
        objective("standard","The approved two-towel standard remains separate from actual handovers",db.scalar(select(HotelParLine.par_quantity).where(HotelParLine.profile_id=="training-room-par"))==2)
    elif lesson.id=="cap-owner-review":
        event=db.get(IntegrationEvent,"training-connected-request");payload=event.payload
        document=db.get(StockDocument,payload.get("related_entity_id")) if payload.get("related_entity_id") else None
        statuses=list(db.scalars(select(IntegrationEvent).where(IntegrationEvent.event_type=="inventory.operations.request_status_changed")))
        objective("accountability","The same canonical assignee retains completed responsibility",payload.get("workflow_status")=="completed" and payload.get("assigned_to_user_id")==v["colleague"] and payload.get("requester_user_id")==v["colleague"] and payload.get("decision_notes")=="handover confirmed" and payload.get("decided_by_user_id")==v["actor"])
        objective("handover","One different authorized colleague issued the linked goods",bool(document and document.posted_by_user_id==v["reviewer"] and document.reference=="TRAIN-WEEKEND-DUTY" and len(document.movements)==1 and document.movements[0].item_id==v["chicken"] and document.movements[0].quantity==-v["quantity"] and document.movements[0].unit_cost==200))
        objective("no_duplicate","Completing follow-up did not deduct the goods twice",not actor_docs and balance("chicken")==v["base"]-v["quantity"])
        objective("pending_status","Acceptance and completion retain two pending local handoffs",len(statuses)==2 and {row.payload.get("workflow_status") for row in statuses}=={"accepted","completed"} and all(row.status=="pending" and row.processed_at is None and row.payload.get("assigned_to_user_id")==v["colleague"] and row.payload.get("decision_notes")=={"accepted":"verified need","completed":"handover confirmed"}.get(row.payload.get("workflow_status")) for row in statuses))
        from dataclasses import replace
        from training.connected_scenarios import verify_connected
        retry,_=verify_connected(db,replace(lesson,id="requeue-failed-accounting-handoff",module="W"),{**v,"base":v["base"]-v["quantity"]},actions)
        objective("retry","The existing failed Accounting event was requeued without new obligations",retry)
    elif lesson.id=="cap-monthly-count":
        count=db.get(CountSession,v["count"]);lines={line.item_id:line for line in count.lines}
        document=db.get(StockDocument,count.posted_document_id) if count.posted_document_id else None
        objective("physical_truth","Both actual physical quantities are saved",len(lines)==2 and lines[v["chicken"]].counted_quantity==v["quantity"] and lines[v["amenities"]].counted_quantity==v["cap_kit_count"])
        objective("submission","The creator submitted the same session for review","count.approval_requested" in audits and count.created_by_user_id==v["actor"])
        objective("independent_review","A different authorized colleague approved it",count.status=="posted" and count.approved_by_user_id==v["reviewer"] and count.approved_by_user_id!=count.created_by_user_id)
        objective("stock_result","Posted stock equals the physical observations",balance("chicken")==v["quantity"] and balance("amenities")==v["cap_kit_count"])
        movement_map={m.item_id:m for m in document.movements} if document else {}
        objective("single_adjustment","One linked adjustment preserves the actual unit costs",bool(document and document.document_type=="count_adjustment" and document.posted_by_user_id==v["reviewer"] and document.reference==count.count_number and len(movement_map)==2 and movement_map[v["chicken"]].quantity==v["quantity"]-v["base"] and movement_map[v["chicken"]].unit_cost==200 and movement_map[v["amenities"]].quantity==v["cap_kit_count"]-v["base"] and movement_map[v["amenities"]].unit_cost==50))
        objective("no_shortcut","The creator made no separate adjustment",not actor_docs and audits<={"count.entries_saved","count.approval_requested"})
        objective("final_review","The final count was refreshed after submission",record_read_after(actions,f"/api/v1/counts/{v['count']}/detail",f"/api/v1/counts/{v['count']}/submit"),False)
    elif lesson.id=="cap-delivery-recovery":
        po=db.get(PurchaseOrder,v["po"])
        receipts=list(db.scalars(select(GoodsReceipt).where(GoodsReceipt.received_by_user_id==v["actor"])))
        returns=list(db.scalars(select(PurchaseReturn).where(PurchaseReturn.created_by_user_id==v["actor"])))
        receipt=receipts[0] if len(receipts)==1 else None;returned=returns[0] if len(returns)==1 else None
        received=receipt.lines[0] if receipt and len(receipt.lines)==1 else None
        objective("actual_receipt","The linked receipt records actual arrived and rejected goods",bool(receipt and received and receipt.purchase_order_id==po.id and receipt.delivery_reference==v["reference"] and received.item_id==v["chicken"] and received.received_quantity==v["quantity"] and received.accepted_quantity==v["quantity"]-2 and received.rejected_quantity==2))
        objective("authorized_return","One previously accepted kg was returned against the same order",bool(returned and returned.purchase_order_id==po.id and returned.reason=="quality failure" and po.lines[0].returned_quantity==1))
        objective("order_continuity","Demand, quotation, approval and arrived quantities remain linked",po.requisition_id=="training-cap-requisition" and po.quotation_id=="training-cap-quote" and po.approved_by_user_id==v["reviewer"] and po.status=="partially_received" and po.lines[0].received_quantity==v["quantity"] and po.lines[0].ordered_quantity==10)
        objective("stock_result","Only accepted stock less the later return is usable",balance("chicken")==v["base"]+v["quantity"]-3)
        linked={receipt.stock_document_id,returned.stock_document_id} if receipt and returned else set()
        objective("no_duplicate","Only the linked receipt and return moved learner stock",len(actor_docs)==2 and {d.id for d in actor_docs}==linked and audits<={"stock.document_posted","goods_receipt.controlled_posted","purchase_return.controlled_posted"})
        by_id={d.id:d for d in actor_docs}
        receipt_doc=by_id.get(receipt.stock_document_id) if receipt else None
        return_doc=by_id.get(returned.stock_document_id) if returned else None
        objective("valuation","Accepted stock and the later credit preserve the actual unit cost",bool(received and received.unit_cost==200 and receipt_doc and return_doc and len(receipt_doc.movements)==len(return_doc.movements)==1 and receipt_doc.movements[0].quantity==v["quantity"]-2 and receipt_doc.movements[0].unit_cost==200 and return_doc.movements[0].quantity==-1 and return_doc.movements[0].unit_cost==200))
        events=list(db.scalars(select(IntegrationEvent).where(IntegrationEvent.aggregate_id.in_([receipt.id,returned.id])))) if receipt and returned else []
        objective("local_handoffs","Both Accounting handoffs remain pending locally",len(events)==2 and {e.event_type for e in events}=={"procurement.goods_received","procurement.purchase_return.posted"} and all(e.status=="pending" and e.processed_at is None for e in events))
    else:raise RuntimeError("Unknown linked capstone")
    passed=bool(objectives) and all(row["passed"] for row in objectives)
    failed=[row["title"] for row in objectives if not row["passed"]]
    evidence={"workflow":lesson.workflow,"passed":passed,"objectives":objectives,"practical_score":round(100*sum(row["passed"] for row in objectives)/len(objectives),2),"critical_pass":all(row["passed"] for row in objectives if row["critical"]),"correction":"Still to demonstrate: "+"; ".join(failed)+". "+lesson.correction}
    # Never return hidden starting quantities through a blind-count assessment.
    return passed,evidence


def recover_capstone_checkpoint(db,lesson,v,checkpoint,actions):
    passed,_=verify_capstone(db,lesson,v,actions)
    if passed:return len(lesson.steps)
    if lesson.id=="cap-busy-weekend":
        if db.scalar(select(PurchaseOrder.id).where(PurchaseOrder.requisition_id=="training-requisition")):return 10
        if db.scalar(select(SupplierQuotation.id).where(SupplierQuotation.supplier_id==v["supplier"])):return max(7,checkpoint)
        return checkpoint
    if lesson.id=="cap-restaurant-service":
        from app.models.production import ProductionBatch
        batch=db.get(ProductionBatch,v["batch"])
        if batch.status=="completed":return 5
        if batch.status=="in_progress":return max(1,checkpoint)
        return checkpoint
    if lesson.id=="cap-housekeeping":
        from app.models.property import PropertyMovement
        refs=set(db.scalars(select(PropertyMovement.reference).where(PropertyMovement.created_by_user_id==v["actor"])))
        if "TRAIN-CLEAN" in refs:return len(lesson.steps)
        if "TRAIN-LAUNDRY" in refs:return 28
        if "TRAIN-ROOM-ISSUE" in refs:return 19
        if db.scalar(select(StockDocument.id).where(StockDocument.posted_by_user_id==v["actor"])):return 9
        return checkpoint
    if lesson.id=="cap-owner-review":
        status=db.get(IntegrationEvent,"training-connected-request").payload.get("workflow_status")
        if status=="completed":return max(7,checkpoint)
        if status=="accepted":return max(4,checkpoint)
        return checkpoint
    if lesson.id=="cap-monthly-count":
        count=db.get(CountSession,v["count"])
        if count.status in {"posted","pending_approval"}:return len(lesson.steps)-1
        lines={line.item_id:line.counted_quantity for line in count.lines}
        if lines[v["chicken"]]==v["quantity"] and lines[v["amenities"]]==v["cap_kit_count"]:return 3
        if lines[v["chicken"]]==v["quantity"]:return 1
        return 0
    if lesson.id=="cap-delivery-recovery":
        if db.scalar(select(GoodsReceipt.id).where(GoodsReceipt.purchase_order_id==v["po"],GoodsReceipt.received_by_user_id==v["actor"])):return 9
        return checkpoint  # The actual receiving draft persists in the tab.
    return 0


def resolve_capstone_route(db,lesson,v):
    if lesson.id=="cap-housekeeping":
        from app.models.property import PropertyMovement
        if db.scalar(select(StockDocument.id).where(StockDocument.posted_by_user_id==v["actor"])):return "/hotel/property"
    if lesson.id=="cap-restaurant-service":
        from app.models.production import ProductionBatch
        if db.get(ProductionBatch,v["batch"]).status=="completed":return "/fnb/staff-meals"
    return lesson.route.format(**v)
