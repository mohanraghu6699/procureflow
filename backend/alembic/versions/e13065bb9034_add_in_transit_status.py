"""add in transit status

Revision ID: e13065bb9034
Revises: 57c7622701c2
Create Date: 2026-09-19 13:26:57.444984

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e13065bb9034'
down_revision: Union[str, None] = '57c7622701c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Autogenerate can't detect new enum values. ADD VALUE must commit before it can be used.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE po_status ADD VALUE IF NOT EXISTS 'IN_TRANSIT' BEFORE 'PARTIALLY_DELIVERED'")
        op.execute("ALTER TYPE delivery_status ADD VALUE IF NOT EXISTS 'IN_TRANSIT' BEFORE 'PARTIAL'")


def downgrade() -> None:
    # PostgreSQL cannot drop a value from an enum type; the extra value is harmless if left in place.
    pass
