import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models import Category, Department, User, UserRole, Vendor
from app.schemas import (
    CategoryCreate,
    CategoryOut,
    DepartmentCreate,
    DepartmentOut,
    VendorCategoriesUpdate,
    VendorCreate,
    VendorOut,
)

router = APIRouter(prefix="/api/master-data", tags=["master-data"])
logger = logging.getLogger("procureflow.master_data")


def _resolve_categories(db: Session, category_ids: list[str]) -> list[Category]:
    unique_ids = list(dict.fromkeys(category_ids))
    if not unique_ids:
        return []
    categories = db.query(Category).filter(Category.id.in_(unique_ids)).all()
    if len(categories) != len(unique_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category_ids")
    return categories


# ---------- Departments ----------


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    include_inactive: bool = Query(default=False),
):
    query = db.query(Department)
    if not include_inactive:
        query = query.filter(Department.is_active.is_(True))
    return query.order_by(Department.is_active.desc(), Department.name).all()


@router.post("/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    existing = db.query(Department).filter(Department.name == payload.name).first()
    if existing is not None:
        if existing.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Department already exists")
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing
    dept = Department(name=payload.name)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    logger.info("Department %s created by %s", dept.name, admin.email)
    return dept


@router.delete("/departments/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_department(
    department_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    dept = db.query(Department).filter(Department.id == department_id).first()
    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    dept.is_active = False
    db.commit()
    logger.info("Department %s deactivated by %s", dept.name, admin.email)


@router.post("/departments/{department_id}/reactivate", response_model=DepartmentOut)
def reactivate_department(
    department_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    dept = db.query(Department).filter(Department.id == department_id).first()
    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    dept.is_active = True
    db.commit()
    db.refresh(dept)
    logger.info("Department %s reactivated by %s", dept.name, admin.email)
    return dept


# ---------- Categories ----------


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    include_inactive: bool = Query(default=False),
):
    query = db.query(Category)
    if not include_inactive:
        query = query.filter(Category.is_active.is_(True))
    return query.order_by(Category.is_active.desc(), Category.name).all()


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    existing = db.query(Category).filter(Category.name == payload.name).first()
    if existing is not None:
        if existing.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category already exists")
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing
    category = Category(name=payload.name)
    db.add(category)
    db.commit()
    db.refresh(category)
    logger.info("Category %s created by %s", category.name, admin.email)
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_category(
    category_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    category.is_active = False
    db.commit()
    logger.info("Category %s deactivated by %s", category.name, admin.email)


@router.post("/categories/{category_id}/reactivate", response_model=CategoryOut)
def reactivate_category(
    category_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    category.is_active = True
    db.commit()
    db.refresh(category)
    logger.info("Category %s reactivated by %s", category.name, admin.email)
    return category


# ---------- Vendors ----------


@router.get("/vendors", response_model=list[VendorOut])
def list_vendors(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    include_inactive: bool = Query(default=False),
    category_id: Optional[str] = Query(default=None),
):
    query = db.query(Vendor).options(selectinload(Vendor.categories))
    if not include_inactive:
        query = query.filter(Vendor.is_active.is_(True))
    if category_id:
        query = query.filter(Vendor.categories.any(Category.id == category_id))
    return query.order_by(Vendor.is_active.desc(), Vendor.name).all()


@router.post("/vendors", response_model=VendorOut, status_code=status.HTTP_201_CREATED)
def create_vendor(
    payload: VendorCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    categories = _resolve_categories(db, payload.category_ids)
    vendor = Vendor(**payload.model_dump(exclude={"category_ids"}))
    vendor.categories = categories
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    logger.info("Vendor %s created by %s", vendor.name, admin.email)
    return vendor


@router.put("/vendors/{vendor_id}/categories", response_model=VendorOut)
def set_vendor_categories(
    vendor_id: str,
    payload: VendorCategoriesUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if vendor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")
    vendor.categories = _resolve_categories(db, payload.category_ids)
    db.commit()
    db.refresh(vendor)
    logger.info("Vendor %s categories set by %s", vendor.name, admin.email)
    return vendor


@router.delete("/vendors/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_vendor(
    vendor_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if vendor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")
    vendor.is_active = False
    db.commit()
    logger.info("Vendor %s deactivated by %s", vendor.name, admin.email)


@router.post("/vendors/{vendor_id}/reactivate", response_model=VendorOut)
def reactivate_vendor(
    vendor_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if vendor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")
    vendor.is_active = True
    db.commit()
    db.refresh(vendor)
    logger.info("Vendor %s reactivated by %s", vendor.name, admin.email)
    return vendor
