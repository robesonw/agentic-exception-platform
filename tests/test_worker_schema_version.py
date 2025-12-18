"""
Unit tests for schema version validation in workers.

Tests that workers:
- Reject events with unsupported schema versions
- Allow future schema versions when ALLOW_FUTURE_SCHEMA=true
- Emit DeadLettered events for schema incompatibility
"""

import json
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from src.events.schema import CanonicalEvent
from src.workers.base import AgentWorker, SchemaVersionError, SUPPORTED_SCHEMA_VERSION


class MockWorker(AgentWorker):
    """Mock worker for testing."""
    
    async def process_event(self, event: CanonicalEvent) -> None:
        """Mock process_event implementation."""
        pass


class TestSchemaVersionValidation(unittest.TestCase):
    """Test schema version validation in workers."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.broker = MagicMock()
        self.worker = MockWorker(
            broker=self.broker,
            topics=["test_topic"],
            group_id="test_group",
        )
        
        # Create a valid event for testing
        self.valid_event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
            version=SUPPORTED_SCHEMA_VERSION,
        )
    
    def tearDown(self):
        """Clean up after tests."""
        # Reset environment variable
        if "ALLOW_FUTURE_SCHEMA" in os.environ:
            del os.environ["ALLOW_FUTURE_SCHEMA"]
    
    def test_valid_schema_version(self):
        """Test that events with supported schema version are accepted."""
        event_bytes = self.valid_event.model_dump_json().encode("utf-8")
        
        # Should not raise an exception
        deserialized_event = self.worker._deserialize_event(event_bytes)
        
        self.assertEqual(deserialized_event.event_id, self.valid_event.event_id)
        self.assertEqual(deserialized_event.version, SUPPORTED_SCHEMA_VERSION)
    
    def test_future_schema_version_rejected(self):
        """Test that events with future schema version are rejected."""
        # Create event with version > SUPPORTED_SCHEMA_VERSION
        future_version = SUPPORTED_SCHEMA_VERSION + 1
        event_dict = json.loads(self.valid_event.model_dump_json())
        event_dict["version"] = future_version
        event_bytes = json.dumps(event_dict).encode("utf-8")
        
        # Ensure ALLOW_FUTURE_SCHEMA is not set
        if "ALLOW_FUTURE_SCHEMA" in os.environ:
            del os.environ["ALLOW_FUTURE_SCHEMA"]
        
        # Should raise SchemaVersionError
        with self.assertRaises(SchemaVersionError) as context:
            self.worker._deserialize_event(event_bytes)
        
        self.assertIn("schema version", str(context.exception).lower())
        self.assertIn(str(future_version), str(context.exception))
    
    def test_future_schema_version_allowed_with_env_flag(self):
        """Test that future schema versions are allowed when ALLOW_FUTURE_SCHEMA=true."""
        # Create event with version > SUPPORTED_SCHEMA_VERSION
        future_version = SUPPORTED_SCHEMA_VERSION + 1
        event_dict = json.loads(self.valid_event.model_dump_json())
        event_dict["version"] = future_version
        event_bytes = json.dumps(event_dict).encode("utf-8")
        
        # Set ALLOW_FUTURE_SCHEMA=true
        os.environ["ALLOW_FUTURE_SCHEMA"] = "true"
        
        # Should not raise an exception (but may log warning)
        deserialized_event = self.worker._deserialize_event(event_bytes)
        
        self.assertEqual(deserialized_event.version, future_version)
    
    def test_future_schema_version_rejected_with_env_flag_false(self):
        """Test that future schema versions are rejected when ALLOW_FUTURE_SCHEMA=false."""
        # Create event with version > SUPPORTED_SCHEMA_VERSION
        future_version = SUPPORTED_SCHEMA_VERSION + 1
        event_dict = json.loads(self.valid_event.model_dump_json())
        event_dict["version"] = future_version
        event_bytes = json.dumps(event_dict).encode("utf-8")
        
        # Set ALLOW_FUTURE_SCHEMA=false
        os.environ["ALLOW_FUTURE_SCHEMA"] = "false"
        
        # Should raise SchemaVersionError
        with self.assertRaises(SchemaVersionError):
            self.worker._deserialize_event(event_bytes)
    
    def test_dead_lettered_event_emitted_on_schema_incompatibility(self):
        """Test that DeadLettered event is emitted when schema is incompatible."""
        # Create event with version > SUPPORTED_SCHEMA_VERSION
        future_version = SUPPORTED_SCHEMA_VERSION + 1
        event_dict = json.loads(self.valid_event.model_dump_json())
        event_dict["version"] = future_version
        event_bytes = json.dumps(event_dict).encode("utf-8")
        
        # Ensure ALLOW_FUTURE_SCHEMA is not set
        if "ALLOW_FUTURE_SCHEMA" in os.environ:
            del os.environ["ALLOW_FUTURE_SCHEMA"]
        
        # Mock broker.publish to capture calls
        publish_calls = []
        original_publish = self.broker.publish
        
        def mock_publish(topic, partition_key, value):
            publish_calls.append((topic, partition_key, value))
            original_publish(topic, partition_key, value)
        
        self.broker.publish = mock_publish
        
        # Should raise SchemaVersionError and emit DeadLettered event
        with self.assertRaises(SchemaVersionError):
            self.worker._deserialize_event(event_bytes)
        
        # Verify DeadLettered event was published
        self.assertEqual(len(publish_calls), 1)
        topic, partition_key, value_bytes = publish_calls[0]
        
        self.assertEqual(topic, "exceptions")
        self.assertEqual(partition_key, self.valid_event.tenant_id)
        
        # Parse the DeadLettered event
        dead_lettered_dict = json.loads(value_bytes.decode("utf-8"))
        self.assertEqual(dead_lettered_dict["event_type"], "DeadLettered")
        self.assertEqual(dead_lettered_dict["payload"]["original_event_id"], self.valid_event.event_id)
        self.assertIn("schema_incompatible", dead_lettered_dict["payload"]["failure_reason"])
        self.assertIn(str(future_version), dead_lettered_dict["payload"]["failure_reason"])
    
    def test_dead_lettered_event_includes_schema_metadata(self):
        """Test that DeadLettered event includes schema version metadata."""
        # Create event with version > SUPPORTED_SCHEMA_VERSION
        future_version = SUPPORTED_SCHEMA_VERSION + 1
        event_dict = json.loads(self.valid_event.model_dump_json())
        event_dict["version"] = future_version
        event_bytes = json.dumps(event_dict).encode("utf-8")
        
        # Ensure ALLOW_FUTURE_SCHEMA is not set
        if "ALLOW_FUTURE_SCHEMA" in os.environ:
            del os.environ["ALLOW_FUTURE_SCHEMA"]
        
        # Mock broker.publish to capture calls
        publish_calls = []
        original_publish = self.broker.publish
        
        def mock_publish(topic, partition_key, value):
            publish_calls.append((topic, partition_key, value))
            original_publish(topic, partition_key, value)
        
        self.broker.publish = mock_publish
        
        # Should raise SchemaVersionError and emit DeadLettered event
        with self.assertRaises(SchemaVersionError):
            self.worker._deserialize_event(event_bytes)
        
        # Verify DeadLettered event metadata includes schema info
        topic, partition_key, value_bytes = publish_calls[0]
        dead_lettered_dict = json.loads(value_bytes.decode("utf-8"))
        
        self.assertIn("metadata", dead_lettered_dict)
        metadata = dead_lettered_dict["metadata"]
        self.assertEqual(metadata["schema_version"], future_version)
        self.assertEqual(metadata["supported_version"], SUPPORTED_SCHEMA_VERSION)
    
    def test_version_defaults_to_one(self):
        """Test that events without version field default to version 1."""
        # Create event without version field
        event_dict = json.loads(self.valid_event.model_dump_json())
        del event_dict["version"]
        event_bytes = json.dumps(event_dict).encode("utf-8")
        
        # Should not raise an exception (defaults to version 1)
        deserialized_event = self.worker._deserialize_event(event_bytes)
        
        self.assertEqual(deserialized_event.version, 1)
    
    def test_schema_version_error_in_message_processing(self):
        """Test that schema version errors are handled in message processing."""
        # Create event with version > SUPPORTED_SCHEMA_VERSION
        future_version = SUPPORTED_SCHEMA_VERSION + 1
        event_dict = json.loads(self.valid_event.model_dump_json())
        event_dict["version"] = future_version
        event_bytes = json.dumps(event_dict).encode("utf-8")
        
        # Ensure ALLOW_FUTURE_SCHEMA is not set
        if "ALLOW_FUTURE_SCHEMA" in os.environ:
            del os.environ["ALLOW_FUTURE_SCHEMA"]
        
        # Mock broker.publish
        self.broker.publish = MagicMock()
        
        # Process message - should handle SchemaVersionError gracefully
        self.worker._process_message_sync("test_topic", None, event_bytes)
        
        # Verify error was recorded
        self.assertEqual(self.worker._errors_count, 1)
        self.assertIsNotNone(self.worker._last_error)
        self.assertIn("schema", self.worker._last_error.lower())
        
        # Verify DeadLettered event was published
        self.broker.publish.assert_called_once()


if __name__ == "__main__":
    unittest.main()

