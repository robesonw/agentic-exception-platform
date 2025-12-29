"""
Verify that the EvidenceDebugResponse model fix is working correctly.
"""
from src.api.routes.router_copilot import EvidenceDebugResponse
from src.services.copilot.copilot_service import CopilotService
import asyncio

async def test_evidence_debug_response():
    """Test that the evidence debug response includes all required fields."""
    
    print("🔍 Testing EvidenceDebugResponse Model Fix...")
    
    # Create a minimal service instance for testing
    service = CopilotService(
        session_repository=None,  # Not needed for this test
        intent_router=None,
        retrieval_service=None,
        similar_exceptions_finder=None,
        playbook_recommender=None,
        response_generator=None,
        safety_service=None
    )
    
    # Test the method that was failing
    try:
        print(f"\n📋 Testing get_evidence_debug_info method...")
        result = await service.get_evidence_debug_info("req_test", "TEST_TENANT")
        
        print(f"✅ Method returned result:")
        print(f"  - request_id: {result.get('request_id')}")
        print(f"  - tenant_id: {result.get('tenant_id')}")
        print(f"  - outcome_summary: {result.get('outcome_summary')}")
        print(f"  - closed_at: {result.get('closed_at')}")
        print(f"  - link_url: {result.get('link_url')}")
        print(f"  - has retrieval_debug: {'retrieval_debug' in result}")
        print(f"  - has intent_debug: {'intent_debug' in result}")
        
        # Test Pydantic model validation
        print(f"\n🔧 Testing Pydantic model validation...")
        model_instance = EvidenceDebugResponse(**result)
        print(f"✅ Pydantic validation successful!")
        print(f"  - Model outcome_summary: {model_instance.outcome_summary}")
        print(f"  - Model closed_at: {model_instance.closed_at}")
        print(f"  - Model link_url: {model_instance.link_url}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_model_requirements():
    """Test the EvidenceDebugResponse model requirements."""
    
    print(f"\n🧪 Testing EvidenceDebugResponse model requirements...")
    
    try:
        # Test with all required fields
        test_data = {
            "request_id": "req_test",
            "tenant_id": "TEST_TENANT",
            "retrieval_debug": {},
            "intent_debug": {},
            "processing_timeline": [],
            "outcome_summary": "Test summary",
            "closed_at": None,
            "link_url": None
        }
        
        model = EvidenceDebugResponse(**test_data)
        print(f"✅ Model validation with all fields: SUCCESS")
        
        # Test without outcome_summary (should fail)
        try:
            test_data_missing = test_data.copy()
            del test_data_missing["outcome_summary"]
            model_fail = EvidenceDebugResponse(**test_data_missing)
            print(f"❌ Expected validation failure but model passed!")
            return False
        except Exception as e:
            print(f"✅ Expected validation failure when missing outcome_summary: {e}")
            
        return True
        
    except Exception as e:
        print(f"❌ Model test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 VERIFYING EVIDENCEDEBUGRESPONSE FIX")
    print("="*50)
    
    # Test 1: Model requirements
    model_success = test_model_requirements()
    
    # Test 2: Service method 
    service_success = asyncio.run(test_evidence_debug_response())
    
    print(f"\n📊 VERIFICATION RESULTS:")
    print(f"  Model requirements: {'✅ PASS' if model_success else '❌ FAIL'}")
    print(f"  Service method: {'✅ PASS' if service_success else '❌ FAIL'}")
    
    if model_success and service_success:
        print(f"\n🎉 ALL VERIFICATIONS SUCCESSFUL!")
        print(f"✅ The get_evidence_debug_info method now includes all required fields")
        print(f"✅ The EvidenceDebugResponse model validation works correctly")
        print(f"✅ The 500 error has been fixed!")
    else:
        print(f"\n💥 Some verifications failed!")