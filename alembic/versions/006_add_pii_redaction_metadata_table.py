"""Add pii_redaction_metadata table

Phase 9 P9-24: PII redaction metadata storage.

Revision ID: 006_add_pii_redaction_metadata
Revises: 005_add_dead_letter_events
Create Date: 2024-01-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006_add_pii_redaction_metadata'
down_revision = '005_add_dead_letter_events'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create pii_redaction_metadata table
    op.create_table(
        'pii_redaction_metadata',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('exception_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('redacted_fields', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('redaction_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('redaction_placeholder', sa.String(), nullable=False, server_default='[REDACTED]'),
        sa.Column('redacted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['exception_id'], ['exception.exception_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create indexes
    op.create_index('idx_pii_redaction_exception', 'pii_redaction_metadata', ['exception_id'])
    op.create_index('idx_pii_redaction_tenant', 'pii_redaction_metadata', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('idx_pii_redaction_tenant', table_name='pii_redaction_metadata')
    op.drop_index('idx_pii_redaction_exception', table_name='pii_redaction_metadata')
    op.drop_table('pii_redaction_metadata')


