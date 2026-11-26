"""Restricted fixtures and read-only assessment of source-backed controls."""
from decimal import Decimal
from sqlalchemy import select
from app.models import User, OperationalAccessScope, OperationalDimension, Item, StockBalance, StockDocument, AuditLog
from app.models.classification import ItemWorkspaceAssignment
from app.models.operations import Notification, NotificationRead, BackupRecord
from app.models.pass5 import AccountingMapping
from app.models.pass6 import SavedView
from app.models.readiness import AcceptanceRun
from app.models.stabilization import StaffFeedback, OperationalIncident
from app.core.security import hash_password


def admin_values(mode):return {"scope_limit":{"guided":1000,"assisted":2000,"independent":3000}[mode]}


def prepare_admin(db,lesson,v):
    if lesson.id=="assign-location-approval-scope":
        db.add(User(id=v['purchaser'],email="training-purchaser@example.com",full_name="Training purchasing colleague",role="procurement_officer",password_hash=hash_password("unusable-training-password")))
    elif lesson.id=="retire-unused-classification":
        db.add(OperationalDimension(id="training-old-department",dimension_type="department",code="train-old-outlet",name="Training old outlet",workspace_id=v['fnb'],is_system=False,is_active=True))
    elif lesson.id=="acknowledge-operational-alert":
        db.add(Notification(id="training-review-alert",user_id=v['actor'],title="TRAIN-REVIEW-ALERT",message="Ask the supervisor to investigate the stock discrepancy; reading this message does not correct stock.",severity="warning"))
    elif lesson.id=="resolve-verified-feedback":
        db.add(StaffFeedback(id="training-feedback",category="usability",severity="normal",page="/counts",message="Training verified readability fix",status="open",submitted_by_user_id=v['colleague']))
    elif lesson.id=="resolve-verified-incident":
        db.add(OperationalIncident(id="training-incident",incident_number="TRAIN-INCIDENT",source="training-workstation",severity="warning",title="Training connection interruption",details="The colleague verified original documents after reconnecting.",status="open",created_by_user_id=v['colleague']))


def after_prepare_admin(db,lesson,v):
    if lesson.id=="resolve-verified-incident":
        # Establish the stated recovery precondition through the real source
        # document reader. This is connection recovery, never a backup claim.
        from app.api.routes.stock_ledger import stock_document_detail
        document=db.scalar(select(StockDocument).where(StockDocument.reference=="Synthetic opening stock"))
        result=stock_document_detail(document.id,db,db.get(User,v['colleague']))
        assert result
        incident=db.get(OperationalIncident,"training-incident")
        incident.metadata_json={"verified_document":document.id,"verification":"source_detail_loaded"}
        db.commit()


