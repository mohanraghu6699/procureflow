from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import BaseModel, EmailStr, Field, PlainSerializer, field_validator

from app.models import DeliveryStatus, POStatus, PRStatus, UserRole


def _as_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


# Event timestamps are stored as naive UTC; emit them with an explicit UTC offset so
# browsers don't read them as local time.
UTCDateTime = Annotated[datetime, PlainSerializer(_as_utc_iso, return_type=str, when_used="json")]

# ---------- Auth ----------


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: UserRole
    department_id: Optional[str] = None
    department_name: Optional[str] = None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    role: UserRole
    department_id: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=100)


# ---------- Master data ----------


class DepartmentOut(BaseModel):
    id: str
    name: str
    is_active: bool

    class Config:
        from_attributes = True


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class CategoryOut(BaseModel):
    id: str
    name: str
    is_active: bool

    class Config:
        from_attributes = True


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class VendorOut(BaseModel):
    id: str
    name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    is_active: bool
    category_ids: list[str] = []

    class Config:
        from_attributes = True


class VendorCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(default=None, max_length=40)
    address: Optional[str] = Field(default=None, max_length=1000)
    category_ids: list[str] = []


class VendorCategoriesUpdate(BaseModel):
    category_ids: list[str]


# ---------- Purchase Request ----------


class PurchaseRequestCreate(BaseModel):
    department_id: str
    description: str = Field(min_length=3, max_length=500)
    category_id: str
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="AED", min_length=3, max_length=6)
    required_date: datetime
    vendor_id: Optional[str] = None

    @field_validator("required_date")
    @classmethod
    def required_date_not_in_past(cls, v: datetime) -> datetime:
        if v.date() < datetime.utcnow().date():
            raise ValueError("required_date cannot be in the past")
        return v


class PurchaseRequestUpdate(BaseModel):
    department_id: Optional[str] = None
    description: Optional[str] = Field(default=None, min_length=3, max_length=500)
    category_id: Optional[str] = None
    amount: Optional[Decimal] = Field(default=None, gt=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=6)
    required_date: Optional[datetime] = None
    vendor_id: Optional[str] = None


class PRStatusHistoryOut(BaseModel):
    id: str
    from_status: Optional[PRStatus] = None
    to_status: PRStatus
    changed_by_id: str
    changed_by_name: Optional[str] = None
    comment: Optional[str] = None
    changed_at: UTCDateTime

    class Config:
        from_attributes = True


class PurchaseRequestOut(BaseModel):
    id: str
    pr_number: str
    requester_id: str
    requester_name: Optional[str] = None
    department_id: str
    department_name: Optional[str] = None
    description: str
    category_id: str
    category_name: Optional[str] = None
    amount: Decimal
    currency: str
    required_date: datetime
    vendor_id: Optional[str] = None
    vendor_name: Optional[str] = None
    status: PRStatus
    revision_required: bool = False
    created_at: UTCDateTime
    updated_at: UTCDateTime

    class Config:
        from_attributes = True


class PurchaseRequestDetail(PurchaseRequestOut):
    status_history: list[PRStatusHistoryOut] = []


class PRDecisionRequest(BaseModel):
    comment: Optional[str] = Field(default=None, max_length=500)


class PaginatedPurchaseRequests(BaseModel):
    items: list[PurchaseRequestOut]
    total: int
    page: int
    page_size: int


# ---------- Purchase Order ----------


class PurchaseOrderCreate(BaseModel):
    pr_id: str
    vendor_id: str
    amount: Decimal = Field(gt=0)


class PurchaseOrderOut(BaseModel):
    id: str
    po_number: str
    pr_id: str
    pr_number: Optional[str] = None
    vendor_id: str
    vendor_name: Optional[str] = None
    amount: Decimal
    currency: str
    status: POStatus
    required_date: datetime
    created_by_id: str
    created_by_name: Optional[str] = None
    created_at: UTCDateTime
    updated_at: UTCDateTime

    class Config:
        from_attributes = True


class DeliveryOut(BaseModel):
    id: str
    po_id: str
    po_number: Optional[str] = None
    delivery_date: Optional[datetime] = None
    status: DeliveryStatus
    remarks: Optional[str] = None
    updated_by_id: str
    updated_by_name: Optional[str] = None
    updated_at: UTCDateTime

    class Config:
        from_attributes = True


class PurchaseOrderDetail(PurchaseOrderOut):
    deliveries: list[DeliveryOut] = []


class PaginatedPurchaseOrders(BaseModel):
    items: list[PurchaseOrderOut]
    total: int
    page: int
    page_size: int


class PaginatedDeliveries(BaseModel):
    items: list[DeliveryOut]
    total: int
    page: int
    page_size: int


# ---------- Delivery ----------


class DeliveryUpdate(BaseModel):
    delivery_date: Optional[datetime] = None
    status: DeliveryStatus
    remarks: Optional[str] = Field(default=None, max_length=500)


# ---------- Dashboard ----------


class StatusCount(BaseModel):
    status: str
    count: int


class MonthlyTrendPoint(BaseModel):
    month: str
    pr_count: int
    po_count: int


class TrendPoint(BaseModel):
    current: Decimal
    previous: Decimal


class DashboardTrends(BaseModel):
    prs_created_month: TrendPoint
    pos_created_month: TrendPoint
    submitted_week: TrendPoint
    ordered_week: TrendPoint
    approved_spend_month: TrendPoint


class DashboardSummary(BaseModel):
    total_purchase_requests: int
    pending_approval: int
    total_purchase_orders: int
    pending_delivery: int
    total_spend_approved: Decimal
    pr_by_status: list[StatusCount]
    po_by_status: list[StatusCount]
    monthly_trend: list[MonthlyTrendPoint]
    trends: DashboardTrends


class RecentActivityItem(BaseModel):
    id: str
    type: str
    message: str
    timestamp: UTCDateTime
