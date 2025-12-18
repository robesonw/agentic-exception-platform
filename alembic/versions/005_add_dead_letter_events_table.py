"""Add dead_letter_events table

Revision ID: 005_add_dead_letter_events
Revises: 004_add_event_processing
Create Date: 2025-01-29 15:00:00.000000

Phase 9 P9-15: Add dead_letter_events table for DLQ.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '005_add_dead_letter_events'
down_revision: Union[str, None] = '004_add_event_processing'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create dead_letter_events table
    op.create_table(
        'dead_letter_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('exception_id', sa.String(), nullable=True),
        sa.Column('original_topic', sa.String(), nullable=False),
        sa.Column('failure_reason', sa.String(), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('worker_type', sa.String(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('failed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['exception_id'], ['exception.exception_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', name='uq_dead_letter_events_event_id')
    )
    
    # Create indexes
    op.create_index('idx_dlq_tenant_failed_at', 'dead_letter_events', ['tenant_id', 'failed_at'])
    op.create_index('idx_dlq_exception_failed_at', 'dead_letter_events', ['exception_id', 'failed_at'])
    op.create_index('idx_dlq_tenant_type_failed_at', 'dead_letter_events', ['tenant_id', 'event_type', 'failed_at'])
    op.create_index('idx_dlq_worker_failed_at', 'dead_letter_events', ['worker_type', 'failed_at'])
    op.create_index(op.f('ix_dead_letter_events_event_id'), 'dead_letter_events', ['event_id'], unique=True)
    op.create_index(op.f('ix_dead_letter_events_event_type'), 'dead_letter_events', ['event_type'])
    op.create_index(op.f('ix_dead_letter_events_tenant_id'), 'dead_letter_events', ['tenant_id'])
    op.create_index(op.f('ix_dead_letter_events_exception_id'), 'dead_letter_events', ['exception_id'])
    op.create_index(op.f('ix_dead_letter_events_worker_type'), 'dead_letter_events', ['worker_type'])
    op.create_index(op.f('ix_dead_letter_events_failed_at'), 'dead_letter_events', ['failed_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_dead_letter_events_failed_at'), table_name='dead_letter_events')
    op.drop_index(op.f('ix_dead_letter_events_worker_type'), table_name='dead_letter_events')
    op.drop_index(op.f('ix_dead_letter_events_exception_id'), table_name='dead_letter_events')
    op.drop_index(op.f('ix_dead_letter_events_tenant_id'), table_name='dead_letter_events')
    op.drop_index(op.f('ix_dead_letter_events_event_type'), table_name='dead_letter_events')
    op.drop_index(op.f('ix_dead_letter_events_event_id'), table_name='dead_letter_events')
    op.drop_index('idx_dlq_worker_failed_at', table_name='dead_letter_events')
    op.drop_index('idx_dlq_tenant_type_failed_at', table_name='dead_letter_events')
    op.drop_index('idx_dlq_exception_failed_at', table_name='dead_letter_events')
    op.drop_index('idx_dlq_tenant_failed_at', table_name='dead_letter_events')
    
    # Drop table
    op.drop_table('dead_letter_events')



