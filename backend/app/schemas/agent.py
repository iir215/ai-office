from typing import Optional

from pydantic import BaseModel


class AgentCreate(BaseModel):
    company_id: int
    name: str
    system_prompt: str
    notify_owner: bool = False
    is_security_auditor: bool = False
    can_publish_instagram: bool = False
    handles_instagram_support: bool = False


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    notify_owner: Optional[bool] = None
    is_security_auditor: Optional[bool] = None
    can_publish_instagram: Optional[bool] = None
    handles_instagram_support: Optional[bool] = None
    is_active: Optional[bool] = None


class AgentResponse(BaseModel):
    id: int
    company_id: int
    name: str
    role_type: str
    status: str
    is_active: bool
    notify_owner: bool
    is_security_auditor: bool
    can_publish_instagram: bool
    handles_instagram_support: bool

    model_config = {
        "from_attributes": True
    }
