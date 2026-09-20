"""add purchase order cancellation

Revision ID: b7c41e9a52d0
Revises: cd2f7a1a681f
Create Date: 2026-09-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c41e9a52d0'
down_revision: Union[str, None] = 'cd2f7a1a681f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Autogenerate can't detect new enum values. ADD VALUE must commit before it can be used.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE po_status ADD VALUE IF NOT EXISTS 'CANCELLED'")
    op.add_column('purchase_orders', sa.Column('cancel_reason', sa.String(length=500), nullable=True))
    op.add_column('purchase_orders', sa.Column('cancelled_by_id', sa.String(length=36), nullable=True))
    op.add_column('purchase_orders', sa.Column('cancelled_at', sa.DateTime(), nullable=True))
    op.create_foreign_key(
        'fk_purchase_orders_cancelled_by_id_users', 'purchase_orders', 'users', ['cancelled_by_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_purchase_orders_cancelled_by_id_users', 'purchase_orders', type_='foreignkey')
    op.drop_column('purchase_orders', 'cancelled_at')
    op.drop_column('purchase_orders', 'cancelled_by_id')
    op.drop_column('purchase_orders', 'cancel_reason')
    # PostgreSQL cannot drop a value from an enum type; the extra value is harmless if left in place.
