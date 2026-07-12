from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.api.integration_auth import integration_token_header, require_integration_token
from app.db.session import get_db
from app.models.operations import IntegrationEvent
from app.models.user import User
from app.services.controls import add_audit, add_notification, enqueue_event

router = APIRouter(tags=["operational-integrations"])
ALLOWED_SOURCES = {"staff", "command-center"}
ALLOWED_REQUEST_TYPES = {"stock_request", "count_request", "purchase_request", "transfer_request", "issue_report", "approval_request"}
ALLOWED_PRIORITIES = {"low", "normal", "high", "urgent"}
ALLOWED_DECISIONS = {"accepted", "rejected", "completed"}


def utcnow(): return datetime.now(timezone.utc)
def fail(status: int, message: str): raise HTTPException(status, message)


class OperationalRequestIn(BaseModel):
    source_system: str
    external_request_id: str = Field(min_length=1, max_length=120)
    requester_user_id: str
    department: str = Field(min_length=1, max_length=100)
    request_type: str
    title: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    priority: str = "normal"
    related_entity_type: str | None = Field(default=None, max_length=80)
    related_entity_id: str | None = Field(default=None, max_length=100)


class OperationalDecision(BaseModel):
    decision: str
    assigned_to_user_id: str | None = None
    notes: str | None = Field(default=None, max_length=2000)


def request_row(event: IntegrationEvent, db: Session) -> dict:
    payload = event.payload or {}
    requester = db.get(User, payload.get("requester_user_id")) if payload.get("requester_user_id") else None
    assignee = db.get(User, payload.get("assigned_to_user_id")) if payload.get("assigned_to_user_id") else None
    return {"id":event.id,"source_system":event.source_system,"external_request_id":payload.get("external_request_id"),"requester_user_id":payload.get("requester_user_id"),"requester_name":requester.full_name if requester else "Unknown identity","department":payload.get("department"),"request_type":payload.get("request_type"),"title":payload.get("title"),"description":payload.get("description"),"priority":payload.get("priority","normal"),"workflow_status":payload.get("workflow_status","submitted"),"assigned_to_user_id":payload.get("assigned_to_user_id"),"assigned_to_name":assignee.full_name if assignee else None,"decision_notes":payload.get("decision_notes"),"related_entity_type":payload.get("related_entity_type"),"related_entity_id":payload.get("related_entity_id"),"created_at":event.created_at,"updated_at":payload.get("updated_at")}


def summary(rows: list[dict]) -> dict:
    counts={name:sum(1 for row in rows if row["workflow_status"]==name) for name in ("submitted","accepted","rejected","completed")}
    return {**counts,"urgent":sum(1 for row in rows if row["priority"]=="urgent" and row["workflow_status"] not in {"rejected","completed"}),"staff_requests":sum(1 for row in rows if row["source_system"]=="staff"),"command_center_requests":sum(1 for row in rows if row["source_system"]=="command-center")}


@router.post("/integrations/operations/requests", status_code=201)
def receive_operational_request(payload: OperationalRequestIn, token: str | None = Depends(integration_token_header), db: Session = Depends(get_db)):
    if payload.source_system not in ALLOWED_SOURCES: fail(422,"Operational requests must originate from Staff or Command Center")
    require_integration_token(payload.source_system,token)
    if payload.request_type not in ALLOWED_REQUEST_TYPES: fail(422,"Unsupported operational request type")
    if payload.priority not in ALLOWED_PRIORITIES: fail(422,"Unsupported priority")
    requester=db.get(User,payload.requester_user_id)
    if not requester or not requester.is_active: fail(422,"Requester must resolve to an active canonical identity")
    key=f"operational-request:{payload.source_system}:{payload.external_request_id}"
    existing=db.scalar(select(IntegrationEvent).where(IntegrationEvent.idempotency_key==key))
    if existing:return request_row(existing,db)
    row=IntegrationEvent(direction="inbound",source_system=payload.source_system,destination_system="inventory",event_type="operations.request.submitted",aggregate_type="operational_request",aggregate_id=payload.external_request_id,idempotency_key=key,payload={**payload.model_dump(),"workflow_status":"submitted","updated_at":utcnow().isoformat()},status="completed",processed_at=utcnow())
    db.add(row);db.flush()
    add_audit(db,actor_user_id=None,action="operations.request_received",entity_type="integration_event",entity_id=row.id,details={"source_system":payload.source_system,"request_type":payload.request_type,"requester_user_id":payload.requester_user_id})
    recipients=db.scalars(select(User).where(User.is_active.is_(True),User.role.in_(["owner","inventory_manager","procurement_manager"]))).all()
    for recipient in recipients:add_notification(db,title="New operational request",message=f"{requester.full_name}: {payload.title}",severity="warning" if payload.priority in {"high","urgent"} else "info",user_id=recipient.id)
    db.commit();return request_row(row,db)


