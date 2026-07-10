from pydantic import BaseModel
class ModuleStatus(BaseModel):
    module: str
    status: str = "framework_ready"
    pass_number: int = 1
    message: str
