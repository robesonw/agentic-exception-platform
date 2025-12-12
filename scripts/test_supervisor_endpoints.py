"""
Test supervisor dashboard endpoints to verify they work with PostgreSQL.
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx


async def test_supervisor_overview():
    """Test GET /ui/supervisor/overview endpoint."""
    print("\n" + "=" * 70)
    print("1. Testing Supervisor Overview Endpoint")
    print("=" * 70)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"X-API-KEY": "test_api_key_tenant_finance"}
            url = "http://localhost:8000/ui/supervisor/overview?tenant_id=TENANT_FINANCE_001"
            
            print(f"[INFO] Calling: {url}")
            response = await client.get(url, headers=headers)
            
            print(f"[INFO] Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"[OK] API returned overview data")
                print(f"     - Escalations count: {data.get('escalations_count', 0)}")
                print(f"     - Pending approvals: {data.get('pending_approvals_count', 0)}")
                counts = data.get('counts', {})
                print(f"     - Counts by severity: {counts.get('by_severity', {})}")
                print(f"     - Counts by status: {counts.get('by_status', {})}")
                return True
            else:
                print(f"[FAILED] API returned error: {response.status_code}")
                print(f"     Response: {response.text}")
                return False
    except Exception as e:
        print(f"[FAILED] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_supervisor_escalations():
    """Test GET /ui/supervisor/escalations endpoint."""
    print("\n" + "=" * 70)
    print("2. Testing Supervisor Escalations Endpoint")
    print("=" * 70)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"X-API-KEY": "test_api_key_tenant_finance"}
            url = "http://localhost:8000/ui/supervisor/escalations?tenant_id=TENANT_FINANCE_001&limit=10"
            
            print(f"[INFO] Calling: {url}")
            response = await client.get(url, headers=headers)
            
            print(f"[INFO] Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"[OK] API returned escalations data")
                print(f"     - Total escalations: {data.get('total', 0)}")
                print(f"     - Escalations returned: {len(data.get('escalations', []))}")
                if data.get('escalations'):
                    esc = data['escalations'][0]
                    print(f"     - Sample: {esc.get('exception_id')} - {esc.get('escalation_reason')}")
                return True
            else:
                print(f"[FAILED] API returned error: {response.status_code}")
                print(f"     Response: {response.text}")
                return False
    except Exception as e:
        print(f"[FAILED] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_supervisor_policy_violations():
    """Test GET /ui/supervisor/policy-violations endpoint."""
    print("\n" + "=" * 70)
    print("3. Testing Supervisor Policy Violations Endpoint")
    print("=" * 70)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"X-API-KEY": "test_api_key_tenant_finance"}
            url = "http://localhost:8000/ui/supervisor/policy-violations?tenant_id=TENANT_FINANCE_001&limit=10"
            
            print(f"[INFO] Calling: {url}")
            response = await client.get(url, headers=headers)
            
            print(f"[INFO] Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"[OK] API returned policy violations data")
                print(f"     - Total violations: {data.get('total', 0)}")
                print(f"     - Violations returned: {len(data.get('violations', []))}")
                return True
            else:
                print(f"[FAILED] API returned error: {response.status_code}")
                print(f"     Response: {response.text}")
                return False
    except Exception as e:
        print(f"[FAILED] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_exception_evidence():
    """Test GET /ui/exceptions/{exception_id}/evidence endpoint."""
    print("\n" + "=" * 70)
    print("4. Testing Exception Evidence Endpoint")
    print("=" * 70)
    
    try:
        # Get an exception ID first
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"X-API-KEY": "test_api_key_tenant_finance"}
            list_url = "http://localhost:8000/ui/exceptions?tenant_id=TENANT_FINANCE_001&page_size=1"
            
            list_response = await client.get(list_url, headers=headers)
            if list_response.status_code != 200:
                print("[SKIP] Could not get exception ID for evidence test")
                return True
            
            items = list_response.json().get('items', [])
            if not items:
                print("[SKIP] No exceptions found for evidence test")
                return True
            
            exception_id = items[0].get('exception_id')
            if not exception_id:
                print("[SKIP] Could not extract exception ID")
                return True
            
            # Test evidence endpoint
            evidence_url = f"http://localhost:8000/ui/exceptions/{exception_id}/evidence?tenant_id=TENANT_FINANCE_001"
            print(f"[INFO] Calling: {evidence_url}")
            
            response = await client.get(evidence_url, headers=headers)
            
            print(f"[INFO] Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"[OK] API returned evidence data")
                print(f"     - RAG results: {len(data.get('rag_results', []))}")
                print(f"     - Tool outputs: {len(data.get('tool_outputs', []))}")
                print(f"     - Agent evidence: {len(data.get('agent_evidence', []))}")
                return True
            else:
                print(f"[FAILED] API returned error: {response.status_code}")
                print(f"     Response: {response.text}")
                return False
    except Exception as e:
        print(f"[FAILED] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_exception_audit():
    """Test GET /ui/exceptions/{exception_id}/audit endpoint."""
    print("\n" + "=" * 70)
    print("5. Testing Exception Audit Endpoint")
    print("=" * 70)
    
    try:
        # Get an exception ID first
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"X-API-KEY": "test_api_key_tenant_finance"}
            list_url = "http://localhost:8000/ui/exceptions?tenant_id=TENANT_FINANCE_001&page_size=1"
            
            list_response = await client.get(list_url, headers=headers)
            if list_response.status_code != 200:
                print("[SKIP] Could not get exception ID for audit test")
                return True
            
            items = list_response.json().get('items', [])
            if not items:
                print("[SKIP] No exceptions found for audit test")
                return True
            
            exception_id = items[0].get('exception_id')
            if not exception_id:
                print("[SKIP] Could not extract exception ID")
                return True
            
            # Test audit endpoint
            audit_url = f"http://localhost:8000/ui/exceptions/{exception_id}/audit?tenant_id=TENANT_FINANCE_001"
            print(f"[INFO] Calling: {audit_url}")
            
            response = await client.get(audit_url, headers=headers)
            
            print(f"[INFO] Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"[OK] API returned audit data")
                print(f"     - Event count: {data.get('count', 0)}")
                print(f"     - Events returned: {len(data.get('events', []))}")
                if data.get('events'):
                    event = data['events'][0]
                    print(f"     - Sample event: {event.get('event_type')} at {event.get('timestamp')}")
                return True
            else:
                print(f"[FAILED] API returned error: {response.status_code}")
                print(f"     Response: {response.text}")
                return False
    except Exception as e:
        print(f"[FAILED] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("=" * 70)
    print("Supervisor and Detail Page API Integration Test")
    print("=" * 70)
    
    results = []
    
    results.append(("Supervisor Overview", await test_supervisor_overview()))
    results.append(("Supervisor Escalations", await test_supervisor_escalations()))
    results.append(("Supervisor Policy Violations", await test_supervisor_policy_violations()))
    results.append(("Exception Evidence", await test_exception_evidence()))
    results.append(("Exception Audit", await test_exception_audit()))
    
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    
    for name, result in results:
        status = "[OK]" if result else "[FAILED]"
        print(f"{status} {name}")
    
    all_ok = all(result for _, result in results)
    
    if not all_ok:
        print("\n" + "=" * 70)
        print("Troubleshooting")
        print("=" * 70)
        print("1. Ensure API server is running with DATABASE_URL set")
        print("2. Check API server logs for errors")
        print("3. Verify data exists in database")
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

