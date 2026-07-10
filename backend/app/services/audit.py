from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog

def record_audit(db: Session, *, actor_user_id: str | None, action: str, entity_type: str, entity_id: str | None = None, details: dict | None = None, request_id: str | None = None, ip_address: str | None = None) -> AuditLog:
    row = AuditLog(actor_user_id=actor_user_id, action=action, entity_type=entity_type, entity_id=entity_id, details=details or {}, request_id=request_id, ip_address=ip_address)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
