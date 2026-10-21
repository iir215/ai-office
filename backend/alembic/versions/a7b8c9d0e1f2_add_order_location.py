"""add latitude/longitude to shop_orders

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-10-21 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('shop_orders')}
    if 'latitude' not in cols:
        op.add_column('shop_orders', sa.Column('latitude', sa.Float(), nullable=True))
    if 'longitude' not in cols:
        op.add_column('shop_orders', sa.Column('longitude', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('shop_orders', 'longitude')
    op.drop_column('shop_orders', 'latitude')
