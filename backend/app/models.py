import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    false,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class UserRole(str, enum.Enum):
    REQUESTER = "REQUESTER"
    APPROVER = "APPROVER"
    ADMIN = "ADMIN"


class PRStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class POStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_TRANSIT = "IN_TRANSIT"
    PARTIALLY_DELIVERED = "PARTIALLY_DELIVERED"
    DELIVERED = "DELIVERED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class DeliveryStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_TRANSIT = "IN_TRANSIT"
    PARTIAL = "PARTIAL"
    DELIVERED = "DELIVERED"


def gen_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(120), nullable=False)
    email = Column(String(180), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole, name="user_role"), nullable=False)
    department_id = Column(String(36), ForeignKey("departments.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    department = relationship("Department", back_populates="users")


class Department(Base):
    __tablename__ = "departments"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(120), unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    users = relationship("User", back_populates="department")
    purchase_requests = relationship("PurchaseRequest", back_populates="department")


class Category(Base):
    __tablename__ = "categories"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(120), unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    purchase_requests = relationship("PurchaseRequest", back_populates="category")


vendor_categories = Table(
    "vendor_categories",
    Base.metadata,
    Column("vendor_id", String(36), ForeignKey("vendors.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", String(36), ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True, index=True),
)


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(180), nullable=False)
    contact_email = Column(String(180), nullable=True)
    contact_phone = Column(String(40), nullable=True)
    address = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    categories = relationship("Category", secondary=vendor_categories)
    purchase_requests = relationship("PurchaseRequest", back_populates="vendor")
    purchase_orders = relationship("PurchaseOrder", back_populates="vendor")

    @property
    def category_ids(self) -> list[str]:
        return [c.id for c in self.categories]


class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    pr_number = Column(String(30), unique=True, nullable=False, index=True)
    requester_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    department_id = Column(String(36), ForeignKey("departments.id"), nullable=False)
    description = Column(String(500), nullable=False)
    category_id = Column(String(36), ForeignKey("categories.id"), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(6), nullable=False, default="AED")
    required_date = Column(DateTime, nullable=False)
    vendor_id = Column(String(36), ForeignKey("vendors.id"), nullable=True)
    status = Column(Enum(PRStatus, name="pr_status"), nullable=False, default=PRStatus.DRAFT)
    revision_required = Column(Boolean, nullable=False, default=False, server_default=false())
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    requester = relationship("User", foreign_keys=[requester_id])
    department = relationship("Department", back_populates="purchase_requests")
    category = relationship("Category", back_populates="purchase_requests")
    vendor = relationship("Vendor", back_populates="purchase_requests")
    status_history = relationship(
        "PRStatusHistory", back_populates="purchase_request", cascade="all, delete-orphan",
        order_by="PRStatusHistory.changed_at",
    )
    purchase_orders = relationship("PurchaseOrder", back_populates="purchase_request")


class PRStatusHistory(Base):
    __tablename__ = "pr_status_history"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    pr_id = Column(String(36), ForeignKey("purchase_requests.id"), nullable=False)
    from_status = Column(Enum(PRStatus, name="pr_status_from"), nullable=True)
    to_status = Column(Enum(PRStatus, name="pr_status_to"), nullable=False)
    changed_by_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    comment = Column(String(500), nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    purchase_request = relationship("PurchaseRequest", back_populates="status_history")
    changed_by = relationship("User")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    po_number = Column(String(30), unique=True, nullable=False, index=True)
    pr_id = Column(String(36), ForeignKey("purchase_requests.id"), nullable=False)
    vendor_id = Column(String(36), ForeignKey("vendors.id"), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(6), nullable=False, default="AED")
    status = Column(Enum(POStatus, name="po_status"), nullable=False, default=POStatus.OPEN)
    created_by_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    # Set only when the order is cancelled (status CANCELLED): why, by whom and when.
    cancel_reason = Column(String(500), nullable=True)
    cancelled_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    purchase_request = relationship("PurchaseRequest", back_populates="purchase_orders")
    vendor = relationship("Vendor", back_populates="purchase_orders")
    created_by = relationship("User", foreign_keys=[created_by_id])
    cancelled_by = relationship("User", foreign_keys=[cancelled_by_id])
    deliveries = relationship("Delivery", back_populates="purchase_order", cascade="all, delete-orphan")


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    po_id = Column(String(36), ForeignKey("purchase_orders.id"), nullable=False)
    delivery_date = Column(DateTime, nullable=True)
    status = Column(Enum(DeliveryStatus, name="delivery_status"), nullable=False, default=DeliveryStatus.PENDING)
    remarks = Column(String(500), nullable=True)
    updated_by_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    purchase_order = relationship("PurchaseOrder", back_populates="deliveries")
    updated_by = relationship("User")
