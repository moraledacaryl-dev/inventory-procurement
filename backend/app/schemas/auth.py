from pydantic import BaseModel, EmailStr, Field
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    model_config = {"from_attributes": True}
class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
