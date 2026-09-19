from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import Integer, cast, func, text
from sqlalchemy.orm import Session

from app.models import Vendor


def assert_vendor_supplies_category(db: Session, vendor_id: str, category_id: str) -> None:
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if vendor is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid vendor_id")
    if not vendor.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected vendor is inactive")
    if category_id not in vendor.category_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Selected vendor does not supply this category"
        )


def next_sequence_number(db: Session, model, number_column, prefix: str) -> str:
    """Generate a PREFIX-YYYY-NNNN number, one higher than the highest existing this year.

    Uses the max existing sequence rather than a row count so deleting a draft can't
    cause a number to be handed out twice. On PostgreSQL a transaction-scoped advisory
    lock serialises concurrent requests until the caller commits.
    """
    year = datetime.utcnow().year
    year_prefix = f"{prefix}-{year}-"

    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": year_prefix})

    highest = (
        db.query(func.max(cast(func.substr(number_column, len(year_prefix) + 1), Integer)))
        .select_from(model)
        .filter(number_column.like(f"{year_prefix}%"))
        .scalar()
    )
    return f"{year_prefix}{(highest or 0) + 1:04d}"
