"""Add onboarding tables

Revision ID: 013_add_onboarding_tables
Revises: 012
Create Date: 2025-01-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '013_add_onboarding_tables'
down_revision: Union[str, None] = '012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add created_by column to tenant table (nullable for backward compatibility)
    op.add_column('tenant', sa.Column('created_by', sa.String(), nullable=True))
    
    # Create pack_status enum
    pack_status_enum = postgresql.ENUM('draft', 'active', 'deprecated', name='pack_status', create_type=True)
    pack_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create domain_packs table
    op.create_table(
        'domain_packs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('domain', sa.String(), nullable=False),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('content_json', postgresql.JSONB(), nullable=False),
        sa.Column('checksum', sa.String(), nullable=False),
        sa.Column('status', postgresql.ENUM('draft', 'active', 'deprecated', name='pack_status', create_type=False), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('domain', 'version', name='uq_domain_packs_domain_version')
    )
    op.create_index(op.f('ix_domain_packs_domain'), 'domain_packs', ['domain'], unique=False)
    op.create_index(op.f('ix_domain_packs_version'), 'domain_packs', ['version'], unique=False)
    op.create_index(op.f('ix_domain_packs_status'), 'domain_packs', ['status'], unique=False)
    
    # Create tenant_packs table
    op.create_table(
        'tenant_packs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('content_json', postgresql.JSONB(), nullable=False),
        sa.Column('checksum', sa.String(), nullable=False),
        sa.Column('status', postgresql.ENUM('draft', 'active', 'deprecated', name='pack_status', create_type=False), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'version', name='uq_tenant_packs_tenant_version')
    )
    op.create_index(op.f('ix_tenant_packs_tenant_id'), 'tenant_packs', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_tenant_packs_version'), 'tenant_packs', ['version'], unique=False)
    op.create_index(op.f('ix_tenant_packs_status'), 'tenant_packs', ['status'], unique=False)
    
    # Create tenant_active_config table
    op.create_table(
        'tenant_active_config',
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('active_domain_pack_version', sa.String(), nullable=True),
        sa.Column('active_tenant_pack_version', sa.String(), nullable=True),
        sa.Column('activated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('activated_by', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tenant_id')
    )


def downgrade() -> None:
    # Drop tenant_active_config table
    op.drop_table('tenant_active_config')
    
    # Drop tenant_packs table
    op.drop_index(op.f('ix_tenant_packs_status'), table_name='tenant_packs')
    op.drop_index(op.f('ix_tenant_packs_version'), table_name='tenant_packs')
    op.drop_index(op.f('ix_tenant_packs_tenant_id'), table_name='tenant_packs')
    op.drop_table('tenant_packs')
    
    # Drop domain_packs table
    op.drop_index(op.f('ix_domain_packs_status'), table_name='domain_packs')
    op.drop_index(op.f('ix_domain_packs_version'), table_name='domain_packs')
    op.drop_index(op.f('ix_domain_packs_domain'), table_name='domain_packs')
    op.drop_table('domain_packs')
    
    # Drop pack_status enum
    pack_status_enum = postgresql.ENUM(name='pack_status')
    pack_status_enum.drop(op.get_bind(), checkfirst=True)
    
    # Remove created_by column from tenant table
    op.drop_column('tenant', 'created_by')

