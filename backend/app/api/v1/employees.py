import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_current_user, get_db
from app.models.employee import Employee
from app.models.employee_sighting import EmployeeSighting
from app.models.user import User
from app.schemas.employee import EmployeeResponse
from app.schemas.employee_sighting import SightingResponse

router = APIRouter(
    prefix="/employees",
    tags=["Employees"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
PHOTO_DIR = os.path.join(BASE_DIR, "employee_photos")
SIGHTING_PHOTO_DIR = os.path.join(BASE_DIR, "employee_sightings")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


@router.get("/", response_model=list[EmployeeResponse])
def list_employees(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return (
        db.query(Employee)
        .filter(Employee.company_id == admin.company_id)
        .order_by(Employee.id)
        .all()
    )


@router.post("/", response_model=EmployeeResponse)
def create_employee(
    full_name: str = Form(...),
    role: str = Form(...),
    photo: UploadFile = File(...),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    ext = os.path.splitext(photo.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Фото должно быть в формате JPG или PNG")

    os.makedirs(PHOTO_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(PHOTO_DIR, filename), "wb") as f:
        f.write(photo.file.read())

    employee = Employee(
        company_id=admin.company_id,
        full_name=full_name,
        role=role,
        photo_filename=filename,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)

    return employee


@router.get("/{employee_id}/photo")
def get_employee_photo(
    employee_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id)
        .filter(Employee.company_id == user.company_id)
        .first()
    )
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    path = os.path.join(PHOTO_DIR, employee.photo_filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Фото не найдено")

    return FileResponse(path)


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(
    employee_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id)
        .filter(Employee.company_id == admin.company_id)
        .first()
    )
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    sightings = db.query(EmployeeSighting).filter(EmployeeSighting.employee_id == employee.id).all()
    for sighting in sightings:
        sighting_path = os.path.join(SIGHTING_PHOTO_DIR, sighting.photo_filename)
        if os.path.exists(sighting_path):
            os.remove(sighting_path)
        db.delete(sighting)
    db.flush()

    photo_path = os.path.join(PHOTO_DIR, employee.photo_filename)
    if os.path.exists(photo_path):
        os.remove(photo_path)

    db.delete(employee)
    db.commit()


@router.get("/{employee_id}/sightings", response_model=list[SightingResponse])
def list_sightings(
    employee_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(EmployeeSighting)
        .filter(EmployeeSighting.employee_id == employee_id)
        .filter(EmployeeSighting.company_id == user.company_id)
        .order_by(EmployeeSighting.created_at.desc())
        .limit(50)
        .all()
    )


@router.post("/{employee_id}/sightings", response_model=SightingResponse)
def create_sighting(
    employee_id: int,
    comment: str = Form(...),
    photo: UploadFile = File(...),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id)
        .filter(Employee.company_id == admin.company_id)
        .first()
    )
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    ext = os.path.splitext(photo.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Фото должно быть в формате JPG или PNG")

    os.makedirs(SIGHTING_PHOTO_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(SIGHTING_PHOTO_DIR, filename), "wb") as f:
        f.write(photo.file.read())

    sighting = EmployeeSighting(
        employee_id=employee.id,
        company_id=admin.company_id,
        photo_filename=filename,
        comment=comment,
    )
    db.add(sighting)
    db.commit()
    db.refresh(sighting)

    return sighting


@router.get("/{employee_id}/sightings/{sighting_id}/photo")
def get_sighting_photo(
    employee_id: int,
    sighting_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sighting = (
        db.query(EmployeeSighting)
        .filter(EmployeeSighting.id == sighting_id)
        .filter(EmployeeSighting.employee_id == employee_id)
        .filter(EmployeeSighting.company_id == user.company_id)
        .first()
    )
    if not sighting:
        raise HTTPException(status_code=404, detail="Снимок не найден")

    path = os.path.join(SIGHTING_PHOTO_DIR, sighting.photo_filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Фото не найдено")

    return FileResponse(path)
