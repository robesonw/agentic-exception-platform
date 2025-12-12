"""Phase 6 initial schema

Revision ID: 001_phase_6_initial
Revises: 
Create Date: 2025-01-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_phase_6_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    tenant_status_enum = postgresql.ENUM('active', 'suspended', 'archived', name='tenant_status', create_type=True)
    tenant_status_enum.create(op.get_bind(), checkfirst=True)
    
    exception_severity_enum = postgresql.ENUM('low', 'medium', 'high', 'critical', name='exception_severity', create_type=True)
    exception_severity_enum.create(op.get_bind(), checkfirst=True)
    
    exception_status_enum = postgresql.ENUM('open', 'analyzing', 'resolved', 'escalated', name='exception_status', create_type=True)
    exception_status_enum.create(op.get_bind(), checkfirst=True)
    
    actor_type_enum = postgresql.ENUM('agent', 'user', 'system', name='actor_type', create_type=True)
    actor_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Create tenant table
    op.create_table(
        'tenant',
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('status', postgresql.ENUM('active', 'suspended', 'archived', name='tenant_status', create_type=False), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('tenant_id')
    )
    
    # Create domain_pack_version table
    op.create_table(
        'domain_pack_version',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('domain', sa.String(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('pack_json', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('domain', 'version', name='uq_domain_pack_version')
    )
    op.create_index(op.f('ix_domain_pack_version_domain'), 'domain_pack_version', ['domain'], unique=False)
    
    # Create tenant_policy_pack_version table
    op.create_table(
        'tenant_policy_pack_version',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('pack_json', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'version', name='uq_tenant_policy_pack_version')
    )
    op.create_index(op.f('ix_tenant_policy_pack_version_tenant_id'), 'tenant_policy_pack_version', ['tenant_id'], unique=False)
    
    # Create playbook table (needed before exception table due to FK)
    op.create_table(
        'playbook',
        sa.Column('playbook_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('conditions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('playbook_id')
    )
    op.create_index(op.f('ix_playbook_tenant_id'), 'playbook', ['tenant_id'], unique=False)
    
    # Create exception table
    op.create_table(
        'exception',
        sa.Column('exception_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('domain', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('severity', postgresql.ENUM('low', 'medium', 'high', 'critical', name='exception_severity', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('open', 'analyzing', 'resolved', 'escalated', name='exception_status', create_type=False), nullable=False, server_default='open'),
        sa.Column('source_system', sa.String(), nullable=False),
        sa.Column('entity', sa.String(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('sla_deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('owner', sa.String(), nullable=True),
        sa.Column('current_playbook_id', sa.Integer(), nullable=True),
        sa.Column('current_step', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['current_playbook_id'], ['playbook.playbook_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('exception_id'),
        sa.UniqueConstraint('exception_id', 'tenant_id', name='uq_exception_tenant')
    )
    op.create_index(op.f('ix_exception_tenant_id'), 'exception', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_exception_domain'), 'exception', ['domain'], unique=False)
    op.create_index('idx_exception_tenant_domain_created', 'exception', ['tenant_id', 'domain', 'created_at'], unique=False)
    op.create_index('idx_exception_status_severity', 'exception', ['status', 'severity'], unique=False)
    
    # Create exception_event table
    op.create_table(
        'exception_event',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('exception_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('actor_type', postgresql.ENUM('agent', 'user', 'system', name='actor_type', create_type=False), nullable=False),
        sa.Column('actor_id', sa.String(), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['exception_id'], ['exception.exception_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('event_id')
    )
    op.create_index(op.f('ix_exception_event_exception_id'), 'exception_event', ['exception_id'], unique=False)
    op.create_index(op.f('ix_exception_event_tenant_id'), 'exception_event', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_exception_event_event_type'), 'exception_event', ['event_type'], unique=False)
    op.create_index(op.f('ix_exception_event_created_at'), 'exception_event', ['created_at'], unique=False)
    op.create_index('idx_exception_event_exception_created', 'exception_event', ['exception_id', 'created_at'], unique=False)
    op.create_index('idx_exception_event_tenant_created', 'exception_event', ['tenant_id', 'created_at'], unique=False)
    
    # Create playbook_step table
    op.create_table(
        'playbook_step',
        sa.Column('step_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('playbook_id', sa.Integer(), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('action_type', sa.String(), nullable=False),
        sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['playbook_id'], ['playbook.playbook_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('step_id')
    )
    op.create_index(op.f('ix_playbook_step_playbook_id'), 'playbook_step', ['playbook_id'], unique=False)
    op.create_index(op.f('ix_playbook_step_step_order'), 'playbook_step', ['step_order'], unique=False)
    
    # Create tool_definition table
    op.create_table(
        'tool_definition',
        sa.Column('tool_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=True),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tool_id')
    )
    op.create_index(op.f('ix_tool_definition_tenant_id'), 'tool_definition', ['tenant_id'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order (respecting foreign key dependencies)
    op.drop_table('tool_definition')
    op.drop_table('playbook_step')
    op.drop_table('exception_event')
    op.drop_table('exception')
    op.drop_table('playbook')
    op.drop_table('tenant_policy_pack_version')
    op.drop_table('domain_pack_version')
    op.drop_table('tenant')
    
    # Drop enum types
    actor_type_enum = postgresql.ENUM(name='actor_type')
    actor_type_enum.drop(op.get_bind(), checkfirst=True)
    
    exception_status_enum = postgresql.ENUM(name='exception_status')
    exception_status_enum.drop(op.get_bind(), checkfirst=True)
    
    exception_severity_enum = postgresql.ENUM(name='exception_severity')
    exception_severity_enum.drop(op.get_bind(), checkfirst=True)
    
    tenant_status_enum = postgresql.ENUM(name='tenant_status')
    tenant_status_enum.drop(op.get_bind(), checkfirst=True)

