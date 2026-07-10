from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class ORMModel(BaseModel): model_config=ConfigDict(from_attributes=True)
class FeedbackCreate(BaseModel): category:str=Field(pattern='^(bug|usability|data|training|request)$'); severity:str=Field(default='normal',pattern='^(low|normal|high|critical)$'); page:str|None=None; message:str=Field(min_length=5,max_length=4000); context:dict={}
class FeedbackOut(ORMModel): id:str; category:str; severity:str; page:str|None; message:str; context:dict; status:str; submitted_by_user_id:str; assigned_to_user_id:str|None; created_at:datetime; resolved_at:datetime|None
class FeedbackUpdate(BaseModel): status:str=Field(pattern='^(open|reviewing|resolved|dismissed)$'); assigned_to_user_id:str|None=None
class IncidentCreate(BaseModel): source:str=Field(min_length=2,max_length=60); severity:str=Field(pattern='^(info|warning|error|critical)$'); title:str=Field(min_length=3,max_length=180); details:str=Field(min_length=3,max_length=4000); request_id:str|None=None; metadata_json:dict={}
class IncidentOut(ORMModel): id:str; incident_number:str; source:str; severity:str; title:str; details:str; request_id:str|None; status:str; metadata_json:dict; created_by_user_id:str|None; created_at:datetime; acknowledged_at:datetime|None; resolved_at:datetime|None
class IncidentUpdate(BaseModel): status:str=Field(pattern='^(open|acknowledged|resolved)$')
class RolloutSummary(BaseModel): open_feedback:int; high_priority_feedback:int; open_incidents:int; critical_incidents:int; failed_acceptance_runs:int; dead_letter_events:int; status:str
class SmokeTestResult(BaseModel): status:str; checks:dict
