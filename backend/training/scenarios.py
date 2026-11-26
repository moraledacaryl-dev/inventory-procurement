"""Deterministic fixtures and read-only outcome verification of real business data."""
from decimal import Decimal
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from dataclasses import asdict
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.db.base import Base
from app.models import *  # registers the same schema used by Inventory
from app.core.security import hash_password
from app.services.inventory import post_document
from app.services.classification_defaults import ensure_operating_structure_defaults
from training.curriculum import Lesson, VERSION
from training.catalogue_scenarios import catalogue_values, prepare_catalogue, verify_catalogue
from training.control_scenarios import control_values, prepare_controls, after_prepare_controls, verify_controls, resolve_control_route, recover_control_checkpoint
from training.procurement_scenarios import prepare_procurement, after_prepare_procurement, verify_procurement, procurement_inspection
from training.food_scenarios import prepare_food, after_prepare_food, verify_food
from training.property_scenarios import property_values, prepare_property, after_prepare_property, verify_property
from training.connected_scenarios import prepare_connected, after_prepare_connected, verify_connected
from training.capstone_scenarios import capstone_values, prepare_capstone, after_prepare_capstone, verify_capstone, recover_capstone_checkpoint, resolve_capstone_route

IDS = {key: f"training-{key}" for key in ["actor", "colleague", "reviewer", "purchaser", "store", "kitchen", "restricted", "category", "kg", "gram", "portion", "each", "chicken", "amenities", "alfredo", "supplier", "po", "po-line", "count", "recipe", "batch"]}


def values(lesson: Lesson, mode: str):
    quantity = lesson.quantity
    if mode == "assisted" and quantity > 1:
        quantity -= 1
    if mode == "independent" and quantity > 1:
        quantity = max(1, quantity - 2)
    rejected = min(lesson.rejected, quantity)
    base={"guided":24,"assisted":27,"independent":31}[mode]
    return {**IDS, **catalogue_values(mode), **control_values(lesson,mode,quantity,base), **property_values(lesson,mode), **capstone_values(lesson,mode), "quantity": quantity, "rejected": rejected,
        "practice_item": IDS["amenities"] if lesson.id in {"housekeeping-supplies","cap-housekeeping"} else IDS["chicken"],
        "practice_name": "TRAIN-AMENITIES — Guest amenity kit" if lesson.id in {"housekeeping-supplies","cap-housekeeping"} else "TRAIN-CHICKEN — Chicken (kg)",
        "movement_reason": "Room preparation" if lesson.id in {"housekeeping-supplies","cap-housekeeping"} else {"issue":"Kitchen preparation","receipt":"Opening inventory","transfer":"Kitchen replenishment"}.get(lesson.workflow,"Training practice"),
        "base": {"guided": 24, "assisted": 27, "independent": 31}[mode],
        "reference": f"TRAIN-{lesson.id.upper()}-{mode.upper()}",
        "reject_reason": "wrong item delivered" if lesson.id == "wrong-item" else "unacceptable expiry" if lesson.id == "expired-delivery" else "damaged or unusable goods",
        "action_label": "Used or issued stock" if lesson.id=="cap-housekeeping" else {"issue": "Used or issued stock", "receipt": "Received stock (no PO)", "transfer": "Moved between locations"}.get(lesson.workflow, lesson.workflow)}


def engine_for(path: Path):
    if path.is_symlink() or path.parent.name != "inventory-training" or not path.name.startswith("attempt-") or path.suffix != ".sqlite":
        raise RuntimeError("Invalid training sandbox path")
    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False, "timeout": 30})


