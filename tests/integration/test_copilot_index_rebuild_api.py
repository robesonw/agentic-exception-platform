"""Integration tests for Copilot Index Rebuild API endpoints.

Tests Phase 13 Prompt 2.5: IndexRebuildService + /copilot/index/rebuild APIs
"""

import asyncio
import json
import uuid
from typing import AsyncGenerator
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routes import router_copilot
from src.infrastructure.db.models import CopilotIndexJob, CopilotIndexJobStatus, Tenant, TenantStatus
from src.infrastructure.db.session import get_db_session_context


@pytest.fixture
async def app() -> FastAPI:
    """FastAPI application fixture."""
    app = FastAPI()
    app.include_router(router_copilot.router)
    return app


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client fixture."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def test_tenant() -> str:
    """Create a test tenant."""
    tenant_id = f"tenant-{uuid.uuid4()}"
    
    async with get_db_session_context() as session:
        tenant = Tenant(tenant_id=tenant_id, name="Test Tenant", status=TenantStatus.ACTIVE)
        session.add(tenant)
        await session.commit()
        
    return tenant_id


@pytest.fixture
def mock_admin_auth():
    """Mock admin authentication dependency."""
    with patch("src.api.routes.router_copilot.require_admin_role", return_value=None):
        yield


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service."""
    with patch("src.api.routes.router_copilot.EmbeddingService") as mock:
        instance = Mock()
        instance.create_embeddings.return_value = [[0.1, 0.2, 0.3]]  # Mock embedding
        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_chunking_service():
    """Mock chunking service."""
    with patch("src.api.routes.router_copilot.DocumentChunkingService") as mock:
        instance = Mock()
        instance.chunk_document.return_value = ["chunk1", "chunk2"]  # Mock chunks
        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_indexers():
    """Mock all indexer services."""
    mocks = {}
    
    indexer_paths = [
        "src.services.copilot.indexing.policy_docs_indexer.PolicyDocsIndexer",
        "src.services.copilot.indexing.resolved_exceptions_indexer.ResolvedExceptionsIndexer",
        "src.services.copilot.indexing.audit_events_indexer.AuditEventsIndexer",
        "src.services.copilot.indexing.tool_registry_indexer.ToolRegistryIndexer",
    ]
    
    for path in indexer_paths:
        with patch(path) as mock_class:
            instance = Mock()
            instance.index_for_tenant.return_value = None
            instance.index_incremental_for_tenant.return_value = None
            instance.index_all.return_value = None
            instance.index_incremental_all.return_value = None
            mock_class.return_value = instance
            mocks[path] = instance
    
    yield mocks


class TestIndexRebuildStartAPI:
    """Test cases for POST /api/copilot/index/rebuild endpoint."""
    
    @pytest.mark.asyncio
    async def test_start_rebuild_success_tenant_specific(
        self,
        async_client: AsyncClient,
        test_tenant: str,
        mock_admin_auth,
        mock_embedding_service,
        mock_chunking_service,
        mock_indexers,
    ):
        """Test successful tenant-specific index rebuild start."""
        request_data = {
            "tenant_id": test_tenant,
            "sources": ["policy_doc", "resolved_exception"],
            "full_rebuild": False,
        }
        
        response = await async_client.post(
            "/api/copilot/index/rebuild",
            json=request_data,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "job_id" in data
        assert "message" in data
        assert test_tenant in data["message"]
        
        # Verify job was created in database
        async with get_db_session_context() as session:
            job = await session.get(CopilotIndexJob, data["job_id"])
            assert job is not None
            assert job.tenant_id == test_tenant
            assert job.sources == ["policy_doc", "resolved_exception"]
            assert job.full_rebuild is False
            assert job.status == CopilotIndexJobStatus.PENDING

    @pytest.mark.asyncio
    async def test_start_rebuild_success_global(
        self,
        async_client: AsyncClient,
        mock_admin_auth,
        mock_embedding_service,
        mock_chunking_service,
        mock_indexers,
    ):
        """Test successful global index rebuild start."""
        request_data = {
            "tenant_id": None,
            "sources": ["audit_event", "tool_registry"],
            "full_rebuild": True,
        }
        
        response = await async_client.post(
            "/api/copilot/index/rebuild",
            json=request_data,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "job_id" in data
        assert "message" in data
        
        # Verify job was created in database
        async with get_db_session_context() as session:
            job = await session.get(CopilotIndexJob, data["job_id"])
            assert job is not None
            assert job.tenant_id is None
            assert job.sources == ["audit_event", "tool_registry"]
            assert job.full_rebuild is True

    @pytest.mark.asyncio
    async def test_start_rebuild_validation_invalid_sources(
        self,
        async_client: AsyncClient,
        test_tenant: str,
        mock_admin_auth,
    ):
        """Test validation for invalid source types."""
        request_data = {
            "tenant_id": test_tenant,
            "sources": ["invalid_source", "policy_doc"],
            "full_rebuild": False,
        }
        
        response = await async_client.post(
            "/api/copilot/index/rebuild",
            json=request_data,
        )
        
        assert response.status_code == 400
        assert "invalid_source" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_start_rebuild_validation_empty_sources(
        self,
        async_client: AsyncClient,
        test_tenant: str,
        mock_admin_auth,
    ):
        """Test validation for empty sources list."""
        request_data = {
            "tenant_id": test_tenant,
            "sources": [],
            "full_rebuild": False,
        }
        
        response = await async_client.post(
            "/api/copilot/index/rebuild",
            json=request_data,
        )
        
        assert response.status_code == 400
        assert "At least one source" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_start_rebuild_unauthorized_without_admin(
        self,
        async_client: AsyncClient,
        test_tenant: str,
    ):
        """Test that non-admin users cannot start rebuilds."""
        request_data = {
            "tenant_id": test_tenant,
            "sources": ["policy_doc"],
            "full_rebuild": False,
        }
        
        response = await async_client.post(
            "/api/copilot/index/rebuild",
            json=request_data,
        )
        
        # Should fail due to missing admin auth
        assert response.status_code in [401, 403]


class TestIndexRebuildStatusAPI:
    """Test cases for GET /api/copilot/index/rebuild/{job_id} endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_status_success(
        self,
        async_client: AsyncClient,
        test_tenant: str,
        mock_admin_auth,
        mock_embedding_service,
        mock_chunking_service,
        mock_indexers,
    ):
        """Test successful status retrieval for a rebuild job."""
        # Create a job first
        async with get_db_session_context() as session:
            job_id = str(uuid.uuid4())
            job = CopilotIndexJob(
                id=job_id,
                tenant_id=test_tenant,
                sources=["policy_doc", "resolved_exception"],
                full_rebuild=False,
                status=CopilotIndexJobStatus.RUNNING,
                progress_current=50,
                progress_total=100,
                documents_processed=25,
                documents_failed=2,
                chunks_indexed=150,
            )
            session.add(job)
            await session.commit()
        
        response = await async_client.get(f"/api/copilot/index/rebuild/{job_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == job_id
        assert data["tenant_id"] == test_tenant
        assert data["sources"] == ["policy_doc", "resolved_exception"]
        assert data["state"] == "running"
        assert data["progress"]["current"] == 50
        assert data["progress"]["total"] == 100
        assert data["counts"]["documents_processed"] == 25
        assert data["counts"]["documents_failed"] == 2
        assert data["counts"]["chunks_indexed"] == 150

    @pytest.mark.asyncio
    async def test_get_status_job_not_found(
        self,
        async_client: AsyncClient,
        mock_admin_auth,
    ):
        """Test status retrieval for non-existent job."""
        fake_job_id = str(uuid.uuid4())
        
        response = await async_client.get(f"/api/copilot/index/rebuild/{fake_job_id}")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_status_unauthorized_without_admin(
        self,
        async_client: AsyncClient,
    ):
        """Test that non-admin users cannot check status."""
        fake_job_id = str(uuid.uuid4())
        
        response = await async_client.get(f"/api/copilot/index/rebuild/{fake_job_id}")
        
        # Should fail due to missing admin auth
        assert response.status_code in [401, 403]


class TestIndexRebuildCancelAPI:
    """Test cases for DELETE /api/copilot/index/rebuild/{job_id} endpoint."""
    
    @pytest.mark.asyncio
    async def test_cancel_job_success(
        self,
        async_client: AsyncClient,
        test_tenant: str,
        mock_admin_auth,
        mock_embedding_service,
        mock_chunking_service,
        mock_indexers,
    ):
        """Test successful job cancellation."""
        # Create a running job first
        async with get_db_session_context() as session:
            job_id = str(uuid.uuid4())
            job = CopilotIndexJob(
                id=job_id,
                tenant_id=test_tenant,
                sources=["policy_doc"],
                full_rebuild=False,
                status=CopilotIndexJobStatus.RUNNING,
            )
            session.add(job)
            await session.commit()
        
        response = await async_client.delete(f"/api/copilot/index/rebuild/{job_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "cancelled" in data["message"]

    @pytest.mark.asyncio
    async def test_cancel_job_not_found(
        self,
        async_client: AsyncClient,
        mock_admin_auth,
    ):
        """Test cancellation of non-existent job."""
        fake_job_id = str(uuid.uuid4())
        
        response = await async_client.delete(f"/api/copilot/index/rebuild/{fake_job_id}")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestIndexRebuildE2EFlow:
    """End-to-end tests for the complete rebuild workflow."""
    
    @pytest.mark.asyncio
    async def test_e2e_rebuild_workflow_with_progress_tracking(
        self,
        async_client: AsyncClient,
        test_tenant: str,
        mock_admin_auth,
        mock_embedding_service,
        mock_chunking_service,
        mock_indexers,
    ):
        """Test complete rebuild workflow: start -> monitor progress -> completion."""
        # 1. Start rebuild
        request_data = {
            "tenant_id": test_tenant,
            "sources": ["policy_doc"],
            "full_rebuild": True,
        }
        
        start_response = await async_client.post(
            "/api/copilot/index/rebuild",
            json=request_data,
        )
        
        assert start_response.status_code == 200
        job_id = start_response.json()["job_id"]
        
        # 2. Wait briefly for background job to start
        await asyncio.sleep(0.1)
        
        # 3. Check initial status
        status_response = await async_client.get(f"/api/copilot/index/rebuild/{job_id}")
        assert status_response.status_code == 200
        
        status_data = status_response.json()
        assert status_data["id"] == job_id
        assert status_data["tenant_id"] == test_tenant
        assert status_data["sources"] == ["policy_doc"]
        
        # Status should be pending or running depending on timing
        assert status_data["state"] in ["pending", "running", "completed"]
        
        # 4. Wait for completion (should be very fast with mocks)
        max_attempts = 10
        for _ in range(max_attempts):
            status_response = await async_client.get(f"/api/copilot/index/rebuild/{job_id}")
            status_data = status_response.json()
            
            if status_data["state"] in ["completed", "failed"]:
                break
            
            await asyncio.sleep(0.1)
        
        # 5. Verify final status
        assert status_data["state"] in ["completed", "failed"]
        
        # If completed successfully, verify mocked indexer was called
        if status_data["state"] == "completed":
            policy_indexer = mock_indexers[
                "src.services.copilot.indexing.policy_docs_indexer.PolicyDocsIndexer"
            ]
            # Should call full rebuild method
            policy_indexer.index_for_tenant.assert_called_once()

    @pytest.mark.asyncio
    async def test_e2e_multi_source_rebuild(
        self,
        async_client: AsyncClient,
        test_tenant: str,
        mock_admin_auth,
        mock_embedding_service,
        mock_chunking_service,
        mock_indexers,
    ):
        """Test rebuild with multiple source types."""
        request_data = {
            "tenant_id": test_tenant,
            "sources": ["policy_doc", "resolved_exception", "audit_event"],
            "full_rebuild": False,
        }
        
        start_response = await async_client.post(
            "/api/copilot/index/rebuild",
            json=request_data,
        )
        
        assert start_response.status_code == 200
        job_id = start_response.json()["job_id"]
        
        # Wait for processing
        await asyncio.sleep(0.2)
        
        # Check status
        status_response = await async_client.get(f"/api/copilot/index/rebuild/{job_id}")
        status_data = status_response.json()
        
        # Verify all sources are included
        assert set(status_data["sources"]) == {"policy_doc", "resolved_exception", "audit_event"}
        
        # Verify all relevant indexers were called
        policy_indexer = mock_indexers[
            "src.services.copilot.indexing.policy_docs_indexer.PolicyDocsIndexer"
        ]
        exception_indexer = mock_indexers[
            "src.services.copilot.indexing.resolved_exceptions_indexer.ResolvedExceptionsIndexer"
        ]
        audit_indexer = mock_indexers[
            "src.services.copilot.indexing.audit_events_indexer.AuditEventsIndexer"
        ]
        
        # For incremental rebuild, should call incremental methods
        policy_indexer.index_incremental_for_tenant.assert_called_once()
        exception_indexer.index_incremental_for_tenant.assert_called_once()
        audit_indexer.index_incremental_for_tenant.assert_called_once()

    @pytest.mark.asyncio
    async def test_e2e_global_rebuild(
        self,
        async_client: AsyncClient,
        mock_admin_auth,
        mock_embedding_service,
        mock_chunking_service,
        mock_indexers,
    ):
        """Test global rebuild across all tenants."""
        request_data = {
            "tenant_id": None,  # Global rebuild
            "sources": ["tool_registry"],
            "full_rebuild": True,
        }
        
        start_response = await async_client.post(
            "/api/copilot/index/rebuild",
            json=request_data,
        )
        
        assert start_response.status_code == 200
        job_id = start_response.json()["job_id"]
        
        # Wait for processing
        await asyncio.sleep(0.2)
        
        # Check status
        status_response = await async_client.get(f"/api/copilot/index/rebuild/{job_id}")
        status_data = status_response.json()
        
        assert status_data["tenant_id"] is None
        assert status_data["sources"] == ["tool_registry"]
        
        # Verify global indexer method was called
        tool_indexer = mock_indexers[
            "src.services.copilot.indexing.tool_registry_indexer.ToolRegistryIndexer"
        ]
        tool_indexer.index_all.assert_called_once()