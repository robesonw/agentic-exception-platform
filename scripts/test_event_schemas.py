"""
Quick test script to verify event schemas work correctly.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import datetime
from uuid import UUID

from src.domain.events.exception_events import (
    ActorType,
    EventType,
    ExceptionCreatedPayload,
    EventEnvelope,
    TriageCompletedPayload,
    validate_and_build_event,
)


def test_exception_created_payload():
    """Test ExceptionCreatedPayload."""
    print("Testing ExceptionCreatedPayload...")
    payload = ExceptionCreatedPayload(
        source_system="ERP",
        raw_payload={"error": "Invalid data"},
    )
    assert payload.source_system == "ERP"
    print("  [OK] Valid payload created")
    
    # Test extra fields rejected
    try:
        ExceptionCreatedPayload(
            source_system="ERP",
            raw_payload={},
            invalid_field="should fail",
        )
        print("  [FAILED] Should have rejected extra field")
        return False
    except Exception:
        print("  [OK] Extra fields rejected")
    
    return True


def test_event_envelope():
    """Test EventEnvelope."""
    print("\nTesting EventEnvelope...")
    envelope = EventEnvelope(
        tenant_id="tenant_001",
        exception_id="exc_001",
        event_type="ExceptionCreated",
        actor_type="system",
        payload={"source_system": "ERP", "raw_payload": {}},
    )
    assert envelope.tenant_id == "tenant_001"
    assert isinstance(envelope.event_id, UUID)
    print("  [OK] Valid envelope created")
    
    # Test invalid event_type
    try:
        EventEnvelope(
            tenant_id="tenant_001",
            exception_id="exc_001",
            event_type="InvalidEvent",
            actor_type="system",
            payload={},
        )
        print("  [FAILED] Should have rejected invalid event_type")
        return False
    except Exception:
        print("  [OK] Invalid event_type rejected")
    
    return True


def test_validate_and_build_event():
    """Test validate_and_build_event."""
    print("\nTesting validate_and_build_event...")
    
    # Valid event
    envelope = validate_and_build_event(
        event_type=EventType.EXCEPTION_CREATED,
        payload_dict={
            "source_system": "ERP",
            "raw_payload": {"error": "Invalid data"},
        },
        tenant_id="tenant_001",
        exception_id="exc_001",
        actor_type=ActorType.SYSTEM,
    )
    assert envelope.event_type == "ExceptionCreated"
    assert envelope.actor_type == "system"
    print("  [OK] Valid event built")
    
    # Invalid event type
    try:
        validate_and_build_event(
            event_type="UnknownEvent",
            payload_dict={},
            tenant_id="tenant_001",
            exception_id="exc_001",
            actor_type="system",
        )
        print("  [FAILED] Should have rejected unknown event_type")
        return False
    except ValueError:
        print("  [OK] Unknown event_type rejected")
    
    # Invalid payload
    try:
        validate_and_build_event(
            event_type=EventType.EXCEPTION_CREATED,
            payload_dict={"invalid": "field"},
            tenant_id="tenant_001",
            exception_id="exc_001",
            actor_type="system",
        )
        print("  [FAILED] Should have rejected invalid payload")
        return False
    except ValueError:
        print("  [OK] Invalid payload rejected")
    
    # TriageCompleted event
    envelope = validate_and_build_event(
        event_type=EventType.TRIAGE_COMPLETED,
        payload_dict={
            "exception_type": "DataQualityFailure",
            "severity": "HIGH",
            "confidence": 0.95,
        },
        tenant_id="tenant_001",
        exception_id="exc_001",
        actor_type="agent",
        actor_id="TriageAgent",
    )
    assert envelope.event_type == "TriageCompleted"
    assert envelope.actor_id == "TriageAgent"
    print("  [OK] TriageCompleted event built")
    
    return True


def main():
    """Run all tests."""
    print("=" * 70)
    print("Event Schema Validation Tests")
    print("=" * 70)
    
    results = []
    results.append(("ExceptionCreatedPayload", test_exception_created_payload()))
    results.append(("EventEnvelope", test_event_envelope()))
    results.append(("validate_and_build_event", test_validate_and_build_event()))
    
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    
    for name, result in results:
        status = "[OK]" if result else "[FAILED]"
        print(f"{status} {name}")
    
    all_ok = all(result for _, result in results)
    
    if all_ok:
        print("\n[SUCCESS] All tests passed!")
        return 0
    else:
        print("\n[FAILED] Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

