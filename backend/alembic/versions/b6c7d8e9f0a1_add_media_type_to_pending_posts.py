"""add media_type to pending_posts

Revision ID: b6c7d8e9f0a1
Revises: a1b2c3d4e5f6
Create Date: 2026-08-26 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6c7d8e9f0a1'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('pending_posts', sa.Column('media_type', sa.String(length=20), nullable=False, server_default='IMAGE'))
    op.alter_column('pending_posts', 'media_type', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('pending_posts', 'media_type')
