from pydantic import BaseModel


class EmployeeResponse(BaseModel):
    id: int
    company_id: int
    full_name: str
    role: str

    model_config = {
        "from_attributes": True
    }
