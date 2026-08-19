from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.session import SessionLocal
from app.models.company import Company
from app.models.user import User
from app.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate


router = APIRouter(
    prefix="/companies",
    tags=["Companies"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=CompanyResponse)
def create_company(
    company_data: CompanyCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    existing_company = (
        db.query(Company)
        .filter(Company.name == company_data.name)
        .first()
    )

    if existing_company:
        raise HTTPException(
            status_code=400,
            detail="Company already exists",
        )

    company = Company(
        name=company_data.name,
        is_active=True,
    )

    db.add(company)
    db.commit()
    db.refresh(company)

    return company


@router.get("/", response_model=list[CompanyResponse])
def get_companies(db: Session = Depends(get_db)):
    return db.query(Company).all()


@router.patch("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: int,
    company_data: CompanyUpdate,
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(Company.id == company_id).first()

    if not company:
        raise HTTPException(
            status_code=404,
            detail="Company not found",
        )

    updates = company_data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(company, field, value)

    db.commit()
    db.refresh(company)

    return company