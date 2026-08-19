from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.agent import Agent
from app.models.company import Company
from app.schemas.agent import AgentCreate, AgentResponse, AgentUpdate


router = APIRouter(
    prefix="/agents",
    tags=["Agents"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=AgentResponse)
def create_agent(
    agent_data: AgentCreate,
    db: Session = Depends(get_db),
):
    company = (
        db.query(Company)
        .filter(Company.id == agent_data.company_id)
        .first()
    )

    if not company:
        raise HTTPException(
            status_code=404,
            detail="Company not found",
        )

    existing_agent = (
        db.query(Agent)
        .filter(Agent.company_id == agent_data.company_id)
        .filter(Agent.name == agent_data.name)
        .first()
    )

    if existing_agent:
        raise HTTPException(
            status_code=400,
            detail="Agent with this name already exists for this company",
        )

    agent = Agent(
        company_id=agent_data.company_id,
        name=agent_data.name,
        role_type="worker",
        system_prompt=agent_data.system_prompt,
        status="idle",
        is_active=True,
        notify_owner=agent_data.notify_owner,
        is_security_auditor=agent_data.is_security_auditor,
        can_publish_instagram=agent_data.can_publish_instagram,
        handles_instagram_support=agent_data.handles_instagram_support,
    )

    db.add(agent)
    db.commit()
    db.refresh(agent)

    return agent


@router.get("/", response_model=list[AgentResponse])
def get_agents(db: Session = Depends(get_db)):
    return db.query(Agent).all()


@router.patch("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: int,
    agent_data: AgentUpdate,
    db: Session = Depends(get_db),
):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()

    if not agent:
        raise HTTPException(
            status_code=404,
            detail="Agent not found",
        )

    updates = agent_data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(agent, field, value)

    db.commit()
    db.refresh(agent)

    return agent
