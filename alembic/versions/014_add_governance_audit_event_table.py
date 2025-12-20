"""Add governance audit event table

Revision ID: 014_gov_audit_event
Revises: 013_add_onboarding_tables
Create Date: 2025-01-28 16:00:00.000000

Phase 12+ Governance & Audit Polish:
Adds governance_audit_event table for enterprise-grade audit trail.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '014_gov_audit_event'
down_revision: Union[str, None] = '013_add_onboarding_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create governance_audit_event table
    op.create_table(
        'governance_audit_event',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('actor_id', sa.String(255), nullable=False),
        sa.Column('actor_role', sa.String(50), nullable=True),
        sa.Column('tenant_id', sa.String(255), nullable=True),
        sa.Column('domain', sa.String(100), nullable=True),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.String(255), nullable=False),
        sa.Column('entity_version', sa.String(50), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('before_json', postgresql.JSONB(), nullable=True),
        sa.Column('after_json', postgresql.JSONB(), nullable=True),
        sa.Column('diff_summary', sa.Text(), nullable=True),
        sa.Column('correlation_id', sa.String(100), nullable=True),
        sa.Column('request_id', sa.String(100), nullable=True),
        sa.Column('related_exception_id', sa.String(255), nullable=True),
        sa.Column('related_change_request_id', sa.String(36), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create single-column indexes
    op.create_index('ix_gov_audit_event_type', 'governance_audit_event', ['event_type'])
    op.create_index('ix_gov_audit_actor_id', 'governance_audit_event', ['actor_id'])
    op.create_index('ix_gov_audit_tenant_id', 'governance_audit_event', ['tenant_id'])
    op.create_index('ix_gov_audit_domain', 'governance_audit_event', ['domain'])
    op.create_index('ix_gov_audit_entity_type', 'governance_audit_event', ['entity_type'])
    op.create_index('ix_gov_audit_entity_id', 'governance_audit_event', ['entity_id'])
    op.create_index('ix_gov_audit_action', 'governance_audit_event', ['action'])
    op.create_index('ix_gov_audit_correlation_id', 'governance_audit_event', ['correlation_id'])
    op.create_index('ix_gov_audit_request_id', 'governance_audit_event', ['request_id'])
    op.create_index('ix_gov_audit_related_exception_id', 'governance_audit_event', ['related_exception_id'])
    op.create_index('ix_gov_audit_related_change_request_id', 'governance_audit_event', ['related_change_request_id'])
    op.create_index('ix_gov_audit_created_at', 'governance_audit_event', ['created_at'])

    # Create composite indexes for common query patterns
    op.create_index('idx_gov_audit_tenant_created', 'governance_audit_event', ['tenant_id', 'created_at'])
    op.create_index('idx_gov_audit_entity_type_id', 'governance_audit_event', ['entity_type', 'entity_id'])
    op.create_index('idx_gov_audit_tenant_entity', 'governance_audit_event', ['tenant_id', 'entity_type', 'entity_id'])
    op.create_index('idx_gov_audit_actor_created', 'governance_audit_event', ['actor_id', 'created_at'])
    op.create_index('idx_gov_audit_action_created', 'governance_audit_event', ['action', 'created_at'])
    op.create_index('idx_gov_audit_domain_created', 'governance_audit_event', ['domain', 'created_at'])
    op.create_index('idx_gov_audit_correlation', 'governance_audit_event', ['correlation_id'])


def downgrade() -> None:
    # Drop composite indexes
    op.drop_index('idx_gov_audit_correlation', table_name='governance_audit_event')
    op.drop_index('idx_gov_audit_domain_created', table_name='governance_audit_event')
    op.drop_index('idx_gov_audit_action_created', table_name='governance_audit_event')
    op.drop_index('idx_gov_audit_actor_created', table_name='governance_audit_event')
    op.drop_index('idx_gov_audit_tenant_entity', table_name='governance_audit_event')
    op.drop_index('idx_gov_audit_entity_type_id', table_name='governance_audit_event')
    op.drop_index('idx_gov_audit_tenant_created', table_name='governance_audit_event')

    # Drop single-column indexes
    op.drop_index('ix_gov_audit_created_at', table_name='governance_audit_event')
    op.drop_index('ix_gov_audit_related_change_request_id', table_name='governance_audit_event')
    op.drop_index('ix_gov_audit_related_exception_id', table_name='governance_audit_event')
    op.drop_index('ix_gov_audit_request_id', table_name='governance_audit_event')
    op.drop_index('ix_gov_audit_correlation_id', table_name='governance_audit_event')
    op.drop_index('ix_gov_audit_action', table_name='governance_audit_event')
    op.drop_index('ix_gov_audit_entity_id', table_name='governance_audit_event')
    op.drop_index('ix_gov_audit_entity_type', table_name='governance_audit_event')
    op.drop_index('ix_gov_audit_domain', table_name='governance_audit_event')
    op.drop_index('ix_gov_audit_tenant_id', table_name='governance_audit_event')
    op.drop_index('ix_gov_audit_actor_id', table_name='governance_audit_event')
    op.drop_index('ix_gov_audit_event_type', table_name='governance_audit_event')

    # Drop table
    op.drop_table('governance_audit_event')
