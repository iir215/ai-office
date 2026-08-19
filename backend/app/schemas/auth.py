from typing import Optional

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: int
    company_id: int
    full_name: str
    email: str
    role: str
    is_admin: bool


class WhitelistCreate(BaseModel):
    email: EmailStr
    full_name: str
    company_id: int
    role_id: int


class WhitelistResponse(BaseModel):
    id: int
    email: str
    user_id: Optional[int] = None
    generated_password: Optional[str] = None

    model_config = {
        "from_attributes": True
    }
