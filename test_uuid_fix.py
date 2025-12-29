"""
Test the UUID to string conversion fix without database dependencies.
"""
import uuid
from src.api.routes.router_copilot import CreateSessionResponse

# Test the response model with different input types
test_uuid = uuid.uuid4()
test_string = str(test_uuid)

print(f"Testing CreateSessionResponse with different session_id types:")
print(f"Original UUID: {test_uuid}")
print(f"String UUID: {test_string}")

try:
    # Test with string (should work)
    response1 = CreateSessionResponse(
        session_id=test_string,
        title="Test Session",
        created_at="1735057200"
    )
    print(f"✅ String session_id works: {response1.session_id}")
except Exception as e:
    print(f"❌ String session_id failed: {e}")

try:
    # Test with UUID object (should fail before our fix)
    response2 = CreateSessionResponse(
        session_id=test_uuid,
        title="Test Session", 
        created_at="1735057200"
    )
    print(f"❌ UUID session_id unexpectedly worked: {response2.session_id}")
except Exception as e:
    print(f"✅ UUID session_id correctly fails validation: {e}")

try:
    # Test with str() conversion of UUID (should work with our fix)
    response3 = CreateSessionResponse(
        session_id=str(test_uuid),
        title="Test Session",
        created_at="1735057200"  
    )
    print(f"✅ str(UUID) session_id works: {response3.session_id}")
    print(f"✅ Response JSON: {response3.model_dump()}")
except Exception as e:
    print(f"❌ str(UUID) session_id failed: {e}")