def prepare(path: Path, lesson: Lesson, role: str, mode: str):
    if path.exists():
        raise RuntimeError("Refusing to overwrite an existing practice database")
    engine = engine_for(path)
    v = values(lesson, mode)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        ensure_operating_structure_defaults(db)
        db.add_all([
            User(id=IDS["actor"], email="inventory-learner@example.com", full_name="Training participant", role=role, password_hash=hash_password("unusable-training-password")),
            User(id=IDS["colleague"], email="inventory-colleague@example.com", full_name="Fictional colleague", role="owner", password_hash=hash_password("unusable-training-password")),
            User(id=IDS["reviewer"], email="inventory-reviewer@example.com", full_name="Fictional reviewer", role="owner", password_hash=hash_password("unusable-training-password")),
            Category(id=IDS["category"], name="Training food"),
            UnitOfMeasure(id=IDS["kg"], code="TRAIN-KG", name="Kilogram", precision=4),
            UnitOfMeasure(id=IDS["gram"], code="TRAIN-G", name="Gram", precision=4),
            UnitOfMeasure(id=IDS["portion"], code="TRAIN-PORTION", name="Portion", precision=0),
            UnitOfMeasure(id=IDS["each"], code="TRAIN-EACH", name="Each", precision=0),
            Location(id=IDS["store"], code="TRAIN-STORE", name="Training stockroom"),
            Location(id=IDS["kitchen"], code="TRAIN-KITCHEN", name="Training kitchen"),
            Location(id=IDS["restricted"], code="TRAIN-RESTRICTED", name="Other department — no access"),
            Supplier(id=IDS["supplier"], code="TRAIN-VALLEY", name="Training Valley Foods", payment_terms_days=7),
        ])
        db.flush()
        db.add_all([
            Item(id=IDS["chicken"], sku="TRAIN-CHICKEN", name="Chicken (kg)", category_id=IDS["category"], base_unit_id=IDS["kg"], standard_cost=200, minimum_stock=40),
            Item(id=IDS["alfredo"], sku="TRAIN-ALFREDO", name="Training Chicken Alfredo", category_id=IDS["category"], base_unit_id=IDS["portion"], standard_cost=50),
            Item(id=IDS["amenities"], sku="TRAIN-AMENITIES", name="Guest amenity kit", category_id=IDS["category"], base_unit_id=IDS["each"], standard_cost=50),
        ])
        db.flush()
        db.add(UnitConversion(item_id=IDS["chicken"], from_unit_id=IDS["kg"], to_unit_id=IDS["gram"], multiplier=1000))
        db.add(SupplierItem(supplier_id=IDS["supplier"], item_id=IDS["chicken"], last_price=200, lead_time_days=3, minimum_order_quantity=1, is_preferred=True))
        if role != "owner":
            locations = [None] if lesson.global_access or role in {"procurement_officer", "viewer"} else [IDS["store"], IDS["kitchen"]] if role == "inventory_manager" else [IDS["store"]]
            for location in locations:
                db.add(OperationalAccessScope(user_id=IDS["actor"], location_id=location, approval_limit=10000, is_active=True))
        # Opening stock precedes this exercise's counting window. Windows
        # clocks can assign equal timestamps to consecutive fixture writes;
        # the unchanged source correctly treats >= snapshot as later movement.
        # Give only these synthetic historical openings a prior-day timestamp.
        opening_at=datetime.now(timezone.utc)-timedelta(days=1)
        for item,cost,reference in (("chicken",200,"Synthetic opening stock"),("amenities",50,"Synthetic amenities")):
            document=post_document(db,kind="receipt",actor_id=IDS["colleague"],entries=[{"item_id":IDS[item],"location_id":IDS["store"],"quantity":Decimal(v["base"]),"unit_cost":Decimal(cost)}],reference=reference,commit=False)
            document.posted_at=opening_at
            for movement in db.scalars(select(StockMovement).where(StockMovement.document_id==document.id)):movement.created_at=opening_at
        db.add(StockReservation(reservation_number="TRAIN-RESERVE", item_id=IDS["chicken"], location_id=IDS["store"], quantity=4, reference_type="training", reference_id="another-job", status="active", created_by_user_id=IDS["colleague"]))
        if lesson.workflow == "requisition":
            db.add(ItemLocationSetting(item_id=IDS["chicken"], location_id=IDS["store"], minimum_stock=v["base"] + 6 + v["quantity"], reorder_quantity=0, preferred_supplier_id=IDS["supplier"]))
        po = PurchaseOrder(id=IDS["po"], purchase_order_number="TRAIN-PO", supplier_id=IDS["supplier"], delivery_location_id=IDS["store"], status="draft" if lesson.workflow == "approve_po" else "approved", created_by_user_id=IDS["colleague"])
        if po.status=="approved":
            po.approved_by_user_id=IDS["reviewer"];po.approved_at=datetime(2026,11,20,tzinfo=timezone.utc)
        order_quantity = v["quantity"] if lesson.workflow == "approve_po" else {"guided":10,"assisted":12,"independent":14}[mode] if lesson.id == "management-review" else 10
        po.lines = [PurchaseOrderLine(id=IDS["po-line"], item_id=IDS["chicken"], ordered_quantity=order_quantity, unit_price=200, received_quantity=0, returned_quantity=0)]
        db.add(po)
        if lesson.id == "check-order":
            decoy = PurchaseOrder(purchase_order_number="TRAIN-PO-WRONG", supplier_id=IDS["supplier"], delivery_location_id=IDS["kitchen"], status="approved", created_by_user_id=IDS["colleague"])
            decoy.lines = [PurchaseOrderLine(item_id=IDS["chicken"], ordered_quantity=10, unit_price=200)]
            db.add(decoy)
        count = CountSession(id=IDS["count"], count_number="TRAIN-COUNT", location_id=IDS["store"], blind_count=True, approval_threshold=1,
            created_by_user_id=IDS["colleague"] if lesson.workflow == "approve_count" else IDS["actor"], status="pending_approval" if lesson.workflow == "approve_count" else "open")
        count.lines = [CountLine(item_id=IDS["chicken"], system_quantity=v["base"], counted_quantity=v["quantity"] if lesson.workflow == "approve_count" else None)]
        db.add(count)
        recipe = Recipe(id=IDS["recipe"], code="TRAIN-ALFREDO", name="Training Chicken Alfredo", output_item_id=IDS["alfredo"], yield_quantity=1, status="approved", created_by_user_id=IDS["colleague"], approved_by_user_id=IDS["reviewer"],approved_at=datetime(2026,11,20,tzinfo=timezone.utc))
        recipe.lines = [RecipeLine(ingredient_item_id=IDS["chicken"], quantity=Decimal("0.25"), waste_factor=0)]
        db.add(recipe)
        db.flush()
        if lesson.id == "expiry-rotation":
            lot=InventoryLot(id="training-expiry-lot",item_id=IDS["chicken"],lot_number="TRAIN-EXPIRY",expiry_date=date(2026,11,27),status="active")
            db.add(lot);db.flush()
            db.add(LotBalance(lot_id=lot.id,location_id=IDS["store"],quantity={"guided":5,"assisted":6,"independent":7}[mode]))
        if lesson.id == "menu-mapping":
            menu=MenuItem(name="Training Chicken Alfredo",display_name="Training Chicken Alfredo",category="Training meals",prep_station="kitchen")
            menu.variants=[MenuVariant(name="Regular",sku="TRAIN-MENU-ALFREDO",barcode="9000000000001",price={"guided":250,"assisted":275,"independent":300}[mode],recipe_id=recipe.id,inventory_item_id=IDS["alfredo"])]
            db.add(menu)
        if lesson.id == "accounting-proof":
            db.add(IntegrationEvent(id="training-accounting",direction="outbound",source_system="inventory",destination_system="accounting",event_type="procurement.purchase_order.approved",aggregate_type="purchase_order",aggregate_id="TRAIN-REVIEW",idempotency_key="training-accounting-review",status="completed",payload={"purchase_order_id":IDS["po"],"total":"2000","accounting_intake":{"status":"ready_for_review","review_id":"TRAIN-ONLY"}}))
        if lesson.id == "connected-work":
            db.add(IntegrationEvent(id="training-operations",direction="inbound",source_system="command-center",destination_system="inventory",event_type="operations.request.submitted",aggregate_type="operational_request",aggregate_id="TRAIN-NEED",idempotency_key="training-need",status="completed",payload={"external_request_id":"TRAIN-NEED","department":"Kitchen","request_type":"purchase_need","title":"Training weekend supplies","workflow_status":"submitted","priority":"urgent"}))
        if lesson.id == "admin-controls":
            db.add(User(id=IDS["purchaser"],email="training-purchaser@example.com",full_name="Training purchasing colleague",role="procurement_officer",password_hash=hash_password("unusable-training-password")))
            db.flush()
            db.add(OperationalAccessScope(user_id=IDS["purchaser"],location_id=IDS["store"],approval_limit={"guided":1000,"assisted":2000,"independent":3000}[mode],is_active=True))
        if lesson.id == "asset-maintenance":
            asset_type=db.scalar(select(OperationalDimension).where(OperationalDimension.dimension_type=="item_type",OperationalDimension.behavior_key=="fixed_asset"))
            asset_class=db.scalar(select(OperationalDimension).where(OperationalDimension.dimension_type=="asset_class"))
            method=db.scalar(select(OperationalDimension).where(OperationalDimension.dimension_type=="depreciation_method"))
            if asset_class is None:
                asset_class=OperationalDimension(dimension_type="asset_class",code="TRAIN-EQUIPMENT",name="Training equipment",behavior_key="equipment")
                db.add(asset_class)
            if method is None:
                method=OperationalDimension(dimension_type="depreciation_method",code="TRAIN-STRAIGHT",name="Training straight line",behavior_key="straight_line")
                db.add(method)
            db.flush()
            asset_item=Item(id="training-fridge-item",sku="TRAIN-FRIDGE",name="Training refrigerator",category_id=IDS["category"],base_unit_id=IDS["portion"],item_type_id=asset_type.id,track_stock=False)
            db.add(asset_item);db.flush()
            db.add(FixedAsset(asset_tag="TRAIN-FRIDGE-01",item_id=asset_item.id,asset_class_id=asset_class.id,depreciation_method_id=method.id,location_id=IDS["store"],acquisition_date=date(2026,1,1),acquisition_cost={"guided":20000,"assisted":22000,"independent":24000}[mode],status="active",created_by_user_id=IDS["colleague"]))
        db.add(ProductionBatch(id=IDS["batch"], batch_number="TRAIN-BATCH", recipe_id=recipe.id, location_id=IDS["store"], planned_quantity=12, created_by_user_id=IDS["actor"]))
        prepare_catalogue(db,lesson,v)
        prepare_controls(db,lesson,v)
        prepare_procurement(db,lesson,v)
        prepare_food(db,lesson,v)
        prepare_property(db,lesson,v)
        prepare_connected(db,lesson,v)
        prepare_capstone(db,lesson,v)
        db.commit()
        after_prepare_controls(db,lesson,v)
        after_prepare_procurement(db,lesson,v)
        after_prepare_food(db,lesson,v)
        after_prepare_property(db,lesson,v)
        after_prepare_connected(db,lesson,v)
        after_prepare_capstone(db,lesson,v)
        if lesson.workflow == "return" or lesson.id == "later-delivery":
            # Seed an earlier real receipt through the same route and service.
            from app.api.routes.receiving_workspace import ControlledReceiptCreate, post_controlled_receipt
            prior = 10 if lesson.workflow == "return" else 10 - v["quantity"]
            post_controlled_receipt(IDS["po"], ControlledReceiptCreate(delivery_reference="TRAIN-EARLIER-DR", lines=[{"purchase_order_line_id": IDS["po-line"], "received_quantity": prior, "accepted_quantity": prior, "rejected_quantity": 0}]), db, db.get(User, IDS["colleague"]))
    engine.dispose()
    path.chmod(0o600)


