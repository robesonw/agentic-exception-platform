"""Add rate limit tables for P10-15 to P10-17

Phase 10: Rate Limiting.
Adds tables for per-tenant rate limiting:
- rate_limit_config: Per-tenant rate limit settings
- rate_limit_usage: Usage tracking for rate limits

Revision ID: 011
Revises: 010_add_audit_report_table
Create Date: 2025-01-18
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add rate limit tables."""
    # Create rate_limit_config table
    op.create_table(
        'rate_limit_config',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('limit_type', sa.String(50), nullable=False),  # api_requests, events_ingested, tool_executions, report_generations
        sa.Column('limit_value', sa.Integer(), nullable=False),  # Max allowed per window
        sa.Column('window_seconds', sa.Integer(), nullable=False, server_default='60'),  # Time window (default 60 seconds)
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'limit_type', name='uq_rate_limit_config_tenant_type'),
    )

    # Create indexes for rate_limit_config
    op.create_index('idx_rate_limit_config_tenant', 'rate_limit_config', ['tenant_id'])
    op.create_index('idx_rate_limit_config_type', 'rate_limit_config', ['limit_type'])

    # Create rate_limit_usage table
    op.create_table(
        'rate_limit_usage',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('limit_type', sa.String(50), nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('current_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'limit_type', 'window_start', name='uq_rate_limit_usage_tenant_type_window'),
    )

    # Create indexes for rate_limit_usage
    op.create_index('idx_rate_limit_usage_tenant', 'rate_limit_usage', ['tenant_id'])
    op.create_index('idx_rate_limit_usage_type', 'rate_limit_usage', ['limit_type'])
    op.create_index('idx_rate_limit_usage_window', 'rate_limit_usage', ['window_start'])
    op.create_index('idx_rate_limit_usage_tenant_type', 'rate_limit_usage', ['tenant_id', 'limit_type'])


def downgrade() -> None:
    """Remove rate limit tables."""
    op.drop_index('idx_rate_limit_usage_tenant_type', table_name='rate_limit_usage')
    op.drop_index('idx_rate_limit_usage_window', table_name='rate_limit_usage')
    op.drop_index('idx_rate_limit_usage_type', table_name='rate_limit_usage')
    op.drop_index('idx_rate_limit_usage_tenant', table_name='rate_limit_usage')
    op.drop_table('rate_limit_usage')

    op.drop_index('idx_rate_limit_config_type', table_name='rate_limit_config')
    op.drop_index('idx_rate_limit_config_tenant', table_name='rate_limit_config')
    op.drop_table('rate_limit_config')
