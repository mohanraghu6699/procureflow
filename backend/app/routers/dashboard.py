from datetime import datetime
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    Delivery,
    POStatus,
    PRStatus,
    PRStatusHistory,
    PurchaseOrder,
    PurchaseRequest,
    User,
    UserRole,
)
from app.schemas import DashboardSummary, MonthlyTrendPoint, RecentActivityItem, StatusCount

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

ACTIVITY_VERB = {
    PRStatus.DRAFT: "created",
    PRStatus.SUBMITTED: "submitted for approval",
    PRStatus.APPROVED: "approved",
    PRStatus.REJECTED: "rejected",
    PRStatus.COMPLETED: "completed",
}


@router.get("/summary", response_model=DashboardSummary)
def get_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    pr_query = db.query(PurchaseRequest)
    po_query = db.query(PurchaseOrder).join(PurchaseRequest, PurchaseOrder.pr_id == PurchaseRequest.id)

    if current_user.role == UserRole.REQUESTER:
        pr_query = pr_query.filter(PurchaseRequest.requester_id == current_user.id)
        po_query = po_query.filter(PurchaseRequest.requester_id == current_user.id)

    total_prs = pr_query.count()
    pending_approval = pr_query.filter(PurchaseRequest.status == PRStatus.SUBMITTED).count()
    total_pos = po_query.count()
    pending_delivery = po_query.filter(
        PurchaseOrder.status.in_([POStatus.OPEN, POStatus.IN_TRANSIT, POStatus.PARTIALLY_DELIVERED])
    ).count()

    total_spend = (
        pr_query.filter(PurchaseRequest.status.in_([PRStatus.APPROVED, PRStatus.COMPLETED]))
        .with_entities(func.coalesce(func.sum(PurchaseRequest.amount), 0))
        .scalar()
    )

    status_rows = (
        pr_query.with_entities(PurchaseRequest.status, func.count())
        .group_by(PurchaseRequest.status)
        .all()
    )
    status_counts = {s.value: 0 for s in PRStatus}
    for status_value, count in status_rows:
        status_counts[status_value.value] = count
    pr_by_status = [StatusCount(status=k, count=v) for k, v in status_counts.items()]

    today = datetime.utcnow().replace(day=1)
    months = [(today - relativedelta(months=i)) for i in range(8, -1, -1)]
    monthly_trend: list[MonthlyTrendPoint] = []
    for month_start in months:
        month_end = month_start + relativedelta(months=1)
        pr_count = pr_query.filter(
            PurchaseRequest.created_at >= month_start, PurchaseRequest.created_at < month_end
        ).count()
        po_count = po_query.filter(
            PurchaseOrder.created_at >= month_start, PurchaseOrder.created_at < month_end
        ).count()
        monthly_trend.append(
            MonthlyTrendPoint(month=month_start.strftime("%b"), pr_count=pr_count, po_count=po_count)
        )

    return DashboardSummary(
        total_purchase_requests=total_prs,
        pending_approval=pending_approval,
        total_purchase_orders=total_pos,
        pending_delivery=pending_delivery,
        total_spend_approved=Decimal(total_spend or 0),
        pr_by_status=pr_by_status,
        monthly_trend=monthly_trend,
    )


@router.get("/recent-activity", response_model=list[RecentActivityItem])
def get_recent_activity(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    history_query = db.query(PRStatusHistory).join(
        PurchaseRequest, PRStatusHistory.pr_id == PurchaseRequest.id
    )
    delivery_query = db.query(Delivery).join(PurchaseOrder, Delivery.po_id == PurchaseOrder.id).join(
        PurchaseRequest, PurchaseOrder.pr_id == PurchaseRequest.id
    )

    if current_user.role == UserRole.REQUESTER:
        history_query = history_query.filter(PurchaseRequest.requester_id == current_user.id)
        delivery_query = delivery_query.filter(PurchaseRequest.requester_id == current_user.id)

    history_items = history_query.order_by(PRStatusHistory.changed_at.desc()).limit(10).all()
    delivery_items = delivery_query.order_by(Delivery.updated_at.desc()).limit(10).all()

    activity: list[RecentActivityItem] = []
    for h in history_items:
        activity.append(
            RecentActivityItem(
                id=h.id,
                type="purchase_request",
                message=f"{h.purchase_request.pr_number} {ACTIVITY_VERB[h.to_status]}",
                timestamp=h.changed_at,
            )
        )
    for d in delivery_items:
        activity.append(
            RecentActivityItem(
                id=d.id,
                type="delivery",
                message=f"{d.purchase_order.po_number} delivery marked {d.status.value.lower().replace('_', ' ')}",
                timestamp=d.updated_at,
            )
        )

    activity.sort(key=lambda item: item.timestamp, reverse=True)
    return activity[:10]
