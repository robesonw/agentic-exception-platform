"""
Tests for Streaming Ingestion Mode (P3-17).

Tests cover:
- Stub backend message handling
- Message normalization
- Integration with orchestrator/queue
- Configuration loading
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.intake import IntakeAgent
from src.ingestion.streaming import (
    KafkaIngestionBackend,
    StreamingIngestionService,
    StreamingMessage,
    StubIngestionBackend,
    create_streaming_backend,
    load_streaming_config,
)


class TestStreamingMessage:
    """Test suite for StreamingMessage."""

    def test_message_to_dict(self):
        """Test converting message to dictionary."""
        message = StreamingMessage(
            tenant_id="tenant_001",
            source_system="test_system",
            raw_payload={"error": "test"},
            exception_type="DataQualityFailure",
            severity="HIGH",
        )
        
        data = message.to_dict()
        assert data["tenantId"] == "tenant_001"
        assert data["sourceSystem"] == "test_system"
        assert data["rawPayload"] == {"error": "test"}
        assert data["exceptionType"] == "DataQualityFailure"
        assert data["severity"] == "HIGH"

    def test_message_from_dict(self):
        """Test creating message from dictionary."""
        data = {
            "tenantId": "tenant_001",
            "sourceSystem": "test_system",
            "rawPayload": {"error": "test"},
            "exceptionType": "DataQualityFailure",
            "severity": "HIGH",
        }
        
        message = StreamingMessage.from_dict(data)
        assert message.tenant_id == "tenant_001"
        assert message.source_system == "test_system"
        assert message.raw_payload == {"error": "test"}
        assert message.exception_type == "DataQualityFailure"
        assert message.severity == "HIGH"


class TestStubIngestionBackend:
    """Test suite for StubIngestionBackend."""

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping stub backend."""
        backend = StubIngestionBackend()
        
        await backend.start()
        assert backend._running is True
        
        await backend.stop()
        assert backend._running is False

    @pytest.mark.asyncio
    async def test_message_handler(self):
        """Test message handler is called."""
        backend = StubIngestionBackend()
        
        received_messages = []
        
        def handler(message: StreamingMessage):
            received_messages.append(message)
        
        backend.set_message_handler(handler)
        await backend.start()
        
        # Push a message
        message = StreamingMessage(
            tenant_id="tenant_001",
            source_system="test_system",
            raw_payload={"error": "test"},
        )
        await backend.push_message(message)
        
        # Wait for message to be processed
        await asyncio.sleep(0.1)
        
        await backend.stop()
        
        assert len(received_messages) == 1
        assert received_messages[0].tenant_id == "tenant_001"

    @pytest.mark.asyncio
    async def test_async_message_handler(self):
        """Test async message handler."""
        backend = StubIngestionBackend()
        
        received_messages = []
        
        async def handler(message: StreamingMessage):
            received_messages.append(message)
        
        backend.set_message_handler(handler)
        await backend.start()
        
        message = StreamingMessage(
            tenant_id="tenant_001",
            source_system="test_system",
            raw_payload={"error": "test"},
        )
        await backend.push_message(message)
        
        await asyncio.sleep(0.1)
        
        await backend.stop()
        
        assert len(received_messages) == 1


