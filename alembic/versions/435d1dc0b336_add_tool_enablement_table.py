"""Add tool_enablement table

Revision ID: 435d1dc0b336
Revises: 002_add_tool_execution
Create Date: 2025-01-28 14:00:00.000000

Phase 8 P8-7: Add tool_enablement table for per-tenant tool enablement policy.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '435d1dc0b336'
down_revision: Union[str, None] = '002_add_tool_execution'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create tool_enablement table
    op.create_table(
        'tool_enablement',
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('tool_id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tool_id'], ['tool_definition.tool_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tenant_id', 'tool_id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_tool_enablement_tenant_id'), 'tool_enablement', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_tool_enablement_tool_id'), 'tool_enablement', ['tool_id'], unique=False)
    op.create_index('idx_tool_enablement_tenant_tool', 'tool_enablement', ['tenant_id', 'tool_id'], unique=True)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_tool_enablement_tenant_tool', table_name='tool_enablement')
    op.drop_index(op.f('ix_tool_enablement_tool_id'), table_name='tool_enablement')
    op.drop_index(op.f('ix_tool_enablement_tenant_id'), table_name='tool_enablement')
    
    # Drop table
    op.drop_table('tool_enablement')
