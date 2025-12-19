"""Add usage metering tables for P10-18 to P10-20

Phase 10: Usage Metering.
Adds tables for tracking resource usage:
- usage_metric: Aggregated usage metrics per tenant

Revision ID: 012
Revises: 011_add_rate_limit_tables
Create Date: 2025-01-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add usage metering tables."""
    # Create usage_metric table
    op.create_table(
        'usage_metric',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('metric_type', sa.String(50), nullable=False),  # api_calls, exceptions, tool_executions, events, storage
        sa.Column('resource_id', sa.String(255), nullable=True),  # Optional resource identifier (e.g., tool_id, endpoint)
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),  # Start of the period
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),  # End of the period
        sa.Column('period_type', sa.String(20), nullable=False, server_default='minute'),  # minute, hour, day, month
        sa.Column('count', sa.BigInteger(), nullable=False, server_default='0'),  # Count for count-based metrics
        sa.Column('bytes_value', sa.BigInteger(), nullable=True),  # For storage metrics
        sa.Column('metadata', JSONB, nullable=True),  # Additional metadata
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create indexes for usage_metric
    op.create_index('idx_usage_metric_tenant', 'usage_metric', ['tenant_id'])
    op.create_index('idx_usage_metric_type', 'usage_metric', ['metric_type'])
    op.create_index('idx_usage_metric_period', 'usage_metric', ['period_start', 'period_end'])
    op.create_index('idx_usage_metric_tenant_type_period', 'usage_metric', ['tenant_id', 'metric_type', 'period_start'])
    op.create_index('idx_usage_metric_tenant_period_type', 'usage_metric', ['tenant_id', 'period_type', 'period_start'])

    # Create unique constraint for deduplication
    op.create_unique_constraint(
        'uq_usage_metric_tenant_type_resource_period',
        'usage_metric',
        ['tenant_id', 'metric_type', 'resource_id', 'period_start', 'period_type']
    )


def downgrade() -> None:
    """Remove usage metering tables."""
    op.drop_constraint('uq_usage_metric_tenant_type_resource_period', 'usage_metric', type_='unique')
    op.drop_index('idx_usage_metric_tenant_period_type', table_name='usage_metric')
    op.drop_index('idx_usage_metric_tenant_type_period', table_name='usage_metric')
    op.drop_index('idx_usage_metric_period', table_name='usage_metric')
    op.drop_index('idx_usage_metric_type', table_name='usage_metric')
    op.drop_index('idx_usage_metric_tenant', table_name='usage_metric')
    op.drop_table('usage_metric')
