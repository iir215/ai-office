"""add sprite to menu_items

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-15 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'sprite' not in {c['name'] for c in inspector.get_columns('menu_items')}:
        op.add_column('menu_items', sa.Column('sprite', sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column('menu_items', 'sprite')
