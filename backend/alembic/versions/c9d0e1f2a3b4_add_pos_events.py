"""add pos_events

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-10-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, Sequence[str], None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('pos_events'):
        return

    op.create_table(
        'pos_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('sender_id', sa.BigInteger(), nullable=False),
        sa.Column('sender_username', sa.String(length=100), nullable=True),
        sa.Column('tg_message_id', sa.BigInteger(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=True),
        sa.Column('parsed_json', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sender_id', 'tg_message_id', name='uq_pos_event_message'),
    )
    op.create_index('ix_pos_events_company_id', 'pos_events', ['company_id'])


def downgrade() -> None:
    op.drop_index('ix_pos_events_company_id', table_name='pos_events')
    op.drop_table('pos_events')
