"""
Synthetic Data Generators for Adversarial Test Suites (P3-23).

Generates edge-case exception data for finance and healthcare domains
that conform to Domain Pack schemas while testing regulatory compliance.
"""

import random
from datetime import datetime, timedelta, timezone
from typing import Any

from src.models.exception_record import ExceptionRecord, Severity


def generate_finance_exception_edge_cases() -> list[dict[str, Any]]:
    """
    Generate finance domain exception edge cases for adversarial testing.
    
    Generates exceptions that:
    - Test FINRA regulatory compliance
    - Include suspicious patterns (round numbers, high values)
    - Test position breaks, cash breaks, settlement failures
    - Include regulatory reporting edge cases
    
    Returns:
        List of exception dictionaries conforming to finance Domain Pack schema
    """
    exceptions: list[dict[str, Any]] = []
    base_time = datetime.now(timezone.utc)
    
    # Position break with suspicious round number
    exceptions.append({
        "exceptionId": f"FIN_POS_BREAK_{random.randint(1000, 9999)}",
        "tenantId": "TENANT_FINANCE",
        "sourceSystem": "TradingSystem",
        "exceptionType": "POSITION_BREAK",
        "severity": "CRITICAL",
        "timestamp": base_time.isoformat(),
        "rawPayload": {
            "accountId": f"ACC-{random.randint(100, 999)}",
            "cusip": "123456789",
            "expectedQuantity": 10000,
            "actualQuantity": 5000,
            "discrepancy": 5000,
            "discrepancyValue": 500000.00,  # Suspicious round number
            "asOfDate": (base_time - timedelta(days=1)).isoformat(),
            "occurrenceCount": 3,  # Multiple occurrences
        },
        "normalizedContext": {
            "domain": "CapitalMarketsTrading",
            "entity": "Position",
        },
    })
    
    # Cash break with exact round number
    exceptions.append({
        "exceptionId": f"FIN_CASH_BREAK_{random.randint(1000, 9999)}",
        "tenantId": "TENANT_FINANCE",
        "sourceSystem": "CashManagement",
        "exceptionType": "CASH_BREAK",
        "severity": "HIGH",
        "timestamp": base_time.isoformat(),
        "rawPayload": {
            "accountId": f"ACC-{random.randint(100, 999)}",
            "currency": "USD",
            "expectedAmount": 1000000.00,  # Exact round number
            "actualAmount": 0.00,
            "discrepancy": 1000000.00,
            "valueDate": base_time.isoformat(),
            "pattern": "round_number_multiple_occurrences",
        },
        "normalizedContext": {
            "domain": "CapitalMarketsTrading",
            "entity": "CashMovement",
        },
    })
    
    # Settlement failure for high-value trade
    exceptions.append({
        "exceptionId": f"FIN_SETTLE_FAIL_{random.randint(1000, 9999)}",
        "tenantId": "TENANT_FINANCE",
        "sourceSystem": "SettlementSystem",
        "exceptionType": "SETTLEMENT_FAIL",
        "severity": "HIGH",
        "timestamp": base_time.isoformat(),
        "rawPayload": {
            "orderId": f"ORD-{random.randint(10000, 99999)}",
            "tradeValue": 10000000.00,  # High value: $10M
            "intendedSettleDate": (base_time - timedelta(days=3)).isoformat(),
            "actualSettleDate": None,
            "failReason": "Counterparty rejection",
            "daysPastSettle": 3,
            "counterparty": "CPTY-UNKNOWN",
        },
        "normalizedContext": {
            "domain": "CapitalMarketsTrading",
            "entity": "Settlement",
        },
    })
    
    # Regulatory report rejection
    exceptions.append({
        "exceptionId": f"FIN_REG_REJECT_{random.randint(1000, 9999)}",
        "tenantId": "TENANT_FINANCE",
        "sourceSystem": "RegReporting",
        "exceptionType": "REG_REPORT_REJECTED",
        "severity": "HIGH",
        "timestamp": base_time.isoformat(),
        "rawPayload": {
            "reportId": f"REG-{random.randint(10000, 99999)}",
            "regType": "TRADE_REPORT",
            "tradeId": f"TRD-{random.randint(10000, 99999)}",
            "rejectReason": "Missing counterparty information",
            "submittedAt": (base_time - timedelta(hours=2)).isoformat(),
            "regulatoryDeadline": (base_time + timedelta(hours=1)).isoformat(),
            "mandatory": True,
        },
        "normalizedContext": {
            "domain": "CapitalMarketsTrading",
            "entity": "RegReport",
        },
    })
    
    # Trade detail mismatch with price discrepancy
    exceptions.append({
        "exceptionId": f"FIN_TRADE_MISMATCH_{random.randint(1000, 9999)}",
        "tenantId": "TENANT_FINANCE",
        "sourceSystem": "TradingSystem",
        "exceptionType": "MISMATCHED_TRADE_DETAILS",
        "severity": "MEDIUM",
        "timestamp": base_time.isoformat(),
        "rawPayload": {
            "orderId": f"ORD-{random.randint(10000, 99999)}",
            "execId": f"EXEC-{random.randint(10000, 99999)}",
            "orderPrice": 100.00,
            "executionPrice": 100.50,  # Price discrepancy
            "orderQuantity": 100,
            "executionQuantity": 1000,  # Quantity discrepancy
            "orderDate": (base_time - timedelta(days=1)).isoformat(),
            "executionDate": base_time.isoformat(),
        },
        "normalizedContext": {
            "domain": "CapitalMarketsTrading",
            "entity": "TradeOrder",
        },
    })
    
    return exceptions


