"""Add event_processing table

Revision ID: 004_add_event_processing
Revises: 003_add_event_log
Create Date: 2025-01-29 14:00:00.000000

Phase 9 P9-12: Add event_processing table for idempotency tracking.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004_add_event_processing'
down_revision: Union[str, None] = '003_add_event_log'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type
    event_processing_status_enum = postgresql.ENUM(
        'processing', 'completed', 'failed',
        name='event_processing_status',
        create_type=True
    )
    event_processing_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create event_processing table
    op.create_table(
        'event_processing',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('worker_type', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('exception_id', sa.String(), nullable=True),
        sa.Column('status', postgresql.ENUM('processing', 'completed', 'failed', name='event_processing_status', create_type=False), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['exception_id'], ['exception.exception_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', 'worker_type', name='uq_event_processing_event_worker')
    )
    
    # Create indexes
    op.create_index('ix_event_processing_event_id', 'event_processing', ['event_id'])
    op.create_index('ix_event_processing_worker_type', 'event_processing', ['worker_type'])
    op.create_index('ix_event_processing_tenant_id', 'event_processing', ['tenant_id'])
    op.create_index('ix_event_processing_exception_id', 'event_processing', ['exception_id'])
    op.create_index('idx_event_processing_tenant_worker', 'event_processing', ['tenant_id', 'worker_type'])
    op.create_index('idx_event_processing_exception_worker', 'event_processing', ['exception_id', 'worker_type'])
    op.create_index('idx_event_processing_status', 'event_processing', ['status', 'processed_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_event_processing_status', table_name='event_processing')
    op.drop_index('idx_event_processing_exception_worker', table_name='event_processing')
    op.drop_index('idx_event_processing_tenant_worker', table_name='event_processing')
    op.drop_index('ix_event_processing_exception_id', table_name='event_processing')
    op.drop_index('ix_event_processing_tenant_id', table_name='event_processing')
    op.drop_index('ix_event_processing_worker_type', table_name='event_processing')
    op.drop_index('ix_event_processing_event_id', table_name='event_processing')
    
    # Drop table
    op.drop_table('event_processing')
    
    # Drop enum type
    op.execute("DROP TYPE IF EXISTS event_processing_status")



