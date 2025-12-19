"""Add status column to dead_letter_events table for P10-4

Phase 10: DLQ Management API enhancement.
Adds status column to track DLQ entry lifecycle:
- pending: Waiting to be processed
- retrying: Currently being retried
- discarded: Manually discarded without retry
- succeeded: Retry succeeded

Revision ID: 007
Revises: 006_add_pii_redaction_metadata_table
Create Date: 2025-01-18
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006_add_pii_redaction_metadata_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add status column to dead_letter_events table."""
    # Add status column with default 'pending'
    op.add_column(
        'dead_letter_events',
        sa.Column(
            'status',
            sa.String(20),
            nullable=False,
            server_default='pending'
        )
    )

    # Add retried_at column to track when retries happen
    op.add_column(
        'dead_letter_events',
        sa.Column(
            'retried_at',
            sa.DateTime(timezone=True),
            nullable=True
        )
    )

    # Add discarded_at column to track when discards happen
    op.add_column(
        'dead_letter_events',
        sa.Column(
            'discarded_at',
            sa.DateTime(timezone=True),
            nullable=True
        )
    )

    # Add discarded_by column to track who discarded
    op.add_column(
        'dead_letter_events',
        sa.Column(
            'discarded_by',
            sa.String(255),
            nullable=True
        )
    )

    # Add index for status queries
    op.create_index(
        'idx_dlq_tenant_status',
        'dead_letter_events',
        ['tenant_id', 'status']
    )


def downgrade() -> None:
    """Remove status and related columns from dead_letter_events table."""
    op.drop_index('idx_dlq_tenant_status', table_name='dead_letter_events')
    op.drop_column('dead_letter_events', 'discarded_by')
    op.drop_column('dead_letter_events', 'discarded_at')
    op.drop_column('dead_letter_events', 'retried_at')
    op.drop_column('dead_letter_events', 'status')
