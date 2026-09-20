"""initial schema

Revision ID: 57c7622701c2
Revises: 
Create Date: 2026-09-18 21:12:36.241847

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '57c7622701c2'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('categories',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('departments',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('vendors',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=180), nullable=False),
    sa.Column('contact_email', sa.String(length=180), nullable=True),
    sa.Column('contact_phone', sa.String(length=40), nullable=True),
    sa.Column('address', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=180), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.Enum('REQUESTER', 'APPROVER', 'ADMIN', name='user_role'), nullable=False),
    sa.Column('department_id', sa.String(length=36), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('vendor_categories',
    sa.Column('vendor_id', sa.String(length=36), nullable=False),
    sa.Column('category_id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('vendor_id', 'category_id')
    )
    op.create_index(op.f('ix_vendor_categories_category_id'), 'vendor_categories', ['category_id'], unique=False)
    op.create_table('purchase_requests',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('pr_number', sa.String(length=30), nullable=False),
    sa.Column('requester_id', sa.String(length=36), nullable=False),
    sa.Column('department_id', sa.String(length=36), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=False),
    sa.Column('category_id', sa.String(length=36), nullable=False),
    sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=6), nullable=False),
    sa.Column('required_date', sa.DateTime(), nullable=False),
    sa.Column('vendor_id', sa.String(length=36), nullable=True),
    sa.Column('status', sa.Enum('DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', 'COMPLETED', name='pr_status'), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ),
    sa.ForeignKeyConstraint(['requester_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_purchase_requests_pr_number'), 'purchase_requests', ['pr_number'], unique=True)
    op.create_table('pr_status_history',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('pr_id', sa.String(length=36), nullable=False),
    sa.Column('from_status', sa.Enum('DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', 'COMPLETED', name='pr_status_from'), nullable=True),
    sa.Column('to_status', sa.Enum('DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', 'COMPLETED', name='pr_status_to'), nullable=False),
    sa.Column('changed_by_id', sa.String(length=36), nullable=False),
    sa.Column('comment', sa.String(length=500), nullable=True),
    sa.Column('changed_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['changed_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['pr_id'], ['purchase_requests.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('purchase_orders',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('po_number', sa.String(length=30), nullable=False),
    sa.Column('pr_id', sa.String(length=36), nullable=False),
    sa.Column('vendor_id', sa.String(length=36), nullable=False),
    sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=6), nullable=False),
    sa.Column('status', sa.Enum('OPEN', 'PARTIALLY_DELIVERED', 'DELIVERED', 'COMPLETED', name='po_status'), nullable=False),
    sa.Column('created_by_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['pr_id'], ['purchase_requests.id'], ),
    sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_purchase_orders_po_number'), 'purchase_orders', ['po_number'], unique=True)
    op.create_table('deliveries',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('po_id', sa.String(length=36), nullable=False),
    sa.Column('delivery_date', sa.DateTime(), nullable=True),
    sa.Column('status', sa.Enum('PENDING', 'PARTIAL', 'DELIVERED', name='delivery_status'), nullable=False),
    sa.Column('remarks', sa.String(length=500), nullable=True),
    sa.Column('updated_by_id', sa.String(length=36), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['po_id'], ['purchase_orders.id'], ),
    sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('deliveries')
    op.drop_index(op.f('ix_purchase_orders_po_number'), table_name='purchase_orders')
    op.drop_table('purchase_orders')
    op.drop_table('pr_status_history')
    op.drop_index(op.f('ix_purchase_requests_pr_number'), table_name='purchase_requests')
    op.drop_table('purchase_requests')
    op.drop_index(op.f('ix_vendor_categories_category_id'), table_name='vendor_categories')
    op.drop_table('vendor_categories')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_table('vendors')
    op.drop_table('departments')
    op.drop_table('categories')
