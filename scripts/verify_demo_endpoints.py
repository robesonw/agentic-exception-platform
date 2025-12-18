#!/usr/bin/env python3
"""
Verify key demo endpoints are working.
"""

import requests
import sys

BASE_URL = "http://localhost:8000"
HEADERS = {
    "X-API-KEY": "test_api_key_tenant_001",
    "X-Tenant-Id": "TENANT_FINANCE_001",
}

def test_endpoint(name, url, method="GET", data=None):
    """Test an endpoint and return success status."""
    try:
        if method == "GET":
            response = requests.get(url, headers=HEADERS, timeout=5)
        else:
            response = requests.post(url, headers=HEADERS, json=data, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            print(f"[OK] {name}: Status {response.status_code}")
            return True, result
        else:
            print(f"[FAIL] {name}: Status {response.status_code} - {response.text[:100]}")
            return False, None
    except Exception as e:
        print(f"[FAIL] {name}: Error - {str(e)[:100]}")
        return False, None

def main():
    print("=" * 60)
    print("DEMO ENDPOINT VERIFICATION")
    print("=" * 60)
    
    # Test health
    success, _ = test_endpoint("Health Check", f"{BASE_URL}/health")
    if not success:
        print("\n[ERROR] Backend is not running. Please start it first.")
        sys.exit(1)
    
    # Test database health
    success, _ = test_endpoint("Database Health", f"{BASE_URL}/health/db")
    
    # Test UI status endpoint
    success, data = test_endpoint(
        "UI Status (Exceptions List)",
        f"{BASE_URL}/ui/status/TENANT_FINANCE_001?limit=10"
    )
    if success and data:
        print(f"  - Total exceptions: {data.get('total', 0)}")
        print(f"  - Returned: {len(data.get('exceptions', []))}")
        if data.get('exceptions'):
            exc = data['exceptions'][0]
            print(f"  - Sample: {exc.get('exceptionId')} ({exc.get('severity')}, {exc.get('status')})")
    
    # Test exception detail
    if success and data.get('exceptions'):
        exc_id = data['exceptions'][0]['exceptionId']
        success2, _ = test_endpoint(
            "Exception Detail",
            f"{BASE_URL}/exceptions/TENANT_FINANCE_001/{exc_id}"
        )
    
    # Test playbook status
    if success and data.get('exceptions'):
        exc_id = data['exceptions'][0]['exceptionId']
        success3, _ = test_endpoint(
            "Playbook Status",
            f"{BASE_URL}/exceptions/TENANT_FINANCE_001/{exc_id}/playbook"
        )
    
    # Test tools list
    success4, tools_data = test_endpoint(
        "Tools List",
        f"{BASE_URL}/api/tools/TENANT_FINANCE_001"
    )
    if success4 and tools_data:
        print(f"  - Total tools: {len(tools_data.get('tools', []))}")
    
    print("\n" + "=" * 60)
    print("[OK] Endpoint verification complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()





