from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    company_id: int
    role_id: int
    full_name: str
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    company_id: int
    role_id: int
    full_name: str
    email: str
    is_active: bool

    model_config = {
        "from_attributes": True
    }