def balance(db, item="chicken", location="store"):
    row = db.scalar(select(StockBalance).where(StockBalance.item_id == IDS[item], StockBalance.location_id == IDS[location]))
    return Decimal(row.quantity) if row else Decimal(0)


def practical_question(lesson, mode):
    v = values(lesson, mode)
    if lesson.workflow=="read_procurement":return procurement_inspection(lesson,mode,v)
    tasks={
        "find-your-work":("On Home, how many pending purchase orders are shown?","1","/dashboard"),
        "catalogue-units":("In this item's conversions, what multiplier converts kilograms to grams?","1000",f"/items/{IDS['chicken']}"),
        "expiry-rotation":("In the expiry queue, how many kg are shown for TRAIN-EXPIRY?",str({"guided":5,"assisted":6,"independent":7}[mode]),"/inventory-operations"),
        "menu-mapping":("What is the Regular price of Training Chicken Alfredo in pesos?",str({"guided":250,"assisted":275,"independent":300}[mode]),"/fnb/menu"),
        "asset-maintenance":("What is the acquisition cost of TRAIN-FRIDGE-01 in pesos?",str({"guided":20000,"assisted":22000,"independent":24000}[mode]),"/assets"),
        "accounting-proof":("For purchase_order: TRAIN-REVIEW, what Accounting intake status is shown?","ready for review","/integrations/accounting"),
        "connected-work":("What is the status of Training weekend supplies?","submitted","/integrations/operations"),
        "management-review":("In supplier performance, what ordered value is shown for Training Valley Foods in pesos?",str({"guided":2000,"assisted":2400,"independent":2800}[mode]),"/reports"),
        "admin-controls":("What approval limit is configured for Training purchasing colleague in pesos?",str({"guided":1000,"assisted":2000,"independent":3000}[mode]),"/settings/access-scopes"),
    }
    if lesson.id in tasks:
        return tasks[lesson.id]
    if lesson.workflow == "read_stock":
        return "On the Stock page, how many kg of chicken are available after the 4 kg reservation?", str(v["base"] - 4), "/stock"
    if lesson.workflow == "read_supplier":
        return "In this supplier's item links, how many delivery lead-time days are shown for chicken?", "3", f"/suppliers/{IDS['supplier']}"
    if lesson.workflow == "read_recipe":
        return "Open the training recipe. What is the chicken cost for one portion in pesos?", "50", f"/production/recipes/{IDS['recipe']}"
    return "", "", lesson.route.format(**v)


