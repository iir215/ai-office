"""add instagram_accounts

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-10-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, Sequence[str], None] = 'b6c7d8e9f0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The app also runs Base.metadata.create_all on startup, which may have
    # created this table already; stay idempotent.
    if sa.inspect(op.get_bind()).has_table('instagram_accounts'):
        return

    op.create_table(
        'instagram_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.String(length=64), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('token_refreshed_at', sa.DateTime(), nullable=True),
        sa.Column('last_refresh_attempt_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id'),
    )


def downgrade() -> None:
    op.drop_table('instagram_accounts')
