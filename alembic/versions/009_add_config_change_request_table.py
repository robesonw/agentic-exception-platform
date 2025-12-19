"""Add config_change_request table for P10-10

Phase 10: Config Change Governance.
Adds config change request table to track configuration changes:
- Domain Pack changes
- Tenant Policy Pack changes
- Tool definition changes
- Playbook changes

Supports workflow: submit -> review -> approve/reject -> apply

Revision ID: 009
Revises: 008_add_alerting_tables
Create Date: 2025-01-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add config_change_request table."""
    op.create_table(
        'config_change_request',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('change_type', sa.String(50), nullable=False),  # domain_pack, tenant_policy, tool, playbook
        sa.Column('resource_id', sa.String(255), nullable=False),  # ID of the resource being changed
        sa.Column('resource_name', sa.String(255), nullable=True),  # Human-readable name
        sa.Column('current_config', JSONB, nullable=True),  # Snapshot of current config
        sa.Column('proposed_config', JSONB, nullable=False),  # Proposed new config
        sa.Column('diff_summary', sa.Text(), nullable=True),  # Human-readable diff
        sa.Column('change_reason', sa.Text(), nullable=True),  # Reason for change
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),  # pending, approved, rejected, applied
        sa.Column('requested_by', sa.String(255), nullable=False),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('reviewed_by', sa.String(255), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_comment', sa.Text(), nullable=True),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('applied_by', sa.String(255), nullable=True),
        sa.Column('rollback_config', JSONB, nullable=True),  # Config to rollback to if needed
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create indexes for common queries
    op.create_index('idx_config_change_tenant', 'config_change_request', ['tenant_id'])
    op.create_index('idx_config_change_status', 'config_change_request', ['status'])
    op.create_index('idx_config_change_tenant_status', 'config_change_request', ['tenant_id', 'status'])
    op.create_index('idx_config_change_type', 'config_change_request', ['change_type'])
    op.create_index('idx_config_change_requested_at', 'config_change_request', ['requested_at'])


def downgrade() -> None:
    """Remove config_change_request table."""
    op.drop_index('idx_config_change_requested_at', table_name='config_change_request')
    op.drop_index('idx_config_change_type', table_name='config_change_request')
    op.drop_index('idx_config_change_tenant_status', table_name='config_change_request')
    op.drop_index('idx_config_change_status', table_name='config_change_request')
    op.drop_index('idx_config_change_tenant', table_name='config_change_request')
    op.drop_table('config_change_request')
