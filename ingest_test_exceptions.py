"""
Script to ingest test exceptions for the UI.

This will populate the exception store with sample data so you can see
exceptions in the UI.

Usage:
    python ingest_test_exceptions.py

Make sure your backend server is running first!
"""

import requests
import json
from datetime import datetime, timezone

# Configuration - adjust these to match your setup
API_BASE_URL = "http://localhost:8000"  # Change if your backend runs on different port
TENANT_ID = "TENANT_001"  # Change to match your tenant
API_KEY = "test_api_key_tenant_001"  # Change to match your API key

# Sample exceptions to ingest
SAMPLE_EXCEPTIONS = [
    {
        "sourceSystem": "ERP",
        "exceptionType": "SETTLEMENT_FAIL",
        "rawPayload": {
            "orderId": "ORD-001",
            "intendedSettleDate": "2024-01-15",
            "failReason": "SSI mismatch",
            "amount": 100000.00,
            "currency": "USD"
        }
    },
    {
        "sourceSystem": "TradingSystem",
        "exceptionType": "POSITION_BREAK",
        "rawPayload": {
            "accountId": "ACC-123",
            "cusip": "CUSIP-456",
            "expectedPosition": 1000,
            "actualPosition": 950,
            "difference": 50
        }
    },
    {
        "sourceSystem": "ClearingSystem",
        "exceptionType": "CASH_BREAK",
        "rawPayload": {
            "accountId": "ACC-123",
            "currency": "USD",
            "expectedCash": 50000.00,
            "actualCash": 49500.00,
            "difference": 500.00
        }
    },
    {
        "sourceSystem": "SettlementSystem",
        "exceptionType": "SETTLEMENT_FAIL",
        "rawPayload": {
            "orderId": "ORD-002",
            "intendedSettleDate": "2024-01-16",
            "failReason": "Insufficient funds",
            "amount": 50000.00,
            "currency": "EUR"
        }
    },
    {
        "sourceSystem": "ERP",
        "exceptionType": "DATA_QUALITY_FAIL",
        "rawPayload": {
            "recordId": "REC-001",
            "field": "customerName",
            "issue": "Missing required field",
            "severity": "HIGH"
        }
    }
]


def ingest_exceptions():
    """Ingest sample exceptions."""
    url = f"{API_BASE_URL}/exceptions/{TENANT_ID}"
    headers = {
        "X-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }
    
    # Ingest as batch
    payload = {
        "exceptions": SAMPLE_EXCEPTIONS
    }
    
    print(f"Ingesting {len(SAMPLE_EXCEPTIONS)} exceptions to tenant {TENANT_ID}...")
    print(f"API URL: {url}")
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ Successfully ingested {data['count']} exceptions!")
            print(f"Exception IDs: {data['exceptionIds']}")
            print(f"\nYou should now see these exceptions in the UI at /exceptions")
        else:
            print(f"\n✗ Error: {response.status_code}")
            print(f"Response: {response.text}")
            if response.status_code == 403:
                print("\nNote: Make sure your API key is registered and matches the tenant ID.")
            elif response.status_code == 401:
                print("\nNote: Make sure you're providing a valid API key in the X-API-KEY header.")
    except requests.exceptions.ConnectionError:
        print(f"\n✗ Error: Could not connect to {API_BASE_URL}")
        print("Make sure your backend server is running!")
    except Exception as e:
        print(f"\n✗ Error: {e}")


if __name__ == "__main__":
    ingest_exceptions()

