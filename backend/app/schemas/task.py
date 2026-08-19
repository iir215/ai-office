from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TaskResponse(BaseModel):
    id: int
    company_id: int
    director_agent_id: int
    assigned_agent_id: int
    instructions: str
    status: str
    result: Optional[str]
    created_at: datetime
    finished_at: Optional[datetime]

    model_config = {
        "from_attributes": True
    }
