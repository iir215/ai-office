"""add menu_items and shop_orders

Revision ID: e5f6a7b8c9d0
Revises: d9e0f1a2b3c4
Create Date: 2026-10-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd9e0f1a2b3c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The app also runs Base.metadata.create_all on startup, which may have
    # created these tables already; stay idempotent.
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table('menu_items'):
        op.create_table(
            'menu_items',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('category', sa.String(length=100), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('name_uz', sa.String(length=200), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('description_uz', sa.Text(), nullable=True),
            sa.Column('price', sa.Integer(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('sort', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_menu_items_company_id', 'menu_items', ['company_id'])

    if not inspector.has_table('shop_orders'):
        op.create_table(
            'shop_orders',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('number', sa.Integer(), nullable=False),
            sa.Column('order_date', sa.Date(), nullable=False),
            sa.Column('tg_user_id', sa.BigInteger(), nullable=False),
            sa.Column('tg_username', sa.String(length=100), nullable=True),
            sa.Column('customer_name', sa.String(length=200), nullable=False),
            sa.Column('phone', sa.String(length=40), nullable=False),
            sa.Column('fulfillment', sa.String(length=20), nullable=False),
            sa.Column('address', sa.Text(), nullable=True),
            sa.Column('comment', sa.Text(), nullable=True),
            sa.Column('items_json', sa.Text(), nullable=False),
            sa.Column('total', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=30), nullable=False),
            sa.Column('payment_method', sa.String(length=20), nullable=False),
            sa.Column('payment_status', sa.String(length=20), nullable=False),
            sa.Column('click_trans_id', sa.String(length=64), nullable=True),
            sa.Column('paid_at', sa.DateTime(), nullable=True),
            sa.Column('notified_messages', sa.Text(), nullable=True),
            sa.Column('lang', sa.String(length=5), nullable=False, server_default='ru'),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_shop_orders_company_id', 'shop_orders', ['company_id'])
        op.create_index('ix_shop_orders_tg_user_id', 'shop_orders', ['tg_user_id'])


def downgrade() -> None:
    op.drop_table('shop_orders')
    op.drop_table('menu_items')
