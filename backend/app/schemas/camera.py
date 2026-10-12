from pydantic import BaseModel


class CameraResponse(BaseModel):
    id: int
    company_id: int
    name: str

    model_config = {
        "from_attributes": True
    }
