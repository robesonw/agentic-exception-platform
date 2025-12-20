"""Add tool_execution table

Revision ID: 002_add_tool_execution
Revises: 001_phase_6_initial
Create Date: 2025-01-28 12:00:00.000000

Phase 8 P8-3: Add tool_execution table for tracking tool executions.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_add_tool_execution'
down_revision: Union[str, None] = '001_phase_6_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create tool_execution_status enum
    tool_execution_status_enum = postgresql.ENUM(
        'requested', 'running', 'succeeded', 'failed',
        name='tool_execution_status',
        create_type=True
    )
    tool_execution_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create tool_execution table
    op.create_table(
        'tool_execution',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('tool_id', sa.Integer(), nullable=False),
        sa.Column('exception_id', sa.String(), nullable=True),
        sa.Column(
            'status',
            postgresql.ENUM(
                'requested', 'running', 'succeeded', 'failed',
                name='tool_execution_status',
                create_type=False
            ),
            nullable=False,
            server_default='requested'
        ),
        sa.Column(
            'requested_by_actor_type',
            postgresql.ENUM('agent', 'user', 'system', name='actor_type', create_type=False),
            nullable=False
        ),
        sa.Column('requested_by_actor_id', sa.String(), nullable=False),
        sa.Column('input_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('output_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tool_id'], ['tool_definition.tool_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['exception_id'], ['exception.exception_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_tool_execution_tenant_id'), 'tool_execution', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_tool_execution_tool_id'), 'tool_execution', ['tool_id'], unique=False)
    op.create_index(op.f('ix_tool_execution_exception_id'), 'tool_execution', ['exception_id'], unique=False)
    op.create_index('idx_tool_execution_tenant_tool', 'tool_execution', ['tenant_id', 'tool_id'], unique=False)
    op.create_index('idx_tool_execution_tenant_exception', 'tool_execution', ['tenant_id', 'exception_id'], unique=False)
    op.create_index('idx_tool_execution_tenant_status', 'tool_execution', ['tenant_id', 'status'], unique=False)
    op.create_index('idx_tool_execution_tenant_created', 'tool_execution', ['tenant_id', 'created_at'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_tool_execution_tenant_created', table_name='tool_execution')
    op.drop_index('idx_tool_execution_tenant_status', table_name='tool_execution')
    op.drop_index('idx_tool_execution_tenant_exception', table_name='tool_execution')
    op.drop_index('idx_tool_execution_tenant_tool', table_name='tool_execution')
    op.drop_index(op.f('ix_tool_execution_exception_id'), table_name='tool_execution')
    op.drop_index(op.f('ix_tool_execution_tool_id'), table_name='tool_execution')
    op.drop_index(op.f('ix_tool_execution_tenant_id'), table_name='tool_execution')
    
    # Drop table
    op.drop_table('tool_execution')
    
    # Drop enum type
    tool_execution_status_enum = postgresql.ENUM(name='tool_execution_status')
    tool_execution_status_enum.drop(op.get_bind(), checkfirst=True)










