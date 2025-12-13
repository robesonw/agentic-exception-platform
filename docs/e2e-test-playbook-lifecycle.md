# End-to-End Test: Playbook Lifecycle (P7-23)

This document describes the end-to-end test for the complete playbook lifecycle, including how to run it.

## Overview

The E2E test (`tests/test_e2e_playbook_lifecycle.py`) verifies the complete playbook lifecycle from exception creation through playbook completion:

1. **Create exception** via API
2. **Triage suggests playbook** (via pipeline execution)
3. **Policy assigns playbook** (via playbook matching service)
4. **UI shows playbook panel** (verified via GET playbook status API)
5. **User completes steps via UI** (simulated via POST step completion API)
6. **Playbook completes** (all steps finished)
7. **Events timeline includes playbook lifecycle events** (PlaybookStarted, PlaybookStepCompleted × 3, PlaybookCompleted)

## Test Architecture

The test uses:
- **Deterministic seeded test data**: A fixed playbook (`PaymentFailurePlaybook`) with 3 steps that always matches exceptions with `domain=Finance, type=PaymentFailure, severity=high`
- **Local DB fixtures**: In-memory SQLite database created fresh for each test run
- **Real API endpoints**: Uses FastAPI TestClient to call actual API routes
- **Database mocking**: Mocks the DB session context to use test database

## Prerequisites

1. Python 3.11+ with virtual environment activated
2. All dependencies installed (`pip install -e .`)
3. Domain pack and tenant policy files (for pipeline execution):
   - `domainpacks/finance.sample.json`
   - `tenantpacks/tenant_finance.sample.json`

These files are used by the test fixtures but are only required if you want to run the full pipeline. The test can run without them if the pipeline execution is skipped.

## How to Run

### Basic Run

```bash
# Run the E2E test
pytest tests/test_e2e_playbook_lifecycle.py -v
```

### Run with E2E Marker

```bash
# Run only E2E tests (if marker is configured)
pytest tests/test_e2e_playbook_lifecycle.py -v -m e2e
```

### Run with Coverage

```bash
# Run with code coverage reporting
pytest tests/test_e2e_playbook_lifecycle.py -v --cov=src --cov-report=term-missing
```

### Run with Detailed Output

```bash
# Run with verbose output and full traceback
pytest tests/test_e2e_playbook_lifecycle.py -v -s --tb=long
```

### Run in Headless Mode

```bash
# Run without printing to stdout (useful for CI)
pytest tests/test_e2e_playbook_lifecycle.py -v --tb=short
```

## Test Flow

### Step 1: Create Exception
- POST `/exceptions/{tenant_id}` with a PaymentFailure exception
- Verifies exception is created in the database

### Step 2: Assign Playbook
- Updates exception with domain/type/severity (as triage would do)
- Uses `PlaybookMatchingService` to find matching playbook
- Updates exception with `current_playbook_id` and `current_step=1`
- Creates `PlaybookStarted` event

### Step 3: Verify Playbook Panel (UI Check)
- GET `/exceptions/{tenant_id}/{exception_id}/playbook`
- Verifies playbook is assigned, steps are listed, and current step is 1

### Step 4: Complete Steps (Simulating UI Actions)
- POST `/exceptions/{tenant_id}/{exception_id}/playbook/steps/1/complete`
- POST `/exceptions/{tenant_id}/{exception_id}/playbook/steps/2/complete`
- POST `/exceptions/{tenant_id}/{exception_id}/playbook/steps/3/complete`
- Each call verifies the step is completed and moves to the next step

### Step 5: Verify Completion
- GET `/exceptions/{tenant_id}/{exception_id}/playbook`
- Verifies `currentStep` is `None` and all steps have status `completed`

### Step 6: Verify Timeline Events
- GET `/exceptions/{exception_id}/events`
- Verifies presence of:
  - `PlaybookStarted` event
  - 3× `PlaybookStepCompleted` events (one for each step)
  - `PlaybookCompleted` event
- Verifies events are in chronological order

## Test Data

The test uses seeded, deterministic data:

### Tenant
- ID: `TENANT_E2E_001`
- Status: `ACTIVE`

### Playbook
- Name: `PaymentFailurePlaybook`
- Version: `1`
- Conditions: Matches `domain=Finance, exception_type=PaymentFailure, severity_in=[high, critical]`
- Steps:
  1. **Notify Team** (`notify` action)
  2. **Retry Payment** (`call_tool` action)
  3. **Update Status** (`set_status` action)

### Exception
- Type: `PaymentFailure`
- Domain: `Finance`
- Severity: `HIGH`
- Source System: `PaymentSystem`

## Troubleshooting

### Test Fails: "Domain pack file not found"
- Ensure `domainpacks/finance.sample.json` exists
- Or skip domain pack fixtures if not needed (test will skip with appropriate message)

### Test Fails: "Tenant policy file not found"
- Ensure `tenantpacks/tenant_finance.sample.json` exists
- Or skip tenant policy fixtures if not needed (test will skip with appropriate message)

### Test Fails: Database Session Issues
- Ensure the test is using async fixtures correctly
- Check that `test_db_session` fixture is properly scoped

### Test Fails: API Key Authentication
- The test automatically sets up API keys via `setup_api_keys` fixture
- If issues persist, check that `get_api_key_auth()` is working correctly

## Expected Output

On successful run, you should see:

```
✅ E2E Test Passed!
   Exception ID: <uuid>
   Playbook: PaymentFailurePlaybook (ID: 1)
   Steps completed: 3/3
   Events in timeline: <number>
   Playbook lifecycle events: PlaybookStarted, 3×PlaybookStepCompleted, PlaybookCompleted

========================= 1 passed in X.XXs =========================
```

## Integration with CI/CD

This test can be run in CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run E2E Playbook Lifecycle Test
  run: |
    pytest tests/test_e2e_playbook_lifecycle.py -v --tb=short
```

The test is deterministic and does not require external services, making it suitable for CI environments.

