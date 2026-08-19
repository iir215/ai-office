import secrets

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_current_user, get_db
from app.core.security import create_access_token, verify_password
from app.models.allowed_email import AllowedEmail
from app.models.company import Company
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import LoginRequest, MeResponse, TokenResponse, WhitelistCreate, WhitelistResponse

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    allowed = (
        db.query(AllowedEmail)
        .filter(AllowedEmail.email.ilike(data.email))
        .first()
    )
    if not allowed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль")

    user = db.query(User).filter(User.email.ilike(data.email)).first()
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.id == user.role_id).first()
    role_name = role.name if role else "unknown"
    return MeResponse(
        id=user.id,
        company_id=user.company_id,
        full_name=user.full_name,
        email=user.email,
        role=role_name,
        is_admin=role_name == "admin",
    )


@router.get("/whitelist", response_model=list[WhitelistResponse])
def list_whitelist(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return db.query(AllowedEmail).order_by(AllowedEmail.id).all()


@router.post("/whitelist", response_model=WhitelistResponse)
def add_to_whitelist(
    data: WhitelistCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    existing = db.query(AllowedEmail).filter(AllowedEmail.email.ilike(data.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Этот email уже в белом списке")

    company = db.query(Company).filter(Company.id == data.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Компания не найдена")

    role = db.query(Role).filter(Role.id == data.role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Роль не найдена")

    user = db.query(User).filter(User.email.ilike(data.email)).first()
    generated_password = None

    if not user:
        generated_password = secrets.token_urlsafe(9)
        password_hash = bcrypt.hashpw(generated_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        user = User(
            company_id=data.company_id,
            role_id=data.role_id,
            full_name=data.full_name,
            email=data.email,
            password_hash=password_hash,
            is_active=True,
        )
        db.add(user)

    entry = AllowedEmail(email=data.email, added_by_user_id=admin.id)
    db.add(entry)

    try:
        db.commit()
        db.refresh(entry)
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Не удалось добавить email")

    return WhitelistResponse(
        id=entry.id,
        email=entry.email,
        user_id=user.id,
        generated_password=generated_password,
    )


@router.delete("/whitelist/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_whitelist(
    entry_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    entry = db.query(AllowedEmail).filter(AllowedEmail.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    db.delete(entry)
    db.commit()
