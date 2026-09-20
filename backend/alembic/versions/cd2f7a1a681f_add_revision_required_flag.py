"""add revision required flag

Revision ID: cd2f7a1a681f
Revises: e13065bb9034
Create Date: 2026-09-19 16:08:13.651115

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd2f7a1a681f'
down_revision: Union[str, None] = 'e13065bb9034'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('purchase_requests', sa.Column('revision_required', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade() -> None:
    op.drop_column('purchase_requests', 'revision_required')
