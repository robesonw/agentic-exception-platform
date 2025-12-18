"""
Unit tests for canonical event schema.
"""

import json
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from src.events.schema import CanonicalEvent


class TestCanonicalEvent:
    """Test CanonicalEvent base schema."""
    
    def test_create_event_with_factory_method(self):
        """Test creating event using factory method."""
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        
        assert event.event_type == "TestEvent"
        assert event.tenant_id == "tenant_001"
        assert event.payload == {"data": "test"}
        assert event.event_id is not None
        assert isinstance(event.timestamp, datetime)
        assert event.version == 1
        
    def test_create_event_with_all_fields(self):
        """Test creating event with all fields."""
        event_id = "550e8400-e29b-41d4-a716-446655440000"
        timestamp = datetime.now(timezone.utc)
        
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
            exception_id="exc_001",
            correlation_id="corr_123",
            metadata={"source": "test"},
            version=2,
            event_id=event_id,
            timestamp=timestamp,
        )
        
        assert event.event_id == event_id
        assert event.event_type == "TestEvent"
        assert event.tenant_id == "tenant_001"
        assert event.exception_id == "exc_001"
        assert event.correlation_id == "corr_123"
        assert event.metadata == {"source": "test"}
        assert event.version == 2
        assert event.timestamp == timestamp
        
    def test_event_immutability(self):
        """Test that events are immutable (frozen)."""
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        
        # Attempting to modify should raise an error
        with pytest.raises(ValidationError):
            event.event_type = "ModifiedEvent"
            
    def test_event_validation_required_fields(self):
        """Test validation of required fields."""
        # Missing event_type
        with pytest.raises(ValidationError):
            CanonicalEvent(
                event_id="test-id",
                tenant_id="tenant_001",
                timestamp=datetime.now(timezone.utc),
                payload={"data": "test"},
            )
            
        # Missing tenant_id
        with pytest.raises(ValidationError):
            CanonicalEvent(
                event_id="test-id",
                event_type="TestEvent",
                timestamp=datetime.now(timezone.utc),
                payload={"data": "test"},
            )
            
        # Missing payload
        with pytest.raises(ValidationError):
            CanonicalEvent(
                event_id="test-id",
                event_type="TestEvent",
                tenant_id="tenant_001",
                timestamp=datetime.now(timezone.utc),
            )
            
    def test_event_validation_version_minimum(self):
        """Test version must be >= 1."""
        with pytest.raises(ValidationError):
            CanonicalEvent.create(
                event_type="TestEvent",
                tenant_id="tenant_001",
                payload={"data": "test"},
                version=0,
            )
            
    def test_event_rejects_extra_fields(self):
        """Test that extra fields are rejected."""
        with pytest.raises(ValidationError):
            CanonicalEvent(
                event_id="test-id",
                event_type="TestEvent",
                tenant_id="tenant_001",
                timestamp=datetime.now(timezone.utc),
                payload={"data": "test"},
                extra_field="not allowed",
            )
            
    def test_event_to_dict(self):
        """Test converting event to dictionary."""
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
            exception_id="exc_001",
        )
        
        event_dict = event.to_dict()
        
        assert isinstance(event_dict, dict)
        assert event_dict["event_type"] == "TestEvent"
        assert event_dict["tenant_id"] == "tenant_001"
        assert event_dict["exception_id"] == "exc_001"
        assert event_dict["payload"] == {"data": "test"}
        assert "timestamp" in event_dict
        
    def test_event_to_json(self):
        """Test converting event to JSON string."""
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        
        json_str = event.to_json()
        
        assert isinstance(json_str, str)
        event_dict = json.loads(json_str)
        assert event_dict["event_type"] == "TestEvent"
        assert event_dict["tenant_id"] == "tenant_001"
        
    def test_event_json_serialization_datetime(self):
        """Test datetime serialization in JSON."""
        timestamp = datetime.now(timezone.utc)
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
            timestamp=timestamp,
        )
        
        json_str = event.to_json()
        event_dict = json.loads(json_str)
        
        # Timestamp should be ISO format string
        assert isinstance(event_dict["timestamp"], str)
        # Can parse it back
        parsed_timestamp = datetime.fromisoformat(event_dict["timestamp"].replace("Z", "+00:00"))
        assert parsed_timestamp == timestamp
        
    def test_event_default_metadata(self):
        """Test default metadata is empty dict."""
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        
        assert event.metadata == {}
        
    def test_event_optional_fields(self):
        """Test optional fields can be None."""
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
            exception_id=None,
            correlation_id=None,
        )
        
        assert event.exception_id is None
        assert event.correlation_id is None
        
    def test_event_string_validation(self):
        """Test string field validation (min_length)."""
        # Empty event_type
        with pytest.raises(ValidationError):
            CanonicalEvent.create(
                event_type="",
                tenant_id="tenant_001",
                payload={"data": "test"},
            )
            
        # Empty tenant_id
        with pytest.raises(ValidationError):
            CanonicalEvent.create(
                event_type="TestEvent",
                tenant_id="",
                payload={"data": "test"},
            )
            
    def test_event_serialization_roundtrip(self):
        """Test event can be serialized and deserialized."""
        original_event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test", "nested": {"key": "value"}},
            exception_id="exc_001",
            correlation_id="corr_123",
            metadata={"source": "test"},
            version=2,
        )
        
        # Serialize to JSON
        json_str = original_event.to_json()
        assert isinstance(json_str, str)
        
        # Deserialize from JSON
        event_dict = json.loads(json_str)
        deserialized_event = CanonicalEvent(**event_dict)
        
        # Verify all fields match
        assert deserialized_event.event_type == original_event.event_type
        assert deserialized_event.tenant_id == original_event.tenant_id
        assert deserialized_event.exception_id == original_event.exception_id
        assert deserialized_event.correlation_id == original_event.correlation_id
        assert deserialized_event.payload == original_event.payload
        assert deserialized_event.metadata == original_event.metadata
        assert deserialized_event.version == original_event.version
        
    def test_event_dict_serialization(self):
        """Test event can be converted to dict and back."""
        original_event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        
        # Convert to dict
        event_dict = original_event.to_dict()
        
        # Create new event from dict
        new_event = CanonicalEvent(**event_dict)
        
        # Verify fields match
        assert new_event.event_type == original_event.event_type
        assert new_event.tenant_id == original_event.tenant_id
        assert new_event.payload == original_event.payload
        assert new_event.event_id == original_event.event_id