def inspection_endpoint(lesson, db=None):
    if lesson.workflow=="read_procurement":
        if lesson.id=="inspect-awarded-order":
            po=db.scalar(select(PurchaseOrder).where(PurchaseOrder.quotation_id=="training-quote-fast")) if db is not None else None
            return f"/api/v1/purchase-orders/{po.id}/detail" if po else "/api/v1/procurement/quotation-workspace"
        return "/api/v1/purchase-orders/training-po/detail"
    endpoints={"find-your-work":"/api/v1/dashboard/summary", "catalogue-units":f"/api/v1/items/{IDS['chicken']}/configuration", "expiry-rotation":"/api/v1/reports/expiry", "menu-mapping":"/api/v1/fnb/menu", "asset-maintenance":"/api/v1/assets", "accounting-proof":"/api/v1/integrations/accounting/workspace", "connected-work":"/api/v1/integrations/operations/workspace", "management-review":"/api/v1/supplier-performance", "admin-controls":"/api/v1/access-scopes"}
    if lesson.id in endpoints:return endpoints[lesson.id]
    return {"read_stock":"/api/v1/availability", "read_supplier":f"/api/v1/suppliers/{IDS['supplier']}/detail", "read_recipe":f"/api/v1/recipes/{IDS['recipe']}/costing-detail"}.get(lesson.workflow)


