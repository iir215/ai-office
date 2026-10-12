"""widen instagram interaction state columns

Revision ID: d2b3c4e5f6a7
Revises: c1a2b3d4e5f6
Create Date: 2026-08-20 05:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2b3c4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'c1a2b3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('instagram_interaction_states', 'external_id',
               existing_type=sa.String(length=128),
               type_=sa.String(length=512))
    op.alter_column('instagram_interaction_states', 'last_value',
               existing_type=sa.String(length=128),
               type_=sa.String(length=512))


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('instagram_interaction_states', 'last_value',
               existing_type=sa.String(length=512),
               type_=sa.String(length=128))
    op.alter_column('instagram_interaction_states', 'external_id',
               existing_type=sa.String(length=512),
               type_=sa.String(length=128))
