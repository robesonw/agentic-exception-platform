"""Add copilot intelligence tables for Phase 13

Revision ID: 015_copilot_tables
Revises: 014_gov_audit_event
Create Date: 2025-01-29 10:00:00.000000

Phase 13 Copilot Intelligence MVP:
- copilot_documents: Vector-indexed documents for RAG retrieval (with pgvector)
- copilot_sessions: Conversation session management
- copilot_messages: Individual messages in sessions

References:
- docs/phase13-copilot-intelligence-mvp.md Section 4.2, 5
- .github/ISSUE_TEMPLATE/phase13-copilot-intelligence-issues.md P13-1, P13-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '015_copilot_tables'
down_revision: Union[str, None] = '014_gov_audit_event'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOTE: pgvector extension is optional. If you want native vector operations,
    # install pgvector on your PostgreSQL server. Otherwise, we use JSONB storage
    # and compute cosine similarity in the application layer.
    # To enable pgvector, run: CREATE EXTENSION IF NOT EXISTS vector;
    # on your database separately before running migrations.

    # =========================================================================
    # copilot_documents table - Vector storage for RAG
    # =========================================================================
    op.create_table(
        'copilot_documents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(255), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_id', sa.String(255), nullable=False),
        sa.Column('domain', sa.String(100), nullable=True),
        sa.Column('chunk_id', sa.String(100), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('content', sa.Text(), nullable=False),
        # embedding stored as JSONB for compatibility; use pgvector in queries
        sa.Column('embedding', postgresql.JSONB(), nullable=True),
        sa.Column('embedding_model', sa.String(100), nullable=True),
        sa.Column('embedding_dimension', sa.Integer(), nullable=True),
        sa.Column('metadata_json', postgresql.JSONB(), nullable=True),
        sa.Column('version', sa.String(50), nullable=True),
        sa.Column('content_hash', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Single-column indexes for copilot_documents
    op.create_index('ix_copilot_doc_tenant_id', 'copilot_documents', ['tenant_id'])
    op.create_index('ix_copilot_doc_source_type', 'copilot_documents', ['source_type'])
    op.create_index('ix_copilot_doc_source_id', 'copilot_documents', ['source_id'])
    op.create_index('ix_copilot_doc_domain', 'copilot_documents', ['domain'])
    op.create_index('ix_copilot_doc_content_hash', 'copilot_documents', ['content_hash'])

    # Composite indexes for copilot_documents
    op.create_index('idx_copilot_doc_tenant_source_type', 'copilot_documents', ['tenant_id', 'source_type'])
    op.create_index('idx_copilot_doc_tenant_domain', 'copilot_documents', ['tenant_id', 'domain'])
    op.create_index('idx_copilot_doc_tenant_source_id', 'copilot_documents', ['tenant_id', 'source_id'])

    # Unique constraint
    op.create_unique_constraint(
        'uq_copilot_doc_tenant_source_chunk',
        'copilot_documents',
        ['tenant_id', 'source_type', 'source_id', 'chunk_id']
    )

    # =========================================================================
    # copilot_sessions table - Conversation sessions
    # =========================================================================
    op.create_table(
        'copilot_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(255), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('context_json', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.PrimaryKeyConstraint('id')
    )

    # Single-column indexes for copilot_sessions
    op.create_index('ix_copilot_session_tenant_id', 'copilot_sessions', ['tenant_id'])
    op.create_index('ix_copilot_session_user_id', 'copilot_sessions', ['user_id'])

    # Composite indexes for copilot_sessions
    op.create_index('idx_copilot_session_tenant_user', 'copilot_sessions', ['tenant_id', 'user_id'])
    op.create_index('idx_copilot_session_tenant_active', 'copilot_sessions', ['tenant_id', 'is_active'])
    op.create_index('idx_copilot_session_last_activity', 'copilot_sessions', ['last_activity_at'])
    op.create_index('idx_copilot_session_expires', 'copilot_sessions', ['expires_at'])

    # =========================================================================
    # copilot_messages table - Messages in sessions
    # =========================================================================
    op.create_table(
        'copilot_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata_json', postgresql.JSONB(), nullable=True),
        sa.Column('intent', sa.String(50), nullable=True),
        sa.Column('request_id', sa.String(100), nullable=True),
        sa.Column('exception_id', sa.String(255), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['copilot_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Single-column indexes for copilot_messages
    op.create_index('ix_copilot_msg_session_id', 'copilot_messages', ['session_id'])
    op.create_index('ix_copilot_msg_tenant_id', 'copilot_messages', ['tenant_id'])
    op.create_index('ix_copilot_msg_created_at', 'copilot_messages', ['created_at'])

    # Composite indexes for copilot_messages
    op.create_index('idx_copilot_msg_session_created', 'copilot_messages', ['session_id', 'created_at'])
    op.create_index('idx_copilot_msg_tenant_created', 'copilot_messages', ['tenant_id', 'created_at'])
    op.create_index('idx_copilot_msg_request_id', 'copilot_messages', ['request_id'])
    op.create_index('idx_copilot_msg_exception_id', 'copilot_messages', ['exception_id'])


def downgrade() -> None:
    # Drop copilot_messages table
    op.drop_index('idx_copilot_msg_exception_id', table_name='copilot_messages')
    op.drop_index('idx_copilot_msg_request_id', table_name='copilot_messages')
    op.drop_index('idx_copilot_msg_tenant_created', table_name='copilot_messages')
    op.drop_index('idx_copilot_msg_session_created', table_name='copilot_messages')
    op.drop_index('ix_copilot_msg_created_at', table_name='copilot_messages')
    op.drop_index('ix_copilot_msg_tenant_id', table_name='copilot_messages')
    op.drop_index('ix_copilot_msg_session_id', table_name='copilot_messages')
    op.drop_table('copilot_messages')

    # Drop copilot_sessions table
    op.drop_index('idx_copilot_session_expires', table_name='copilot_sessions')
    op.drop_index('idx_copilot_session_last_activity', table_name='copilot_sessions')
    op.drop_index('idx_copilot_session_tenant_active', table_name='copilot_sessions')
    op.drop_index('idx_copilot_session_tenant_user', table_name='copilot_sessions')
    op.drop_index('ix_copilot_session_user_id', table_name='copilot_sessions')
    op.drop_index('ix_copilot_session_tenant_id', table_name='copilot_sessions')
    op.drop_table('copilot_sessions')

    # Drop copilot_documents table
    op.drop_constraint('uq_copilot_doc_tenant_source_chunk', 'copilot_documents', type_='unique')
    op.drop_index('idx_copilot_doc_tenant_source_id', table_name='copilot_documents')
    op.drop_index('idx_copilot_doc_tenant_domain', table_name='copilot_documents')
    op.drop_index('idx_copilot_doc_tenant_source_type', table_name='copilot_documents')
    op.drop_index('ix_copilot_doc_content_hash', table_name='copilot_documents')
    op.drop_index('ix_copilot_doc_domain', table_name='copilot_documents')
    op.drop_index('ix_copilot_doc_source_id', table_name='copilot_documents')
    op.drop_index('ix_copilot_doc_source_type', table_name='copilot_documents')
    op.drop_index('ix_copilot_doc_tenant_id', table_name='copilot_documents')
    op.drop_table('copilot_documents')

    # Note: We don't drop the pgvector extension as it may be used by other tables