@router.get("/integrations/operations/workspace")
def operational_workspace(status:str|None=None,limit:int=Query(200,ge=1,le=500),db:Session=Depends(get_db),_:User=Depends(require_permission("integrations.read"))):
    events=db.scalars(select(IntegrationEvent).where(IntegrationEvent.direction=="inbound",IntegrationEvent.event_type=="operations.request.submitted",IntegrationEvent.source_system.in_(ALLOWED_SOURCES)).order_by(IntegrationEvent.created_at.desc()).limit(limit)).all()
    all_rows=[request_row(event,db) for event in events];filtered=[row for row in all_rows if not status or row["workflow_status"]==status]
    return {"summary":summary(all_rows),"filtered_summary":summary(filtered),"requests":filtered}


@router.post("/integrations/operations/requests/{event_id}/decision")
def decide_operational_request(event_id:str,payload:OperationalDecision,db:Session=Depends(get_db),user:User=Depends(require_permission("integrations.*"))):
    if payload.decision not in ALLOWED_DECISIONS:fail(422,"Decision must be accepted, rejected, or completed")
    event=db.scalar(select(IntegrationEvent).where(IntegrationEvent.id==event_id,IntegrationEvent.event_type=="operations.request.submitted").with_for_update())
    if not event:fail(404,"Operational request not found")
    data=dict(event.payload or {});current=data.get("workflow_status","submitted");allowed={"submitted":{"accepted","rejected"},"accepted":{"completed","rejected"}}
    if payload.decision not in allowed.get(current,set()):fail(409,f"Cannot move request from {current} to {payload.decision}")
    assignee=None
    if payload.assigned_to_user_id:
        assignee=db.get(User,payload.assigned_to_user_id)
        if not assignee or not assignee.is_active:fail(422,"Assignee must resolve to an active canonical identity")
    if payload.decision=="accepted" and not payload.assigned_to_user_id:fail(422,"Accepted requests require an assignee")
    data.update({"workflow_status":payload.decision,"assigned_to_user_id":payload.assigned_to_user_id or data.get("assigned_to_user_id"),"decision_notes":payload.notes,"decided_by_user_id":user.id,"updated_at":utcnow().isoformat()});event.payload=data
    outbound=enqueue_event(db,destination_system=event.source_system,event_type="inventory.operations.request_status_changed",aggregate_type="operational_request",aggregate_id=event.aggregate_id,idempotency_key=f"operations-status:{event.id}:{payload.decision}",payload={"inventory_event_id":event.id,"external_request_id":data.get("external_request_id"),"workflow_status":payload.decision,"assigned_to_user_id":data.get("assigned_to_user_id"),"decision_notes":payload.notes,"updated_at":data["updated_at"]})
    add_audit(db,actor_user_id=user.id,action=f"operations.request_{payload.decision}",entity_type="integration_event",entity_id=event.id,details={"assigned_to_user_id":data.get("assigned_to_user_id"),"source_system":event.source_system,"outbound_event_id":outbound.id})
    if assignee:add_notification(db,title="Operational request assigned",message=data.get("title") or "Operational request",severity="info",user_id=assignee.id)
    db.commit();return request_row(event,db)
