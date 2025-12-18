"""Add event_log table

Revision ID: 003_add_event_log
Revises: 435d1dc0b336
Create Date: 2025-01-29 12:00:00.000000

Phase 9 P9-4: Add event_log table for canonical event storage (append-only event store).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_add_event_log'
down_revision: Union[str, None] = '435d1dc0b336'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create event_log table
    op.create_table(
        'event_log',
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('exception_id', sa.String(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('correlation_id', sa.String(), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['exception_id'], ['exception.exception_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('event_id')
    )
    
    # Create indexes for performance
    op.create_index('idx_event_log_tenant_timestamp', 'event_log', ['tenant_id', 'timestamp'])
    op.create_index('idx_event_log_exception_timestamp', 'event_log', ['exception_id', 'timestamp'])
    op.create_index('idx_event_log_tenant_type_timestamp', 'event_log', ['tenant_id', 'event_type', 'timestamp'])
    op.create_index('ix_event_log_event_type', 'event_log', ['event_type'])
    op.create_index('ix_event_log_tenant_id', 'event_log', ['tenant_id'])
    op.create_index('ix_event_log_exception_id', 'event_log', ['exception_id'])
    op.create_index('ix_event_log_timestamp', 'event_log', ['timestamp'])
    op.create_index('ix_event_log_correlation_id', 'event_log', ['correlation_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_event_log_correlation_id', table_name='event_log')
    op.drop_index('ix_event_log_timestamp', table_name='event_log')
    op.drop_index('ix_event_log_exception_id', table_name='event_log')
    op.drop_index('ix_event_log_tenant_id', table_name='event_log')
    op.drop_index('ix_event_log_event_type', table_name='event_log')
    op.drop_index('idx_event_log_tenant_type_timestamp', table_name='event_log')
    op.drop_index('idx_event_log_exception_timestamp', table_name='event_log')
    op.drop_index('idx_event_log_tenant_timestamp', table_name='event_log')
    
    # Drop table
    op.drop_table('event_log')

