"""
Integration tests for RetrievalService with real database interactions.

Tests the complete retrieval flow with PostgreSQL and pgvector.
"""

import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.copilot.retrieval.retrieval_service import RetrievalService
from src.services.copilot.embedding_service import EmbeddingService, EmbeddingConfig
from src.infrastructure.repositories.copilot_document_repository import CopilotDocumentRepository
from src.infrastructure.db.session import get_db_session
from src.infrastructure.db.models import CopilotDocument


@pytest.mark.integration
@pytest.mark.asyncio
class TestRetrievalServiceIntegration:
    """Integration tests for RetrievalService with real database."""
    
    @pytest.fixture
    async def db_session(self):
        """Get database session for testing."""
        async with get_db_session() as session:
            yield session
    
    @pytest.fixture
    def embedding_config(self):
        """Embedding configuration for testing."""
        return EmbeddingConfig(
            provider="mock",  # Use mock provider for testing
            model="mock-model",
            dimensions=384,
            api_key="test-key"
        )
    
    @pytest.fixture
    def embedding_service(self, embedding_config):
        """EmbeddingService instance for testing."""
        return EmbeddingService(embedding_config)
    
    @pytest.fixture
    def document_repository(self, db_session):
        """CopilotDocumentRepository instance for testing."""
        return CopilotDocumentRepository(db_session)
    
    @pytest.fixture
    def retrieval_service(self, embedding_service, document_repository):
        """RetrievalService instance with real dependencies."""
        return RetrievalService(embedding_service, document_repository)
    
    async def _seed_test_documents(self, db_session: AsyncSession, tenant_id, documents_data):
        """Helper to seed test documents in the database."""
        for doc_data in documents_data:
            document = CopilotDocument(
                tenant_id=tenant_id,
                source_type=doc_data["source_type"],
                source_id=doc_data["source_id"],
                source_version=doc_data.get("source_version", "v1.0"),
                title=doc_data["title"],
                chunk_text=doc_data["chunk_text"],
                url=doc_data.get("url"),
                domain=doc_data.get("domain"),
                embedding=doc_data.get("embedding", [0.1] * 384)  # Mock embedding
            )
            db_session.add(document)
        
        await db_session.commit()
    
    async def test_multi_tenant_isolation_integration(self, retrieval_service, db_session):
        """Test tenant isolation with real database."""
        tenant_a = uuid4()
        tenant_b = uuid4()
        
        # Seed documents for both tenants
        await self._seed_test_documents(db_session, tenant_a, [
            {
                "source_type": "PolicyDoc",
                "source_id": str(uuid4()),
                "title": "Tenant A Security Policy",
                "chunk_text": "Tenant A specific security policy requirements and procedures.",
                "domain": "security"
            }
        ])
        
        await self._seed_test_documents(db_session, tenant_b, [
            {
                "source_type": "PolicyDoc", 
                "source_id": str(uuid4()),
                "title": "Tenant B Security Policy",
                "chunk_text": "Tenant B specific security policy requirements and procedures.",
                "domain": "security"
            }
        ])
        
        # Test tenant A retrieval
        evidence_a = await retrieval_service.retrieve_evidence(
            tenant_id=tenant_a,
            query_text="security policy requirements"
        )
        
        # Test tenant B retrieval
        evidence_b = await retrieval_service.retrieve_evidence(
            tenant_id=tenant_b,
            query_text="security policy requirements"
        )
        
        # Verify isolation
        assert len(evidence_a) > 0
        assert len(evidence_b) > 0
        
        # Each tenant should only see their own documents
        for evidence in evidence_a:
            assert "Tenant A" in evidence.title or "Tenant A" in evidence.chunk_text
        
        for evidence in evidence_b:
            assert "Tenant B" in evidence.title or "Tenant B" in evidence.chunk_text
        
        # Cross-contamination check
        tenant_a_content = " ".join([e.chunk_text for e in evidence_a])
        tenant_b_content = " ".join([e.chunk_text for e in evidence_b])
        
        assert "Tenant B" not in tenant_a_content
        assert "Tenant A" not in tenant_b_content
    
    async def test_source_type_filtering_integration(self, retrieval_service, db_session):
        """Test source type filtering with real database."""
        tenant_id = uuid4()
        
        # Seed different source types
        await self._seed_test_documents(db_session, tenant_id, [
            {
                "source_type": "PolicyDoc",
                "source_id": str(uuid4()),
                "title": "Access Control Policy",
                "chunk_text": "Policy document about access control and authentication requirements."
            },
            {
                "source_type": "ResolvedException",
                "source_id": str(uuid4()),
                "title": "Authentication Exception Resolved",
                "chunk_text": "Exception about authentication failure that was successfully resolved."
            },
            {
                "source_type": "ToolRegistry",
                "source_id": str(uuid4()),
                "title": "Password Reset Tool",
                "chunk_text": "Tool for resetting user passwords when authentication fails."
            }
        ])
        
        # Test filtering by specific source types
        policy_evidence = await retrieval_service.retrieve_evidence(
            tenant_id=tenant_id,
            query_text="authentication",
            source_types=["PolicyDoc"]
        )
        
        exception_evidence = await retrieval_service.retrieve_evidence(
            tenant_id=tenant_id,
            query_text="authentication",
            source_types=["ResolvedException"]
        )
        
        # Verify filtering
        assert len(policy_evidence) > 0
        assert len(exception_evidence) > 0
        
        for evidence in policy_evidence:
            assert evidence.source_type == "PolicyDoc"
        
        for evidence in exception_evidence:
            assert evidence.source_type == "ResolvedException"
    
    async def test_domain_filtering_integration(self, retrieval_service, db_session):
        """Test domain filtering with real database."""
        tenant_id = uuid4()
        
        # Seed documents with different domains
        await self._seed_test_documents(db_session, tenant_id, [
            {
                "source_type": "PolicyDoc",
                "source_id": str(uuid4()),
                "title": "Financial Compliance Policy",
                "chunk_text": "Policy for financial data handling and compliance requirements.",
                "domain": "finance"
            },
            {
                "source_type": "PolicyDoc",
                "source_id": str(uuid4()),
                "title": "Healthcare Privacy Policy", 
                "chunk_text": "Policy for healthcare data privacy and HIPAA compliance.",
                "domain": "healthcare"
            }
        ])
        
        # Test domain filtering
        finance_evidence = await retrieval_service.retrieve_evidence(
            tenant_id=tenant_id,
            query_text="compliance policy",
            domain="finance"
        )
        
        healthcare_evidence = await retrieval_service.retrieve_evidence(
            tenant_id=tenant_id,
            query_text="compliance policy",
            domain="healthcare"
        )
        
        # Verify domain filtering
        assert len(finance_evidence) > 0
        assert len(healthcare_evidence) > 0
        
        # Finance evidence should only contain finance content
        finance_content = " ".join([e.chunk_text for e in finance_evidence])
        assert "financial" in finance_content.lower()
        assert "hipaa" not in finance_content.lower()
        
        # Healthcare evidence should only contain healthcare content  
        healthcare_content = " ".join([e.chunk_text for e in healthcare_evidence])
        assert "hipaa" in healthcare_content.lower()
        assert "financial" not in healthcare_content.lower()
    
    async def test_similarity_ranking_integration(self, retrieval_service, db_session):
        """Test that similarity ranking works correctly."""
        tenant_id = uuid4()
        
        # Seed documents with varying relevance
        await self._seed_test_documents(db_session, tenant_id, [
            {
                "source_type": "PolicyDoc",
                "source_id": str(uuid4()),
                "title": "Password Security Policy",
                "chunk_text": "Password must be strong with special characters and numbers for security.",
                "embedding": [0.9, 0.8, 0.7, 0.6] + [0.1] * 380  # High similarity mock
            },
            {
                "source_type": "PolicyDoc",
                "source_id": str(uuid4()),
                "title": "General Security Guidelines",
                "chunk_text": "General security guidelines for all users and administrators.",
                "embedding": [0.5, 0.4, 0.3, 0.2] + [0.1] * 380  # Medium similarity mock
            },
            {
                "source_type": "PolicyDoc",
                "source_id": str(uuid4()),
                "title": "Parking Policy",
                "chunk_text": "Policy for employee parking spaces and vehicle registration.",
                "embedding": [0.1, 0.1, 0.1, 0.1] + [0.1] * 380  # Low similarity mock
            }
        ])
        
        # Query for password security
        evidence = await retrieval_service.retrieve_evidence(
            tenant_id=tenant_id,
            query_text="password security policy"
        )
        
        # Verify ranking by similarity
        assert len(evidence) >= 2
        
        # First result should be most relevant (Password Security Policy)
        assert evidence[0].title == "Password Security Policy"
        assert "password" in evidence[0].chunk_text.lower()
        
        # Similarity scores should be in descending order
        for i in range(len(evidence) - 1):
            assert evidence[i].similarity_score >= evidence[i + 1].similarity_score
        
        # Parking policy should not be in top results due to low relevance
        parking_titles = [e.title for e in evidence[:2]]
        assert "Parking Policy" not in parking_titles
    
    async def test_snippet_extraction_integration(self, retrieval_service, db_session):
        """Test snippet extraction with real content."""
        tenant_id = uuid4()
        
        long_policy_text = """
        This is a comprehensive security policy document that contains many sections.
        
        Section 1: Password Requirements
        All passwords must be at least 12 characters long and contain uppercase letters,
        lowercase letters, numbers, and special characters. Passwords must not be reused
        for at least 12 months and must be changed every 90 days.
        
        Section 2: Access Control
        Access to systems must be granted on a need-to-know basis. All access requests
        must be approved by the appropriate manager and documented in the access log.
        
        Section 3: Data Handling
        Sensitive data must be encrypted both in transit and at rest. All data access
        must be logged and monitored for suspicious activity.
        """
        
        await self._seed_test_documents(db_session, tenant_id, [
            {
                "source_type": "PolicyDoc",
                "source_id": str(uuid4()),
                "title": "Comprehensive Security Policy",
                "chunk_text": long_policy_text
            }
        ])
        
        # Query for password requirements
        evidence = await retrieval_service.retrieve_evidence(
            tenant_id=tenant_id,
            query_text="password requirements"
        )
        
        assert len(evidence) > 0
        
        # Check snippet extraction
        snippet = evidence[0].snippet
        assert len(snippet) <= 300  # Default max length
        assert "password" in snippet.lower()
        
        # Snippet should contain relevant context
        assert "characters" in snippet.lower() or "uppercase" in snippet.lower()
    
    async def test_top_k_limiting_integration(self, retrieval_service, db_session):
        """Test top_k limiting with real database."""
        tenant_id = uuid4()
        
        # Seed many similar documents
        documents = []
        for i in range(8):
            documents.append({
                "source_type": "PolicyDoc",
                "source_id": str(uuid4()),
                "title": f"Security Policy {i}",
                "chunk_text": f"Security policy document number {i} with security guidelines."
            })
        
        await self._seed_test_documents(db_session, tenant_id, documents)
        
        # Test with different top_k values
        evidence_3 = await retrieval_service.retrieve_evidence(
            tenant_id=tenant_id,
            query_text="security policy",
            top_k=3
        )
        
        evidence_5 = await retrieval_service.retrieve_evidence(
            tenant_id=tenant_id,
            query_text="security policy",
            top_k=5
        )
        
        # Verify limits are respected
        assert len(evidence_3) <= 3
        assert len(evidence_5) <= 5
        assert len(evidence_5) >= len(evidence_3)
        
        # Top results should be the same in both queries
        if len(evidence_3) > 0 and len(evidence_5) > 0:
            assert evidence_3[0].source_id == evidence_5[0].source_id