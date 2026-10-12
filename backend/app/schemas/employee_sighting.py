from datetime import datetime

from pydantic import BaseModel


class SightingResponse(BaseModel):
    id: int
    employee_id: int
    comment: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
