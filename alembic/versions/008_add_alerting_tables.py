"""Add alerting tables for P10-5 through P10-9

Phase 10: Alerting System
- alert_config: Per-tenant alert configuration
- alert_history: Alert trigger history and acknowledgment

Revision ID: 008
Revises: 007_add_dlq_status_column
Create Date: 2025-01-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create alerting tables."""
    # Create alert_config table
    op.create_table(
        'alert_config',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.String(255), nullable=False, index=True),
        sa.Column('alert_type', sa.String(50), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('threshold', sa.Float(), nullable=True),
        sa.Column('threshold_unit', sa.String(50), nullable=True),
        sa.Column('channels', JSONB, nullable=False, server_default='[]'),
        sa.Column('quiet_hours_start', sa.Time(), nullable=True),
        sa.Column('quiet_hours_end', sa.Time(), nullable=True),
        sa.Column('escalation_minutes', sa.Integer(), nullable=True),
        sa.Column('config_metadata', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'alert_type', name='uq_alert_config_tenant_type'),
    )

    # Create alert_history table
    op.create_table(
        'alert_history',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('alert_id', sa.String(50), nullable=False, unique=True, index=True),
        sa.Column('tenant_id', sa.String(255), nullable=False, index=True),
        sa.Column('alert_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False, server_default='warning'),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('details', JSONB, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='triggered'),
        sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by', sa.String(255), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.String(255), nullable=True),
        sa.Column('notification_sent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notification_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create indexes for common queries
    op.create_index(
        'idx_alert_history_tenant_status',
        'alert_history',
        ['tenant_id', 'status']
    )
    op.create_index(
        'idx_alert_history_tenant_type',
        'alert_history',
        ['tenant_id', 'alert_type']
    )
    op.create_index(
        'idx_alert_history_triggered_at',
        'alert_history',
        ['triggered_at']
    )


def downgrade() -> None:
    """Remove alerting tables."""
    op.drop_index('idx_alert_history_triggered_at', table_name='alert_history')
    op.drop_index('idx_alert_history_tenant_type', table_name='alert_history')
    op.drop_index('idx_alert_history_tenant_status', table_name='alert_history')
    op.drop_table('alert_history')
    op.drop_table('alert_config')
