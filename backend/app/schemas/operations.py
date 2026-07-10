from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
class ORMModel(BaseModel): model_config=ConfigDict(from_attributes=True)
class NotificationOut(ORMModel):
    id:str; user_id:str|None; title:str; message:str; severity:str; is_read:bool; created_at:datetime
class IntegrationEventCreate(BaseModel):
    direction:str=Field(pattern='^(inbound|outbound)$'); source_system:str; destination_system:str; event_type:str; aggregate_type:str; aggregate_id:str; idempotency_key:str; payload:dict
class IntegrationEventOut(ORMModel):
    id:str; direction:str; source_system:str; destination_system:str; event_type:str; aggregate_type:str; aggregate_id:str; idempotency_key:str; payload:dict; status:str; attempts:int; last_error:str|None; available_at:datetime; processed_at:datetime|None; created_at:datetime
class BackupOut(ORMModel):
    id:str; filename:str; status:str; size_bytes:int; checksum_sha256:str|None; created_by_user_id:str|None; created_at:datetime
class AuditOut(ORMModel):
    id:str; actor_user_id:str|None; action:str; entity_type:str; entity_id:str|None; details:dict; request_id:str|None; ip_address:str|None; created_at:datetime
class PageMeta(BaseModel): total:int; limit:int; offset:int
class PaginatedItems(BaseModel): items:list[dict]; meta:PageMeta
