import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models import (
    POStatus,
    PRStatus,
    PurchaseOrder,
    PurchaseRequest,
    User,
    UserRole,
)
from app.schemas import (
    DeliveryOut,
    PaginatedPurchaseOrders,
    PurchaseOrderCreate,
    PurchaseOrderDetail,
    PurchaseOrderOut,
)
from app.utils import assert_vendor_supplies_category, next_sequence_number

router = APIRouter(prefix="/api/purchase-orders", tags=["purchase-orders"])
logger = logging.getLogger("procureflow.purchase_orders")


def _to_out(po: PurchaseOrder) -> PurchaseOrderOut:
    return PurchaseOrderOut(
        id=po.id,
        po_number=po.po_number,
        pr_id=po.pr_id,
        pr_number=po.purchase_request.pr_number if po.purchase_request else None,
        vendor_id=po.vendor_id,
        vendor_name=po.vendor.name if po.vendor else None,
        amount=po.amount,
        currency=po.currency,
        status=po.status,
        required_date=po.purchase_request.required_date,
        created_by_id=po.created_by_id,
        created_by_name=po.created_by.name if po.created_by else None,
        created_at=po.created_at,
        updated_at=po.updated_at,
    )


def _get_po_or_404(db: Session, po_id: str) -> PurchaseOrder:
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    return po


def _assert_can_view(po: PurchaseOrder, user: User) -> None:
    if user.role == UserRole.REQUESTER and po.purchase_request.requester_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this purchase order")


@router.post("", response_model=PurchaseOrderOut, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.APPROVER, UserRole.ADMIN)),
):
    pr = db.query(PurchaseRequest).filter(PurchaseRequest.id == payload.pr_id).first()
    if pr is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid pr_id")
    if pr.status != PRStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A purchase order can only be created against an approved purchase request",
        )
    if any(po.status != POStatus.COMPLETED for po in pr.purchase_orders):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This purchase request already has an active purchase order",
        )
    assert_vendor_supplies_category(db, payload.vendor_id, pr.category_id)
    if payload.amount > pr.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PO amount cannot exceed the approved amount of {pr.currency} {pr.amount:,.2f}",
        )

    po = PurchaseOrder(
        po_number=next_sequence_number(db, PurchaseOrder, PurchaseOrder.po_number, "PO"),
        pr_id=pr.id,
        vendor_id=payload.vendor_id,
        amount=payload.amount,
        currency=pr.currency,
        status=POStatus.OPEN,
        created_by_id=current_user.id,
    )
    db.add(po)
    db.commit()
    db.refresh(po)
    logger.info(
        "%s created for %s by %s (%s %s)", po.po_number, pr.pr_number, current_user.email, po.currency, po.amount
    )
    return _to_out(po)


@router.get("", response_model=PaginatedPurchaseOrders)
def list_purchase_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: Optional[POStatus] = Query(default=None, alias="status"),
    vendor_id: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = Query(default="created_at", pattern="^(created_at|amount|po_number|required_date)$"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
):
    query = db.query(PurchaseOrder).join(PurchaseRequest, PurchaseOrder.pr_id == PurchaseRequest.id)

    if current_user.role == UserRole.REQUESTER:
        query = query.filter(PurchaseRequest.requester_id == current_user.id)

    if status_filter is not None:
        query = query.filter(PurchaseOrder.status == status_filter)
    if vendor_id:
        query = query.filter(PurchaseOrder.vendor_id == vendor_id)
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(PurchaseOrder.po_number.ilike(like), PurchaseRequest.pr_number.ilike(like))
        )

    total = query.count()

    sort_columns = {
        "created_at": PurchaseOrder.created_at,
        "amount": PurchaseOrder.amount,
        "po_number": PurchaseOrder.po_number,
        "required_date": PurchaseRequest.required_date,
    }
    sort_column = sort_columns[sort_by]
    sort_column = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
    query = query.order_by(sort_column)

    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return PaginatedPurchaseOrders(
        items=[_to_out(po) for po in items], total=total, page=page, page_size=page_size
    )


@router.get("/{po_id}", response_model=PurchaseOrderDetail)
def get_purchase_order(
    po_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    po = _get_po_or_404(db, po_id)
    _assert_can_view(po, current_user)
    out = PurchaseOrderDetail(**_to_out(po).model_dump())
    out.deliveries = [
        DeliveryOut(
            id=d.id,
            po_id=d.po_id,
            po_number=po.po_number,
            delivery_date=d.delivery_date,
            status=d.status,
            remarks=d.remarks,
            updated_by_id=d.updated_by_id,
            updated_by_name=d.updated_by.name if d.updated_by else None,
            updated_at=d.updated_at,
        )
        for d in po.deliveries
    ]
    return out
