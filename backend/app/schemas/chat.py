from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    company_id: int
    user_id: int
    conversation_id: Optional[int] = None
    message: str


class ChatResponse(BaseModel):
    conversation_id: int
    reply: str


class MessageResponse(BaseModel):
    id: int
    sender_type: str
    agent_id: Optional[int]
    content: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