def verify_admin(db,lesson,v,actions):
    id=lesson.id
    documents=list(db.scalars(select(StockDocument).where(StockDocument.posted_by_user_id==v['actor'])))
    def balance(item):return db.scalar(select(StockBalance.quantity).where(StockBalance.item_id==item,StockBalance.location_id==v['store'])) or Decimal(0)
    untouched=not documents and balance(v['chicken'])==v['base'] and balance(v['amenities'])==v['base'] and balance(v['alfredo'])==0
    def audit(action,entity=None):
        query=select(AuditLog).where(AuditLog.actor_user_id==v['actor'],AuditLog.action==action)
        if entity is not None:query=query.where(AuditLog.entity_id==entity)
        return db.scalar(query)
    ok=False
    if id=="assign-location-approval-scope":
        rows=list(db.scalars(select(OperationalAccessScope).where(OperationalAccessScope.user_id==v['purchaser'])))
        ok=len(rows)==1 and rows[0].location_id==v['store'] and rows[0].approval_limit==v['scope_limit'] and rows[0].is_active and rows[0].workspace_id is None and rows[0].department_id is None and rows[0].record_class_id is None and db.get(User,v['purchaser']).role=="procurement_officer" and audit("access.scope_created",rows[0].id)
    elif id=="create-operating-department":
        row=db.scalar(select(OperationalDimension).where(OperationalDimension.dimension_type=="department",OperationalDimension.code=="train-cafe"))
        ok=row and row.name=="Training café outlet" and row.workspace_id==v['fnb'] and row.behavior_key is None and row.parent_id is None and row.sort_order==0 and row.is_active and not row.is_system and audit("classification.dimension_created",row.id)
    elif id=="retire-unused-classification":
        row=db.get(OperationalDimension,"training-old-department")
        ok=not row.is_active and row.code=="train-old-outlet" and row.name=="Training old outlet" and row.workspace_id==v['fnb'] and audit("classification.dimension_updated",row.id)
    elif id=="classify-legacy-ingredient":
        row=db.get(Item,v['chicken']);type=db.get(OperationalDimension,v['ingredient'])
        assignments=list(db.scalars(select(ItemWorkspaceAssignment).where(ItemWorkspaceAssignment.item_id==row.id)))
        ok=row.primary_workspace_id==v['fnb'] and row.item_type_id==type.id and row.record_class_id==type.parent_id and row.department_id is None and row.cost_center_id is None and row.base_unit_id==v['kg'] and row.sku=="TRAIN-CHICKEN" and len(assignments)==1 and assignments[0].workspace_id==v['fnb'] and assignments[0].is_primary and audit("item.classification_updated",row.id)
    elif id=="create-accounting-mapping":
        rows=list(db.scalars(select(AccountingMapping)))
        ok=len(rows)==1 and rows[0].event_key=="inventory.stock_document.posted" and rows[0].debit_account=="TRAIN-INVENTORY" and rows[0].credit_account=="TRAIN-CLEARING" and rows[0].description=="Training reviewer-approved mapping" and rows[0].is_active
    elif id=="save-report-scope":
        rows=list(db.scalars(select(SavedView).where(SavedView.user_id==v['actor'])))
        ok=len(rows)==1 and rows[0].name=="Training F&B review" and rows[0].module_key=="operating-summary" and rows[0].filters=={"workspace_id":v['fnb']} and rows[0].columns==["stock_value","reusable_units","net_fixed_assets","overdue_maintenance"] and not rows[0].is_default
    elif id=="acknowledge-operational-alert":
        reads=list(db.scalars(select(NotificationRead).where(NotificationRead.user_id==v['actor'])))
        ok=len(reads)==1 and reads[0].notification_id=="training-review-alert" and audit("notification.read","training-review-alert")
    elif id=="submit-workflow-feedback":
        rows=list(db.scalars(select(StaffFeedback).where(StaffFeedback.submitted_by_user_id==v['actor'])))
        ok=len(rows)==1 and rows[0].message=="Training: count field difficult to read on phone" and rows[0].category=="usability" and rows[0].severity=="normal" and rows[0].page=="/counts" and rows[0].status=="open" and audit("feedback.submitted",rows[0].id)
    elif id=="resolve-verified-feedback":
        row=db.get(StaffFeedback,"training-feedback")
        ok=row.status=="resolved" and row.resolved_at is not None and row.message=="Training verified readability fix" and row.submitted_by_user_id==v['colleague'] and audit("feedback.updated",row.id)
    elif id=="resolve-verified-incident":
        row=db.get(OperationalIncident,"training-incident")
        document=db.get(StockDocument,row.metadata_json.get("verified_document"))
        ok=row.status=="resolved" and row.resolved_at is not None and row.created_by_user_id==v['colleague'] and document and document.reference=="Synthetic opening stock" and row.metadata_json.get("verification")=="source_detail_loaded" and audit("incident.updated",row.id)
    elif id=="record-assurance-review":
        row=audit("assurance.snapshot_recorded")
        details=row.details if row else {}
        backup=next((check for check in details.get('checks',[]) if check['key']=='backup'),{})
        ok=details.get('overall_status')=='critical' and details.get('summary',{}).get('stock_mismatches')==0 and backup.get('status')=='failed' and backup.get('count')==1 and not db.scalar(select(BackupRecord.id))
    elif id=="run-isolated-acceptance":
        rows=list(db.scalars(select(AcceptanceRun).where(AcceptanceRun.created_by_user_id==v['actor'])))
        ok=len(rows)==1 and rows[0].status=='failed' and rows[0].completed_at is not None and rows[0].results.get('database',{}).get('passed') is True and rows[0].results.get('stock_reconciliation',{}).get('passed') is True and rows[0].results.get('backup',{}).get('passed') is False and audit('acceptance.completed',rows[0].id) and not db.scalar(select(BackupRecord.id))
    elif id=="check-isolated-rollout":
        ok=any(action.get('method')=='POST' and action.get('path')=='/api/v1/rollout/smoke-test' and action.get('status')==200 for action in actions) and not db.scalar(select(BackupRecord.id))
    passed=bool(ok and untouched)
    return passed,{"workflow":lesson.workflow,"passed":passed,"stock_integrity":bool(untouched),"correction":lesson.situation.format(**v)+" Check the real saved record and keep its exceptions and original business evidence. Reset practice if an unintended stock posting was made."}