def read_only_unchanged(db,actor_id):
    return not db.scalar(select(AuditLog.id).where(AuditLog.actor_user_id==actor_id)) and not db.scalar(select(StockDocument.id).where(StockDocument.posted_by_user_id==actor_id))


def verify(db: Session, lesson: Lesson, mode: str, business_actions=()) -> tuple[bool, dict]:
    v = values(lesson, mode)
    if lesson.workflow.startswith("catalogue_"):
        return verify_catalogue(db,lesson,v,business_actions)
    if lesson.workflow.startswith("control_"):
        return verify_controls(db,lesson,v,business_actions)
    if lesson.workflow.startswith("procurement_"):
        return verify_procurement(db,lesson,v,business_actions)
    if lesson.workflow.startswith("food_"):
        return verify_food(db,lesson,v,business_actions)
    if lesson.workflow.startswith("property_"):
        return verify_property(db,lesson,v,business_actions)
    if lesson.workflow.startswith("connected_"):
        return verify_connected(db,lesson,v,business_actions)
    if lesson.workflow.startswith("capstone_"):
        return verify_capstone(db,lesson,v,business_actions)
    q = Decimal(v["quantity"])
    start = Decimal(v["base"])
    workflow = lesson.workflow
    actual = balance(db, "amenities" if lesson.id=="housekeeping-supplies" else "chicken")
    result = {"physical_quantity": str(actual), "workflow": workflow}
    if workflow in {"issue", "receipt", "transfer"}:
        docs = list(db.scalars(select(StockDocument).where(StockDocument.posted_by_user_id == IDS["actor"], StockDocument.document_type == workflow)).all())
        expected = start + q if workflow == "receipt" else start - q
        exact = len(docs) == 1 and len(docs[0].movements) == (2 if workflow == "transfer" else 1)
        movement_item = v["practice_item"]
        expected_cost=Decimal(50) if lesson.id=="housekeeping-supplies" else Decimal(200)
        actor_documents=list(db.scalars(select(StockDocument).where(StockDocument.posted_by_user_id==IDS["actor"])).all())
        ok = exact and len(actor_documents)==1 and actual == expected and all(movement.item_id == movement_item and Decimal(movement.unit_cost)==expected_cost for movement in docs[0].movements) and sum((Decimal(movement.quantity) for movement in docs[0].movements if movement.location_id == IDS["store"]), Decimal(0)) == (q if workflow == "receipt" else -q)
        if workflow=="receipt" and not ok:
            result["correction"]="Record only the starting quantity in the situation, at PHP 200 per kg. Unit cost is the price of one kg, not zero or the total value. Reset this practice if an incorrect opening transaction was already posted."
        if workflow == "transfer":
            ok = ok and balance(db, location="kitchen") == q
        result.update(expected_quantity=str(expected), document_ids=[doc.id for doc in docs])
    elif workflow == "receiving":
        receipts = list(db.scalars(select(GoodsReceipt).where(GoodsReceipt.received_by_user_id == IDS["actor"])).all())
        prior = Decimal(10) - q if lesson.id == "later-delivery" else Decimal(0)
        expected = start + prior + q - v["rejected"]
        po = db.get(PurchaseOrder, IDS["po"])
        lines = receipts[0].lines if len(receipts) == 1 else []
        ok = len(lines) == 1 and receipts[0].purchase_order_id == IDS["po"] and receipts[0].delivery_reference == v["reference"] and Decimal(lines[0].received_quantity) == q and Decimal(lines[0].rejected_quantity) == v["rejected"] and actual == expected and Decimal(po.lines[0].received_quantity) == prior + q
        result.update(expected_quantity=str(expected), purchase_order_status=po.status, received_quantity=str(po.lines[0].received_quantity), receipt_ids=[row.id for row in receipts])
        if not ok:
            result["correction"] = f"This situation has {q} kg arrived and {v['rejected']} kg rejected. Record the actual delivery, not the original order quantity. " + ("No delivery is posted yet. Finish the confirmation." if not receipts else "The posted receipt does not match. Reset this practice and record only the goods in the situation.")
    elif workflow in {"count", "approve_count"}:
        count = db.get(CountSession, IDS["count"])
        expected_status = "posted" if workflow == "approve_count" or q == start else "pending_approval"
        ok = count.status == expected_status and count.lines[0].counted_quantity == q and actual == (q if count.status == "posted" else start)
        if workflow == "approve_count":
            ok = ok and count.approved_by_user_id == IDS["actor"] and count.created_by_user_id != IDS["actor"] and bool(count.posted_document_id)
        result.update(count_status=count.status, counted_quantity=str(count.lines[0].counted_quantity))
        if workflow == "count" and count.status != "posted":
            result["physical_quantity"] = None  # Never leak a blind snapshot through assessment evidence.
        if not ok:
            result["correction"] = f"Your physical count in this situation is {q} kg. Enter and save that number, then submit all saved lines. Do not try to match hidden stock."
    elif workflow == "return":
        returns = list(db.scalars(select(PurchaseReturn).where(PurchaseReturn.created_by_user_id == IDS["actor"])).all())
        ok = len(returns) == 1 and returns[0].purchase_order_id == IDS["po"] and balance(db) == start + 10 - q and db.get(PurchaseOrder, IDS["po"]).lines[0].returned_quantity == q
    elif workflow == "waste":
        docs = list(db.scalars(select(StockDocument).where(StockDocument.posted_by_user_id == IDS["actor"], StockDocument.document_type.in_(["waste", "spoilage"]))).all())
        ok = len(docs) == 1 and actual == start - q and len(docs[0].movements) == 1 and docs[0].movements[0].reason == "spoilage"
    elif workflow == "purchase_order":
        rows = list(db.scalars(select(PurchaseOrder).where(PurchaseOrder.created_by_user_id == IDS["actor"])).all())
        ok = len(rows) == 1 and rows[0].supplier_id == IDS["supplier"] and rows[0].delivery_location_id == IDS["store"] and rows[0].status == "draft" and len(rows[0].lines) == 1 and rows[0].lines[0].item_id == IDS["chicken"] and rows[0].lines[0].ordered_quantity == q and rows[0].lines[0].unit_price == 200 and actual == start
    elif workflow == "approve_po":
        po = db.get(PurchaseOrder, IDS["po"])
        ok = po.status == "approved" and po.approved_by_user_id == IDS["actor"] and po.created_by_user_id != IDS["actor"] and actual == start
    elif workflow == "requisition":
        rows = list(db.scalars(select(PurchaseRequisition).where(PurchaseRequisition.requested_by_user_id == IDS["actor"])).all())
        ok = len(rows) == 1 and rows[0].location_id == IDS["store"] and rows[0].status == "submitted" and len(rows[0].lines) == 1 and rows[0].lines[0].item_id == IDS["chicken"] and rows[0].lines[0].quantity == q and actual == start
    elif workflow == "staff_meal":
        rows = list(db.scalars(select(StaffMeal).where(StaffMeal.created_by_user_id == IDS["actor"])).all())
        ok = len(rows) == 1 and rows[0].status == "posted" and rows[0].location_id == IDS["store"] and len(rows[0].lines) == 1 and rows[0].lines[0].item_id == IDS["chicken"] and rows[0].lines[0].quantity == q and actual == start - q
    elif workflow == "production":
        batch = db.get(ProductionBatch, IDS["batch"])
        ok = batch.status == "completed" and batch.actual_quantity == q and bool(batch.stock_document_id) and balance(db, "alfredo") == q and actual == start - Decimal(3)
    else:
        return False, {"message": "This reading exercise also needs a record inspection answer."}
    result["passed"] = bool(ok)
    return bool(ok), result