def generate_healthcare_exception_edge_cases() -> list[dict[str, Any]]:
    """
    Generate healthcare domain exception edge cases for adversarial testing.
    
    Generates exceptions that:
    - Test HIPAA compliance (PHI handling)
    - Include patient safety edge cases
    - Test medication safety scenarios
    - Include provider credentialing edge cases
    - Test authorization and eligibility edge cases
    
    Returns:
        List of exception dictionaries conforming to healthcare Domain Pack schema
    """
    exceptions: list[dict[str, Any]] = []
    base_time = datetime.now(timezone.utc)
    
    # Duplicate therapy with high-risk combination
    exceptions.append({
        "exceptionId": f"HC_MED_DUP_{random.randint(1000, 9999)}",
        "tenantId": "TENANT_HEALTHCARE",
        "sourceSystem": "PharmacySystem",
        "exceptionType": "PHARMACY_DUPLICATE_THERAPY",
        "severity": "CRITICAL",
        "timestamp": base_time.isoformat(),
        "rawPayload": {
            "patientId": f"P{random.randint(10000, 99999)}",
            "orderId": f"ORD-{random.randint(10000, 99999)}",
            "medication1": {
                "ndc": "12345-678-90",
                "name": "Warfarin",
                "dose": "5mg",
                "frequency": "daily",
            },
            "medication2": {
                "ndc": "98765-432-10",
                "name": "Aspirin",
                "dose": "81mg",
                "frequency": "daily",
            },
            "riskLevel": "HIGH",
            "interactionType": "bleeding_risk",
            "overlapDays": 7,
        },
        "normalizedContext": {
            "domain": "HealthcareClaimsAndCareOps",
            "entity": "MedicationOrder",
        },
    })
    
    # Claim missing authorization
    exceptions.append({
        "exceptionId": f"HC_CLAIM_NO_AUTH_{random.randint(1000, 9999)}",
        "tenantId": "TENANT_HEALTHCARE",
        "sourceSystem": "ClaimsSystem",
        "exceptionType": "CLAIM_MISSING_AUTH",
        "severity": "HIGH",
        "timestamp": base_time.isoformat(),
        "rawPayload": {
            "claimId": f"CLM-{random.randint(10000, 99999)}",
            "patientId": f"P{random.randint(10000, 99999)}",
            "procedureCode": "99213",
            "procedureDescription": "Office visit",
            "serviceDate": (base_time - timedelta(days=5)).isoformat(),
            "authRequired": True,
            "authId": None,
            "providerId": f"PRV-{random.randint(100, 999)}",
        },
        "normalizedContext": {
            "domain": "HealthcareClaimsAndCareOps",
            "entity": "Claim",
        },
    })
    
    # Provider credential expired
    exceptions.append({
        "exceptionId": f"HC_PROV_EXP_{random.randint(1000, 9999)}",
        "tenantId": "TENANT_HEALTHCARE",
        "sourceSystem": "CredentialingSystem",
        "exceptionType": "PROVIDER_CREDENTIAL_EXPIRED",
        "severity": "HIGH",
        "timestamp": base_time.isoformat(),
        "rawPayload": {
            "providerId": f"PRV-{random.randint(100, 999)}",
            "npi": f"{random.randint(1000000000, 9999999999)}",
            "credentialStatus": "EXPIRED",
            "credentialExpiryDate": (base_time - timedelta(days=180)).isoformat(),  # 6 months expired
            "serviceDate": base_time.isoformat(),
            "facilityId": f"FAC-{random.randint(10, 99)}",
        },
        "normalizedContext": {
            "domain": "HealthcareClaimsAndCareOps",
            "entity": "Provider",
        },
    })
    
    # Patient demographic conflict (with PHI)
    exceptions.append({
        "exceptionId": f"HC_DEMO_CONFLICT_{random.randint(1000, 9999)}",
        "tenantId": "TENANT_HEALTHCARE",
        "sourceSystem": "PatientMaster",
        "exceptionType": "PATIENT_DEMOGRAPHIC_CONFLICT",
        "severity": "LOW",
        "timestamp": base_time.isoformat(),
        "rawPayload": {
            "patientId": f"P{random.randint(10000, 99999)}",
            "systemA": {
                "dob": "1980-01-15",
                "gender": "M",
                "insuranceId": f"INS-{random.randint(10000, 99999)}",
            },
            "systemB": {
                "dob": "1980-01-16",  # DOB mismatch
                "gender": "F",  # Gender mismatch
                "insuranceId": f"INS-{random.randint(10000, 99999)}",  # Different insurance
            },
            "affectsBilling": True,
        },
        "normalizedContext": {
            "domain": "HealthcareClaimsAndCareOps",
            "entity": "Patient",
        },
    })
    
    # Eligibility coverage lapse
    exceptions.append({
        "exceptionId": f"HC_ELIG_LAPSE_{random.randint(1000, 9999)}",
        "tenantId": "TENANT_HEALTHCARE",
        "sourceSystem": "EligibilitySystem",
        "exceptionType": "ELIGIBILITY_COVERAGE_LAPSE",
        "severity": "HIGH",
        "timestamp": base_time.isoformat(),
        "rawPayload": {
            "patientId": f"P{random.randint(10000, 99999)}",
            "insuranceId": f"INS-{random.randint(10000, 99999)}",
            "coverageStart": (base_time - timedelta(days=365)).isoformat(),
            "coverageEnd": (base_time - timedelta(days=60)).isoformat(),  # Lapsed 2 months ago
            "serviceDate": base_time.isoformat(),
            "lapseReason": "Non-payment",
        },
        "normalizedContext": {
            "domain": "HealthcareClaimsAndCareOps",
            "entity": "Patient",
        },
    })
    
    # Claim code mismatch
    exceptions.append({
        "exceptionId": f"HC_CODE_MISMATCH_{random.randint(1000, 9999)}",
        "tenantId": "TENANT_HEALTHCARE",
        "sourceSystem": "ClaimsSystem",
        "exceptionType": "CLAIM_CODE_MISMATCH",
        "severity": "MEDIUM",
        "timestamp": base_time.isoformat(),
        "rawPayload": {
            "claimId": f"CLM-{random.randint(10000, 99999)}",
            "patientId": f"P{random.randint(10000, 99999)}",
            "procedureCode": "99213",
            "diagnosisCode": "Z00.00",  # Routine exam code
            "procedureDescription": "Surgical procedure",  # Mismatch
            "eligibilityCheck": "FAILED",
        },
        "normalizedContext": {
            "domain": "HealthcareClaimsAndCareOps",
            "entity": "Claim",
        },
    })
    
    return exceptions


def generate_exception_from_dict(exception_dict: dict[str, Any]) -> ExceptionRecord:
    """
    Convert exception dictionary to ExceptionRecord.
    
    Args:
        exception_dict: Exception dictionary from generators
        
    Returns:
        ExceptionRecord instance
    """
    # Parse severity
    severity_str = exception_dict.get("severity", "MEDIUM")
    try:
        severity = Severity(severity_str)
    except ValueError:
        severity = Severity.MEDIUM
    
    # Parse timestamp
    timestamp_str = exception_dict.get("timestamp")
    if isinstance(timestamp_str, str):
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    else:
        timestamp = datetime.now(timezone.utc)
    
    return ExceptionRecord(
        exception_id=exception_dict.get("exceptionId", "unknown"),
        tenant_id=exception_dict.get("tenantId", "unknown"),
        exception_type=exception_dict.get("exceptionType"),
        severity=severity,
        resolution_status="OPEN",
        source_system=exception_dict.get("sourceSystem", "unknown"),
        timestamp=timestamp,
        raw_payload=exception_dict.get("rawPayload", {}),
        normalized_context=exception_dict.get("normalizedContext", {}),
    )

