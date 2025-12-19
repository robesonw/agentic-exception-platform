"""Add audit_report table for P10-11 to P10-14

Phase 10: Audit Reports.
Adds table to track generated audit reports:
- Exception Activity reports
- Tool Execution reports
- Policy Decisions reports
- Config Changes reports
- SLA Compliance reports

Revision ID: 010
Revises: 009_add_config_change_request_table
Create Date: 2025-01-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add audit_report table."""
    op.create_table(
        'audit_report',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('report_type', sa.String(50), nullable=False),  # exception_activity, tool_execution, policy_decisions, config_changes, sla_compliance
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),  # pending, generating, completed, failed
        sa.Column('format', sa.String(10), nullable=False, server_default='json'),  # json, csv, pdf
        sa.Column('parameters', JSONB, nullable=True),  # Report generation parameters (date range, filters, etc.)
        sa.Column('file_path', sa.String(500), nullable=True),  # Path to generated file
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('download_url', sa.String(1000), nullable=True),  # Signed URL for download
        sa.Column('download_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('row_count', sa.Integer(), nullable=True),  # Number of rows/records in report
        sa.Column('error_message', sa.Text(), nullable=True),  # Error if generation failed
        sa.Column('requested_by', sa.String(255), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create indexes for common queries
    op.create_index('idx_audit_report_tenant', 'audit_report', ['tenant_id'])
    op.create_index('idx_audit_report_status', 'audit_report', ['status'])
    op.create_index('idx_audit_report_tenant_status', 'audit_report', ['tenant_id', 'status'])
    op.create_index('idx_audit_report_type', 'audit_report', ['report_type'])
    op.create_index('idx_audit_report_created_at', 'audit_report', ['created_at'])


def downgrade() -> None:
    """Remove audit_report table."""
    op.drop_index('idx_audit_report_created_at', table_name='audit_report')
    op.drop_index('idx_audit_report_type', table_name='audit_report')
    op.drop_index('idx_audit_report_tenant_status', table_name='audit_report')
    op.drop_index('idx_audit_report_status', table_name='audit_report')
    op.drop_index('idx_audit_report_tenant', table_name='audit_report')
    op.drop_table('audit_report')