def recover_checkpoint(db: Session, lesson: Lesson, mode: str, checkpoint: int, business_actions=()) -> int:
    """Recover a lost guide acknowledgement from committed business state.

    A browser can close after Save commits but before its checkpoint request
    arrives. Never leave the trainee pointing at a disabled Save button.
    """
    if lesson.workflow.startswith("capstone_"):
        return recover_capstone_checkpoint(db,lesson,values(lesson,mode),checkpoint,business_actions)
    if lesson.workflow.startswith("control_"):
        return recover_control_checkpoint(db,lesson,values(lesson,mode),checkpoint,business_actions)
    if lesson.workflow == "count":
        count = db.get(CountSession, IDS["count"])
        quantity = Decimal(values(lesson, mode)["quantity"])
        if count and all(line.counted_quantity == quantity for line in count.lines):
            if count.status in {"pending_approval", "posted"}: return len(lesson.steps)
            if count.status == "open": return max(checkpoint, 2)
    if not lesson.workflow.startswith("read_"):
        passed, _ = verify(db, lesson, mode,business_actions)
        if passed: return len(lesson.steps)
        # These real forms persist an attempt-scoped browser draft. The guide
        # validates its acknowledged fields before restoring this checkpoint.
        if lesson.id in {"create-item","create-supplier"}: return checkpoint
        # Receiving has an attempt-scoped browser draft. Other unposted forms
        # restart their guide rather than pointing at empty/disabled controls.
        if lesson.workflow != "receiving": return 0
    return checkpoint


def resolve_practice_route(db,lesson,mode):
    if lesson.workflow.startswith("capstone_"):return resolve_capstone_route(db,lesson,values(lesson,mode))
    return resolve_control_route(db,lesson,values(lesson,mode))


def public_lesson(lesson: Lesson, mode="guided"):
    v = values(lesson, mode)
    row = asdict(lesson)
    row["curriculum_version"] = VERSION
    row.pop("answer")
    row["situation"] = lesson.situation.format(**v)
    row["route"] = lesson.route.format(**v)
    row["quantity"] = v["quantity"]
    row["rejected"] = v["rejected"]
    row["reference"] = v["reference"]
    row["steps"] = [{**asdict(step), "instruction": step.instruction.format(**v), "value": (step.value.format(**v) if step.value and "{" in step.value else step.value)} for step in lesson.steps]
    row["practical_question"], _, row["inspection_route"] = practical_question(lesson, mode)
    row["inspection_api_path"] = inspection_endpoint(lesson) if lesson.workflow.startswith("read_") else None
    return row
