"""add must_change_password to users

Revision ID: c5d8a1f07e93
Revises: b7c41e9a52d0
Create Date: 2026-09-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5d8a1f07e93'
down_revision: Union[str, None] = 'b7c41e9a52d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users', sa.Column('must_change_password', sa.Boolean(), server_default=sa.false(), nullable=False)
    )


def downgrade() -> None:
    op.drop_column('users', 'must_change_password')
