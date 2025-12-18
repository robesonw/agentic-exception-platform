"""
Security tests for tenant isolation at message broker layer (P9-23).

Tests verify:
- Cross-tenant events are rejected
- Tenant validation in workers
- Missing tenant_id is rejected
- Invalid tenant_id is rejected
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4

from src.events.types import ExceptionIngested, ExceptionNormalized
from src.workers.base import AgentWorker
from src.workers.intake_worker import IntakeWorker
from src.workers.triage_worker import TriageWorker


class TestTenantIsolation:
    """Security tests for tenant isolation."""

    @pytest.fixture
    def mock_broker(self):
        """Create mock broker."""
        return Mock()

    @pytest.fixture
    def mock_event_publisher(self):
        """Create mock event publisher."""
        return Mock()

    @pytest.fixture
    def intake_worker(self, mock_broker, mock_event_publisher):
        """Create IntakeWorker instance."""
        from unittest.mock import AsyncMock
        
        mock_intake_agent = AsyncMock()
        mock_exception_repo = AsyncMock()
        
        worker = IntakeWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="intake-workers",
            intake_agent=mock_intake_agent,
            exception_repository=mock_exception_repo,
            event_publisher=mock_event_publisher,
        )
        return worker

    @pytest.fixture
    def tenant_scoped_worker(self, mock_broker):
        """Create a tenant-scoped worker for testing."""
        class TestWorker(AgentWorker):
            async def process_event(self, event):
                pass
        
        worker = TestWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="test-workers",
        )
        worker.set_expected_tenant("TENANT_001")
        return worker

    def test_cross_tenant_event_rejected(self, tenant_scoped_worker):
        """Test that cross-tenant events are rejected."""
        # Create event from different tenant
        event = ExceptionIngested.create(
            tenant_id="TENANT_002",  # Different from expected TENANT_001
            exception_id=str(uuid4()),
            raw_payload={"error": "Test"},
            source_system="TEST",
            ingestion_method="api",
        )
        
        # Validate tenant - should fail
        is_valid = tenant_scoped_worker._validate_tenant(event)
        
        assert not is_valid, "Cross-tenant event should be rejected"

    def test_same_tenant_event_accepted(self, tenant_scoped_worker):
        """Test that events from same tenant are accepted."""
        # Create event from same tenant
        event = ExceptionIngested.create(
            tenant_id="TENANT_001",  # Matches expected tenant
            exception_id=str(uuid4()),
            raw_payload={"error": "Test"},
            source_system="TEST",
            ingestion_method="api",
        )
        
        # Validate tenant - should pass
        is_valid = tenant_scoped_worker._validate_tenant(event)
        
        assert is_valid, "Same-tenant event should be accepted"

    def test_missing_tenant_id_rejected(self, tenant_scoped_worker):
        """Test that events with missing tenant_id are rejected."""
        # Create event without tenant_id (simulate malformed event)
        event = ExceptionIngested.create(
            tenant_id="",  # Empty tenant_id
            exception_id=str(uuid4()),
            raw_payload={"error": "Test"},
            source_system="TEST",
            ingestion_method="api",
        )
        
        # Validate tenant - should fail
        is_valid = tenant_scoped_worker._validate_tenant(event)
        
        assert not is_valid, "Event with missing tenant_id should be rejected"

    def test_non_tenant_scoped_worker_accepts_all_tenants(self, mock_broker):
        """Test that non-tenant-scoped workers accept events from any tenant."""
        class TestWorker(AgentWorker):
            async def process_event(self, event):
                pass
        
        worker = TestWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="test-workers",
        )
        # Worker is not tenant-scoped (no set_expected_tenant called)
        
        # Create events from different tenants
        event1 = ExceptionIngested.create(
            tenant_id="TENANT_001",
            exception_id=str(uuid4()),
            raw_payload={"error": "Test"},
            source_system="TEST",
            ingestion_method="api",
        )
        
        event2 = ExceptionIngested.create(
            tenant_id="TENANT_002",
            exception_id=str(uuid4()),
            raw_payload={"error": "Test"},
            source_system="TEST",
            ingestion_method="api",
        )
        
        # Both should be accepted (worker is not tenant-scoped)
        assert worker._validate_tenant(event1), "Non-tenant-scoped worker should accept any tenant"
        assert worker._validate_tenant(event2), "Non-tenant-scoped worker should accept any tenant"

    def test_tenant_validation_in_message_handler(self, tenant_scoped_worker):
        """Test that tenant validation is called in _handle_message."""
        # Create cross-tenant event
        event = ExceptionIngested.create(
            tenant_id="TENANT_002",  # Different tenant
            exception_id=str(uuid4()),
            raw_payload={"error": "Test"},
            source_system="TEST",
            ingestion_method="api",
        )
        
        # Serialize event
        event_dict = event.model_dump(by_alias=True)
        import json
        event_bytes = json.dumps(event_dict).encode("utf-8")
        
        # Mock _deserialize_event to return our event
        with patch.object(tenant_scoped_worker, "_deserialize_event", return_value=event):
            with patch.object(tenant_scoped_worker, "process_event") as mock_process:
                # Handle message
                tenant_scoped_worker._handle_message(
                    topic="exceptions",
                    key="test_key",
                    value=event_bytes,
                )
                
                # process_event should NOT be called (event rejected)
                mock_process.assert_not_called()

    def test_intake_worker_rejects_cross_tenant_event(self, intake_worker):
        """Test that IntakeWorker rejects cross-tenant events when tenant-scoped."""
        # Set worker to be tenant-scoped
        intake_worker.set_expected_tenant("TENANT_001")
        
        # Create event from different tenant
        event = ExceptionIngested.create(
            tenant_id="TENANT_002",  # Different tenant
            exception_id=str(uuid4()),
            raw_payload={"error": "Test"},
            source_system="TEST",
            ingestion_method="api",
        )
        
        # Validate tenant - should fail
        is_valid = intake_worker._validate_tenant(event)
        
        assert not is_valid, "IntakeWorker should reject cross-tenant events"

    def test_triage_worker_rejects_cross_tenant_event(self, mock_broker):
        """Test that TriageWorker rejects cross-tenant events when tenant-scoped."""
        from unittest.mock import AsyncMock
        
        mock_triage_agent = AsyncMock()
        mock_exception_repo = AsyncMock()
        mock_event_publisher = Mock()
        mock_domain_pack = Mock()
        mock_llm_client = Mock()
        
        worker = TriageWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="triage-workers",
            triage_agent=mock_triage_agent,
            exception_repository=mock_exception_repo,
            event_publisher=mock_event_publisher,
            domain_pack=mock_domain_pack,
            llm_client=mock_llm_client,
        )
        
        # Set worker to be tenant-scoped
        worker.set_expected_tenant("TENANT_001")
        
        # Create event from different tenant
        event = ExceptionNormalized.create(
            tenant_id="TENANT_002",  # Different tenant
            exception_id=str(uuid4()),
            normalized_exception={},
            normalization_rules=[],
        )
        
        # Validate tenant - should fail
        is_valid = worker._validate_tenant(event)
        
        assert not is_valid, "TriageWorker should reject cross-tenant events"

    def test_whitespace_tenant_id_handled(self, tenant_scoped_worker):
        """Test that tenant_id with whitespace is handled correctly."""
        # Create event with whitespace in tenant_id
        event = ExceptionIngested.create(
            tenant_id="  TENANT_001  ",  # Whitespace
            exception_id=str(uuid4()),
            raw_payload={"error": "Test"},
            source_system="TEST",
            ingestion_method="api",
        )
        
        # Validate tenant - should pass (whitespace is stripped)
        is_valid = tenant_scoped_worker._validate_tenant(event)
        
        assert is_valid, "Tenant_id with whitespace should be handled (stripped)"

    def test_none_tenant_id_rejected(self, tenant_scoped_worker):
        """Test that None tenant_id is rejected."""
        # Create event with None tenant_id (simulate malformed event)
        # This shouldn't happen with Pydantic validation, but test defensive code
        event = Mock()
        event.tenant_id = None
        event.event_id = str(uuid4())
        event.event_type = "ExceptionIngested"
        
        # Validate tenant - should fail
        is_valid = tenant_scoped_worker._validate_tenant(event)
        
        assert not is_valid, "Event with None tenant_id should be rejected"