class TestKafkaIngestionBackend:
    """Test suite for KafkaIngestionBackend (stub)."""

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping Kafka backend (stub)."""
        backend = KafkaIngestionBackend(
            bootstrap_servers="localhost:9092",
            topic="exceptions",
            group_id="test-group",
        )
        
        await backend.start()
        assert backend._running is True
        
        await backend.stop()
        assert backend._running is False


class TestStreamingIngestionService:
    """Test suite for StreamingIngestionService."""

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping service."""
        backend = StubIngestionBackend()
        service = StreamingIngestionService(backend=backend)
        
        await service.start()
        assert service._running is True
        
        await service.stop()
        assert service._running is False

    @pytest.mark.asyncio
    async def test_message_processing_with_intake_agent(self):
        """Test message processing with IntakeAgent."""
        backend = StubIngestionBackend()
        
        # Mock intake agent
        intake_agent = MagicMock(spec=IntakeAgent)
        normalized_exception = MagicMock()
        normalized_exception.model_dump.return_value = {
            "exceptionId": "exc_001",
            "tenantId": "tenant_001",
        }
        decision = MagicMock()
        intake_agent.process = AsyncMock(return_value=(normalized_exception, decision))
        
        processed_exceptions = []
        
        async def orchestrator_callback(exception_dict: dict):
            processed_exceptions.append(exception_dict)
        
        service = StreamingIngestionService(
            backend=backend,
            intake_agent=intake_agent,
            orchestrator_callback=orchestrator_callback,
        )
        
        await service.start()
        
        # Push message
        message = StreamingMessage(
            tenant_id="tenant_001",
            source_system="test_system",
            raw_payload={"error": "test"},
        )
        await backend.push_message(message)
        
        # Wait for processing
        await asyncio.sleep(0.2)
        
        await service.stop()
        
        # Verify intake agent was called
        intake_agent.process.assert_called_once()
        
        # Verify orchestrator callback was called
        assert len(processed_exceptions) == 1
        assert processed_exceptions[0]["exceptionId"] == "exc_001"

    @pytest.mark.asyncio
    async def test_message_processing_without_intake_agent(self):
        """Test message processing without IntakeAgent."""
        backend = StubIngestionBackend()
        
        processed_exceptions = []
        
        async def orchestrator_callback(exception_dict: dict):
            processed_exceptions.append(exception_dict)
        
        service = StreamingIngestionService(
            backend=backend,
            orchestrator_callback=orchestrator_callback,
        )
        
        await service.start()
        
        message = StreamingMessage(
            tenant_id="tenant_001",
            source_system="test_system",
            raw_payload={"error": "test"},
        )
        await backend.push_message(message)
        
        await asyncio.sleep(0.2)
        
        await service.stop()
        
        # Verify callback was called with raw exception
        assert len(processed_exceptions) == 1
        assert processed_exceptions[0]["tenantId"] == "tenant_001"
        assert processed_exceptions[0]["rawPayload"] == {"error": "test"}

    @pytest.mark.asyncio
    async def test_message_processing_with_queue(self):
        """Test message processing with queue (no callback)."""
        backend = StubIngestionBackend()
        service = StreamingIngestionService(backend=backend)
        
        await service.start()
        
        message = StreamingMessage(
            tenant_id="tenant_001",
            source_system="test_system",
            raw_payload={"error": "test"},
        )
        await backend.push_message(message)
        
        await asyncio.sleep(0.2)
        
        # Check queue
        queue = service.get_processing_queue()
        assert queue is not None
        
        # Queue should have been processed (task_done called)
        # But we can't easily verify that without more complex setup
        # For now, just verify queue exists
        
        await service.stop()

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in message processing."""
        backend = StubIngestionBackend()
        
        # Mock intake agent that raises error
        intake_agent = MagicMock(spec=IntakeAgent)
        intake_agent.process = AsyncMock(side_effect=Exception("Normalization failed"))
        
        processed_exceptions = []
        
        async def orchestrator_callback(exception_dict: dict):
            processed_exceptions.append(exception_dict)
        
        service = StreamingIngestionService(
            backend=backend,
            intake_agent=intake_agent,
            orchestrator_callback=orchestrator_callback,
        )
        
        await service.start()
        
        message = StreamingMessage(
            tenant_id="tenant_001",
            source_system="test_system",
            raw_payload={"error": "test"},
        )
        await backend.push_message(message)
        
        await asyncio.sleep(0.2)
        
        await service.stop()
        
        # Should still process with raw exception (fallback)
        assert len(processed_exceptions) == 1
        assert processed_exceptions[0]["tenantId"] == "tenant_001"


class TestStreamingBackendFactory:
    """Test suite for backend factory."""

    def test_create_stub_backend(self):
        """Test creating stub backend."""
        backend = create_streaming_backend("stub")
        assert isinstance(backend, StubIngestionBackend)

    def test_create_kafka_backend(self):
        """Test creating Kafka backend."""
        backend = create_streaming_backend(
            "kafka",
            bootstrap_servers="localhost:9092",
            topic="exceptions",
            group_id="test-group",
        )
        assert isinstance(backend, KafkaIngestionBackend)
        assert backend.bootstrap_servers == "localhost:9092"
        assert backend.topic == "exceptions"
        assert backend.group_id == "test-group"

    def test_create_invalid_backend(self):
        """Test creating invalid backend type."""
        with pytest.raises(ValueError, match="Unknown streaming backend type"):
            create_streaming_backend("invalid")


class TestStreamingConfig:
    """Test suite for streaming configuration."""

    def test_load_default_config(self):
        """Test loading default configuration."""
        with patch.dict("os.environ", {}, clear=True):
            config = load_streaming_config()
            
            assert "enabled" in config
            assert "backend" in config
            assert "kafka" in config
            assert config["backend"] == "stub"
            assert config["enabled"] is False

    def test_load_config_from_env(self):
        """Test loading configuration from environment variables."""
        with patch.dict(
            "os.environ",
            {
                "STREAMING_ENABLED": "true",
                "STREAMING_BACKEND": "kafka",
                "KAFKA_BOOTSTRAP_SERVERS": "kafka:9092",
                "KAFKA_TOPIC": "custom-topic",
                "KAFKA_GROUP_ID": "custom-group",
            },
        ):
            config = load_streaming_config()
            
            assert config["enabled"] is True
            assert config["backend"] == "kafka"
            assert config["kafka"]["bootstrap_servers"] == "kafka:9092"
            assert config["kafka"]["topic"] == "custom-topic"
            assert config["kafka"]["group_id"] == "custom-group"

