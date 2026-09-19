from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models import (
    Category,
    Department,
    PRStatus,
    PRStatusHistory,
    PurchaseRequest,
    User,
    UserRole,
)
from app.schemas import (
    PaginatedPurchaseRequests,
    PRDecisionRequest,
    PRStatusHistoryOut,
    PurchaseRequestCreate,
    PurchaseRequestDetail,
    PurchaseRequestOut,
    PurchaseRequestUpdate,
)
from app.utils import assert_vendor_supplies_category, next_sequence_number

router = APIRouter(prefix="/api/purchase-requests", tags=["purchase-requests"])

EDITABLE_STATUSES = {PRStatus.DRAFT, PRStatus.REJECTED}


def _comparable(field: str, value):
    # Required dates are calendar dates and descriptions ignore surrounding spaces, so neither
    # a same-day timezone shift nor a trailing space counts as an edit.
    if field == "required_date":
        return value.replace(tzinfo=None).date()
    if field == "description":
        return value.strip()
    return value


def _differs(pr: "PurchaseRequest", field: str, new_value) -> bool:
    return _comparable(field, new_value) != _comparable(field, getattr(pr, field))


def _to_out(pr: PurchaseRequest) -> PurchaseRequestOut:
    return PurchaseRequestOut(
        id=pr.id,
        pr_number=pr.pr_number,
        requester_id=pr.requester_id,
        requester_name=pr.requester.name if pr.requester else None,
        department_id=pr.department_id,
        department_name=pr.department.name if pr.department else None,
        description=pr.description,
        category_id=pr.category_id,
        category_name=pr.category.name if pr.category else None,
        amount=pr.amount,
        currency=pr.currency,
        required_date=pr.required_date,
        vendor_id=pr.vendor_id,
        vendor_name=pr.vendor.name if pr.vendor else None,
        status=pr.status,
        revision_required=pr.revision_required,
        created_at=pr.created_at,
        updated_at=pr.updated_at,
    )


def _get_pr_or_404(db: Session, pr_id: str) -> PurchaseRequest:
    pr = db.query(PurchaseRequest).filter(PurchaseRequest.id == pr_id).first()
    if pr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase request not found")
    return pr


def _assert_can_view(pr: PurchaseRequest, user: User) -> None:
    if user.role == UserRole.REQUESTER and pr.requester_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this purchase request")


def _add_history(
    db: Session, pr: PurchaseRequest, to_status: PRStatus, user: User, comment: Optional[str], initial: bool = False
) -> None:
    db.add(
        PRStatusHistory(
            pr_id=pr.id,
            from_status=None if initial else pr.status,
            to_status=to_status,
            changed_by_id=user.id,
            comment=comment,
        )
    )


