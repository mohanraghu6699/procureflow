from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import (
    DeliveryStatus,
    POStatus,
    PRStatus,
    PurchaseOrder,
    User,
    UserRole,
    Delivery,
)
from app.routers.purchase_orders import _to_out as po_to_out
from app.schemas import DeliveryOut, DeliveryUpdate, PurchaseOrderOut

router = APIRouter(prefix="/api", tags=["deliveries"])

STATUS_TO_PO_STATUS = {
    DeliveryStatus.PENDING: POStatus.OPEN,
    DeliveryStatus.IN_TRANSIT: POStatus.IN_TRANSIT,
    DeliveryStatus.PARTIAL: POStatus.PARTIALLY_DELIVERED,
    DeliveryStatus.DELIVERED: POStatus.COMPLETED,
}


def _to_out(delivery: Delivery) -> DeliveryOut:
    return DeliveryOut(
        id=delivery.id,
        po_id=delivery.po_id,
        delivery_date=delivery.delivery_date,
        status=delivery.status,
        remarks=delivery.remarks,
        updated_by_id=delivery.updated_by_id,
        updated_by_name=delivery.updated_by.name if delivery.updated_by else None,
        updated_at=delivery.updated_at,
    )


@router.post(
    "/purchase-orders/{po_id}/deliveries",
    response_model=PurchaseOrderOut,
    status_code=status.HTTP_201_CREATED,
)
def record_delivery(
    po_id: str,
    payload: DeliveryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.APPROVER, UserRole.ADMIN)),
):
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    if po.status == POStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This purchase order is already completed")
    if payload.status == DeliveryStatus.DELIVERED and payload.delivery_date is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="delivery_date is required when marking as delivered")
    if payload.delivery_date is not None:
        # Delivery dates are calendar dates sent as UTC midnight, so allow a day of slack for timezones.
        delivery_day = payload.delivery_date.date()
        if delivery_day > datetime.utcnow().date() + timedelta(days=1):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Delivery date cannot be in the future")
        if delivery_day < po.created_at.date() - timedelta(days=1):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Delivery date cannot be before the purchase order was created",
            )

    delivery = Delivery(
        po_id=po.id,
        delivery_date=payload.delivery_date,
        status=payload.status,
        remarks=payload.remarks,
        updated_by_id=current_user.id,
    )
    db.add(delivery)

    po.status = STATUS_TO_PO_STATUS[payload.status]
    if payload.status == DeliveryStatus.DELIVERED:
        po.purchase_request.status = PRStatus.COMPLETED

    db.commit()
    db.refresh(po)
    return po_to_out(po)


@router.get("/deliveries", response_model=list[DeliveryOut])
def list_deliveries(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.APPROVER, UserRole.ADMIN)),
    status_filter: Optional[DeliveryStatus] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
):
    query = db.query(Delivery)
    if status_filter is not None:
        query = query.filter(Delivery.status == status_filter)
    deliveries = query.order_by(Delivery.updated_at.desc()).limit(limit).all()
    return [_to_out(d) for d in deliveries]
