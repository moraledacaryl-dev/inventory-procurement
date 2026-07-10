from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class ORMModel(BaseModel): model_config=ConfigDict(from_attributes=True)
class ImportValidationOut(BaseModel): job_id:str; import_type:str; filename:str; status:str; summary:dict; errors:list
class ImportApplyOut(BaseModel): job_id:str; status:str; summary:dict; applied_at:datetime
class ImportJobOut(ORMModel): id:str; import_type:str; filename:str; status:str; summary:dict; errors:list; created_by_user_id:str; created_at:datetime; applied_at:datetime|None
class AcceptanceRunCreate(BaseModel): environment:str='production-candidate'; notes:str|None=None
class AcceptanceRunOut(ORMModel): id:str; run_number:str; environment:str; status:str; results:dict; notes:str|None; created_by_user_id:str; created_at:datetime; completed_at:datetime|None
class DeploymentStatusOut(BaseModel): environment:str; database:str; migrations:str; worker_backlog:int; dead_letter_events:int; latest_backup_at:datetime|None; backup_age_hours:float|None; status:str
class PrintableDocumentOut(BaseModel): document_type:str; document_number:str; status:str; title:str; header:dict; lines:list[dict]; totals:dict