@router.post("", response_model=PurchaseRequestOut, status_code=status.HTTP_201_CREATED)
def create_purchase_request(
    payload: PurchaseRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.REQUESTER, UserRole.ADMIN)),
):
    if not db.query(Department).filter(Department.id == payload.department_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid department_id")
    if not db.query(Category).filter(Category.id == payload.category_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category_id")
    if payload.vendor_id:
        assert_vendor_supplies_category(db, payload.vendor_id, payload.category_id)

    pr = PurchaseRequest(
        pr_number=next_sequence_number(db, PurchaseRequest, PurchaseRequest.pr_number, "PR"),
        requester_id=current_user.id,
        department_id=payload.department_id,
        description=payload.description,
        category_id=payload.category_id,
        amount=payload.amount,
        currency=payload.currency,
        required_date=payload.required_date,
        vendor_id=payload.vendor_id,
        status=PRStatus.DRAFT,
    )
    db.add(pr)
    db.flush()
    _add_history(db, pr, PRStatus.DRAFT, current_user, "Purchase request created", initial=True)
    db.commit()
    db.refresh(pr)
    return _to_out(pr)


@router.get("", response_model=PaginatedPurchaseRequests)
def list_purchase_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: Optional[PRStatus] = Query(default=None, alias="status"),
    department_id: Optional[str] = None,
    category_id: Optional[str] = None,
    search: Optional[str] = None,
    mine: bool = False,
    awaiting_po: bool = False,
    sort_by: str = Query(default="created_at", pattern="^(created_at|amount|required_date|pr_number)$"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
):
    query = db.query(PurchaseRequest)

    if current_user.role == UserRole.REQUESTER or mine:
        query = query.filter(PurchaseRequest.requester_id == current_user.id)

    if status_filter is not None:
        query = query.filter(PurchaseRequest.status == status_filter)
    if awaiting_po:
        query = query.filter(~PurchaseRequest.purchase_orders.any())
    if department_id:
        query = query.filter(PurchaseRequest.department_id == department_id)
    if category_id:
        query = query.filter(PurchaseRequest.category_id == category_id)
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(PurchaseRequest.pr_number.ilike(like), PurchaseRequest.description.ilike(like))
        )

    total = query.count()

    sort_column = getattr(PurchaseRequest, sort_by)
    sort_column = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
    query = query.order_by(sort_column)

    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return PaginatedPurchaseRequests(
        items=[_to_out(pr) for pr in items], total=total, page=page, page_size=page_size
    )


@router.get("/{pr_id}", response_model=PurchaseRequestDetail)
def get_purchase_request(
    pr_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    pr = _get_pr_or_404(db, pr_id)
    _assert_can_view(pr, current_user)
    out = PurchaseRequestDetail(**_to_out(pr).model_dump())
    out.status_history = [
        PRStatusHistoryOut(
            id=h.id,
            from_status=h.from_status,
            to_status=h.to_status,
            changed_by_id=h.changed_by_id,
            changed_by_name=h.changed_by.name if h.changed_by else None,
            comment=h.comment,
            changed_at=h.changed_at,
        )
        for h in pr.status_history
    ]
    return out


@router.patch("/{pr_id}", response_model=PurchaseRequestOut)
def update_purchase_request(
    pr_id: str,
    payload: PurchaseRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pr = _get_pr_or_404(db, pr_id)
    if current_user.role == UserRole.REQUESTER and pr.requester_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to edit this purchase request")
    if pr.status not in EDITABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit a purchase request in status {pr.status.value}",
        )

    data = payload.model_dump(exclude_unset=True)
    changes = {field: value for field, value in data.items() if _differs(pr, field, value)}
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No changes to save")

    if "department_id" in changes and not db.query(Department).filter(Department.id == changes["department_id"]).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid department_id")
    if "category_id" in changes and not db.query(Category).filter(Category.id == changes["category_id"]).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category_id")
    if "vendor_id" in changes or "category_id" in changes:
        effective_vendor_id = changes["vendor_id"] if "vendor_id" in changes else pr.vendor_id
        effective_category_id = changes.get("category_id", pr.category_id)
        if effective_vendor_id:
            assert_vendor_supplies_category(db, effective_vendor_id, effective_category_id)

    for field, value in changes.items():
        setattr(pr, field, value.strip() if field == "description" else value)
    pr.revision_required = False

    db.commit()
    db.refresh(pr)
    return _to_out(pr)


@router.post("/{pr_id}/submit", response_model=PurchaseRequestOut)
def submit_purchase_request(
    pr_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    pr = _get_pr_or_404(db, pr_id)
    if current_user.role == UserRole.REQUESTER and pr.requester_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to submit this purchase request")
    if pr.status not in EDITABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit a purchase request in status {pr.status.value}",
        )
    if pr.status == PRStatus.REJECTED and pr.revision_required:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Update the purchase request to address the rejection before resubmitting",
        )

    _add_history(db, pr, PRStatus.SUBMITTED, current_user, "Submitted for approval")
    pr.status = PRStatus.SUBMITTED
    db.commit()
    db.refresh(pr)
    return _to_out(pr)


@router.post("/{pr_id}/approve", response_model=PurchaseRequestOut)
def approve_purchase_request(
    pr_id: str,
    payload: PRDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.APPROVER, UserRole.ADMIN)),
):
    pr = _get_pr_or_404(db, pr_id)
    if pr.status != PRStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve a purchase request in status {pr.status.value}",
        )
    if pr.requester_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Requesters cannot approve their own purchase request")

    _add_history(db, pr, PRStatus.APPROVED, current_user, payload.comment or "Approved")
    pr.status = PRStatus.APPROVED
    db.commit()
    db.refresh(pr)
    return _to_out(pr)


@router.post("/{pr_id}/reject", response_model=PurchaseRequestOut)
def reject_purchase_request(
    pr_id: str,
    payload: PRDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.APPROVER, UserRole.ADMIN)),
):
    reason = (payload.comment or "").strip()
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="A reason is required to reject a purchase request"
        )
    pr = _get_pr_or_404(db, pr_id)
    if pr.status != PRStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject a purchase request in status {pr.status.value}",
        )
    if pr.requester_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Requesters cannot reject their own purchase request")

    _add_history(db, pr, PRStatus.REJECTED, current_user, reason)
    pr.status = PRStatus.REJECTED
    pr.revision_required = True
    db.commit()
    db.refresh(pr)
    return _to_out(pr)


@router.delete("/{pr_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_purchase_request(
    pr_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    pr = _get_pr_or_404(db, pr_id)
    if current_user.role == UserRole.REQUESTER and pr.requester_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to delete this purchase request")
    if pr.status != PRStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft purchase requests can be deleted")

    db.delete(pr)
    db.commit()
