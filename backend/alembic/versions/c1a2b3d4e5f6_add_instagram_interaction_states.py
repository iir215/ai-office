"""add instagram interaction states

Revision ID: c1a2b3d4e5f6
Revises: 8d68649bb5ca
Create Date: 2026-08-20 05:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a2b3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '8d68649bb5ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('instagram_interaction_states',
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('external_id', sa.String(length=128), nullable=False),
    sa.Column('last_value', sa.String(length=128), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('kind', 'external_id', name='uq_instagram_interaction_kind_external_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('instagram_interaction_states')
