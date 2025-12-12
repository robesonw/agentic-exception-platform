# Repository Test Suite

## Overview

This directory contains comprehensive tests for all Phase 6 DB-backed repositories.

## Test Files

### Core Repository Tests

- `test_exceptions_repository_crud.py` - CRUD operations for ExceptionRepository
- `test_exceptions_repository_copilot_helpers.py` - Co-Pilot query helpers
- `test_exception_events_repository_append_only.py` - Append-only event log operations
- `test_idempotency_helpers.py` - Idempotent write operations (upsert, append_if_new)
- `test_base_repository.py` - AbstractBaseRepository interface tests

### Infrastructure Repository Tests

Located in `tests/infrastructure/repositories/`:

- `test_tenant_repository.py` - Tenant CRUD and filtering
- `test_domain_pack_repository.py` - Domain pack versioning
- `test_tenant_policy_pack_repository.py` - Tenant policy pack versioning
- `test_playbook_repository.py` - Playbook CRUD and filtering
- `test_playbook_step_repository.py` - Playbook step ordering and management
- `test_tool_definition_repository.py` - Tool definition CRUD (global and tenant-scoped)

## Running Tests

```bash
# Run all repository tests
pytest tests/repository tests/infrastructure/repositories -v

# Run with coverage
pytest tests/repository tests/infrastructure/repositories \
  --cov=src.infrastructure.repositories \
  --cov=src.repository \
  --cov-report=term-missing

# Run specific test file
pytest tests/repository/test_exceptions_repository_crud.py -v

# Run specific test class
pytest tests/repository/test_exceptions_repository_crud.py::TestExceptionRepositoryCreate -v
```

## Test Fixtures

Shared fixtures are defined in `tests/repository/conftest.py`:

- `test_engine` - In-memory SQLite engine (fresh for each test)
- `test_session` - AsyncSession for database operations
- `fixed_timestamp` - Deterministic timestamp (2024-01-15 12:00:00 UTC)
- `sample_tenants` - Pre-populated tenant data

## Test Coverage Requirements

Each repository test suite must cover:

1. **Happy-path CRUD operations**
   - Create, Read, Update, Delete (where applicable)
   - Proper error handling for invalid inputs

2. **Tenant isolation**
   - No cross-tenant data leakage
   - Tenant-scoped queries return only correct tenant's data
   - Global resources (domain packs) are accessible to all tenants

3. **Filtering**
   - Domain, status, severity, date range filters
   - Filter combinations
   - Pagination with filters

4. **Versioning behavior** (where applicable)
   - Domain pack versioning (get latest, get specific version)
   - Tenant policy pack versioning
   - Playbook versioning

5. **Idempotency helpers** (where applicable)
   - `upsert_exception` - Safe create/update
   - `append_event_if_new` - Prevents duplicate events
   - `event_exists` - Checks for event existence

## Test Determinism

All tests must be deterministic:

- Use `fixed_timestamp` fixture for consistent timestamps
- Use explicit ORDER BY clauses in queries
- Avoid dependency on random data or system time
- Each test gets a fresh database (no shared state)

## Adding New Tests

When adding tests for a new repository:

1. Create test file in appropriate directory:
   - Core repositories → `tests/repository/test_<name>_repository.py`
   - Infrastructure repositories → `tests/infrastructure/test_<name>_repository.py`

2. Use shared fixtures from `conftest.py`:
   ```python
   @pytest.mark.asyncio
   async def test_operation(self, test_session, sample_tenants):
       repo = MyRepository(test_session)
       # ... test code ...
   ```

3. Follow naming convention:
   - Test classes: `Test<RepositoryName><Operation>`
   - Test methods: `test_<operation>_<scenario>`

4. Ensure coverage for all required areas (CRUD, isolation, filtering, etc.)

## Continuous Integration

Repository tests are run as part of CI/CD:

- All tests must pass before merge
- Coverage threshold: 80% for repository code
- Tests run on every commit and pull request

