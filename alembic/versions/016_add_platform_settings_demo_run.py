"""Add platform_settings and demo_run tables for demo system.

Revision ID: 016_platform_settings_demo
Revises: 4f29dbca11b7
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision: str = '016_platform_settings_demo'
down_revision: Union[str, None] = '4f29dbca11b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create platform_settings and demo_run tables."""
    
    # Create platform_settings table
    op.create_table(
        'platform_settings',
        sa.Column('key', sa.String(length=255), primary_key=True, nullable=False,
                  comment='Setting key (e.g., demo.enabled, demo.scenarios.mode)'),
        sa.Column('value_json', JSONB, nullable=True,
                  comment='JSON value for complex settings'),
        sa.Column('value_text', sa.String, nullable=True,
                  comment='Text value for simple string settings'),
        sa.Column('value_type', sa.String(length=50), nullable=False, default='string',
                  comment='Type hint: string, boolean, number, json, timestamp'),
        sa.Column('description', sa.Text, nullable=True,
                  comment='Human-readable description of the setting'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  onupdate=sa.func.now(), nullable=False),
        sa.Column('updated_by', sa.String(length=255), nullable=True,
                  comment='User/system that last updated this setting'),
        sa.Column('audit_reason', sa.Text, nullable=True,
                  comment='Reason for the last change'),
    )
    
    # Create demo_run table for tracking demo scenario runs
    op.create_table(
        'demo_run',
        sa.Column('run_id', UUID(as_uuid=True), primary_key=True,
                  comment='Unique run identifier'),
        sa.Column('status', sa.String(length=50), nullable=False, default='pending',
                  comment='Status: pending, running, completed, cancelled, failed'),
        sa.Column('mode', sa.String(length=50), nullable=False,
                  comment='Mode: burst, scheduled, continuous'),
        sa.Column('scenario_ids', JSONB, nullable=False, default=[],
                  comment='Array of scenario IDs being run'),
        sa.Column('tenant_keys', JSONB, nullable=False, default=[],
                  comment='Array of tenant keys (empty = all demo tenants)'),
        sa.Column('frequency_seconds', sa.Integer, nullable=True,
                  comment='Generation frequency in seconds'),
        sa.Column('duration_seconds', sa.Integer, nullable=True,
                  comment='Scheduled run duration in seconds'),
        sa.Column('burst_count', sa.Integer, nullable=True,
                  comment='Number of exceptions for burst mode'),
        sa.Column('intensity_multiplier', sa.Float, nullable=True, default=1.0,
                  comment='Exception count multiplier'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True,
                  comment='When the run started'),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True,
                  comment='When the scheduled run should end'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True,
                  comment='When the run completed/cancelled/failed'),
        sa.Column('generated_count', sa.Integer, nullable=False, default=0,
                  comment='Number of exceptions generated so far'),
        sa.Column('last_tick_at', sa.DateTime(timezone=True), nullable=True,
                  comment='Timestamp of last generation tick'),
        sa.Column('error', sa.Text, nullable=True,
                  comment='Error message if failed'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
    )
    
    # Create index for finding active runs
    op.create_index(
        'idx_demo_run_status',
        'demo_run',
        ['status']
    )
    
    # Add simulation fields to tool_definition table
    op.add_column(
        'tool_definition',
        sa.Column('execution_mode', sa.String(length=50), nullable=True,
                  server_default='http',
                  comment='Execution mode: simulate, http, webhook, queue')
    )
    op.add_column(
        'tool_definition',
        sa.Column('simulate_profile', sa.String(length=50), nullable=True,
                  comment='Simulation profile: success, fail, delayed, flaky')
    )
    op.add_column(
        'tool_definition',
        sa.Column('simulate_latency_ms', JSONB, nullable=True,
                  comment='Simulation latency range: {min: number, max: number}')
    )
    op.add_column(
        'tool_definition',
        sa.Column('simulate_result_template', JSONB, nullable=True,
                  comment='Template for simulated response')
    )
    
    # Add demo tags to tenant table
    op.add_column(
        'tenant',
        sa.Column('tags', JSONB, nullable=True, server_default='[]',
                  comment='Tags array (e.g., ["demo", "finance"])')
    )
    op.add_column(
        'tenant',
        sa.Column('industry', sa.String(length=100), nullable=True,
                  comment='Industry type: finance, insurance, healthcare, retail, saas_ops')
    )
    op.add_column(
        'tenant',
        sa.Column('metadata', JSONB, nullable=True, server_default='{}',
                  comment='Additional tenant metadata')
    )


def downgrade() -> None:
    """Drop platform_settings and demo_run tables."""
    
    # Remove tenant columns
    op.drop_column('tenant', 'metadata')
    op.drop_column('tenant', 'industry')
    op.drop_column('tenant', 'tags')
    
    # Remove tool_definition columns
    op.drop_column('tool_definition', 'simulate_result_template')
    op.drop_column('tool_definition', 'simulate_latency_ms')
    op.drop_column('tool_definition', 'simulate_profile')
    op.drop_column('tool_definition', 'execution_mode')
    
    # Drop demo_run table
    op.drop_index('idx_demo_run_status', table_name='demo_run')
    op.drop_table('demo_run')
    
    # Drop platform_settings table
    op.drop_table('platform_settings')
