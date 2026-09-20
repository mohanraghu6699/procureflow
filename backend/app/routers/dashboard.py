from datetime import datetime, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends
from sqlalchemy import and_, func
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
from app.schemas import (
    CurrencyTotal,
    DashboardSummary,
    DashboardTrends,
    MonthlyTrendPoint,
    RecentActivityItem,
    StatusCount,
    TrendPoint,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# POStatus.DELIVERED is never assigned (delivering completes the PO), so it isn't summarised.
PO_SUMMARY_STATUSES = [
    POStatus.OPEN,
    POStatus.IN_TRANSIT,
    POStatus.PARTIALLY_DELIVERED,
    POStatus.COMPLETED,
    POStatus.CANCELLED,
]

# A cancelled order is still listed and counted, but it is no money spent or on order: amounts and spend skip it.
LIVE_PO = PurchaseOrder.status != POStatus.CANCELLED

ACTIVITY_VERB = {
    PRStatus.DRAFT: "created",
    PRStatus.SUBMITTED: "submitted for approval",
    PRStatus.APPROVED: "approved",
    PRStatus.REJECTED: "rejected",
    PRStatus.COMPLETED: "completed",
}


def _amounts_by_currency(query, currency_column, amount_column) -> list[CurrencyTotal]:
    total = func.sum(amount_column)
    rows = query.with_entities(currency_column, total).group_by(currency_column).order_by(total.desc()).all()
    return [CurrencyTotal(currency=currency, amount=Decimal(str(amount))) for currency, amount in rows]


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

    # Actual PO price once ordered, otherwise the approved PR amount.
    total_spend = (
        pr_query.filter(PurchaseRequest.status.in_([PRStatus.APPROVED, PRStatus.COMPLETED]))
        .outerjoin(PurchaseOrder, and_(PurchaseOrder.pr_id == PurchaseRequest.id, LIVE_PO))
        .with_entities(func.coalesce(func.sum(func.coalesce(PurchaseOrder.amount, PurchaseRequest.amount)), 0))
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

    po_counts = {s.value: 0 for s in PO_SUMMARY_STATUSES}
    for status_value, count in (
        po_query.with_entities(PurchaseOrder.status, func.count()).group_by(PurchaseOrder.status).all()
    ):
        if status_value.value in po_counts:
            po_counts[status_value.value] = count
    po_by_status = [StatusCount(status=k, count=v) for k, v in po_counts.items()]

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

    now = datetime.utcnow()
    horizon = now + timedelta(days=1)
    this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month = this_month - relativedelta(months=1)
    this_week = now - timedelta(days=7)
    last_week = now - timedelta(days=14)
    is_requester = current_user.role == UserRole.REQUESTER

    def created(query, column, start, end):
        return query.filter(column >= start, column < end).count()

    def transitions(to_status, start, end):
        q = db.query(PRStatusHistory).join(PurchaseRequest, PRStatusHistory.pr_id == PurchaseRequest.id)
        if is_requester:
            q = q.filter(PurchaseRequest.requester_id == current_user.id)
        return q.filter(
            PRStatusHistory.to_status == to_status,
            PRStatusHistory.changed_at >= start,
            PRStatusHistory.changed_at < end,
        ).count()

    def approved_spend(start, end):
        q = (
            db.query(func.coalesce(func.sum(func.coalesce(PurchaseOrder.amount, PurchaseRequest.amount)), 0))
            .select_from(PRStatusHistory)
            .join(PurchaseRequest, PRStatusHistory.pr_id == PurchaseRequest.id)
            .outerjoin(PurchaseOrder, and_(PurchaseOrder.pr_id == PurchaseRequest.id, LIVE_PO))
        )
        if is_requester:
            q = q.filter(PurchaseRequest.requester_id == current_user.id)
        return q.filter(
            PRStatusHistory.to_status == PRStatus.APPROVED,
            PRStatusHistory.changed_at >= start,
            PRStatusHistory.changed_at < end,
        ).scalar()

    trends = DashboardTrends(
        prs_created_month=TrendPoint(
            current=created(pr_query, PurchaseRequest.created_at, this_month, horizon),
            previous=created(pr_query, PurchaseRequest.created_at, last_month, this_month),
        ),
        pos_created_month=TrendPoint(
            current=created(po_query, PurchaseOrder.created_at, this_month, horizon),
            previous=created(po_query, PurchaseOrder.created_at, last_month, this_month),
        ),
        submitted_week=TrendPoint(
            current=transitions(PRStatus.SUBMITTED, this_week, horizon),
            previous=transitions(PRStatus.SUBMITTED, last_week, this_week),
        ),
        ordered_week=TrendPoint(
            current=created(po_query, PurchaseOrder.created_at, this_week, horizon),
            previous=created(po_query, PurchaseOrder.created_at, last_week, this_week),
        ),
        approved_spend_month=TrendPoint(
            current=approved_spend(this_month, horizon),
            previous=approved_spend(last_month, this_month),
        ),
    )

    return DashboardSummary(
        total_purchase_requests=total_prs,
        pending_approval=pending_approval,
        total_purchase_orders=total_pos,
        pending_delivery=pending_delivery,
        pr_amounts=_amounts_by_currency(pr_query, PurchaseRequest.currency, PurchaseRequest.amount),
        po_amounts=_amounts_by_currency(po_query.filter(LIVE_PO), PurchaseOrder.currency, PurchaseOrder.amount),
        total_spend_approved=Decimal(total_spend or 0),
        pr_by_status=pr_by_status,
        po_by_status=po_by_status,
        monthly_trend=monthly_trend,
        trends=trends,
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

    cancelled_query = (
        db.query(PurchaseOrder)
        .join(PurchaseRequest, PurchaseOrder.pr_id == PurchaseRequest.id)
        .filter(PurchaseOrder.status == POStatus.CANCELLED)
    )
    if current_user.role == UserRole.REQUESTER:
        cancelled_query = cancelled_query.filter(PurchaseRequest.requester_id == current_user.id)

    history_items = history_query.order_by(PRStatusHistory.changed_at.desc()).limit(10).all()
    delivery_items = delivery_query.order_by(Delivery.updated_at.desc()).limit(10).all()
    cancelled_items = cancelled_query.order_by(PurchaseOrder.cancelled_at.desc()).limit(10).all()

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

    for po in cancelled_items:
        activity.append(
            RecentActivityItem(
                id=f"cancel-{po.id}",
                type="purchase_order",
                message=f"{po.po_number} cancelled",
                timestamp=po.cancelled_at,
            )
        )

    activity.sort(key=lambda item: item.timestamp, reverse=True)
    return activity[:10]
