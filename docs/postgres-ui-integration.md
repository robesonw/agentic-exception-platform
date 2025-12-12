# PostgreSQL UI Integration

## Summary

Updated the API read endpoints to use PostgreSQL instead of the in-memory store, so data persisted to PostgreSQL will now appear in the UI.

## Changes Made

### 1. Updated GET /exceptions/{tenant_id}/{exception_id}
- **File**: `src/api/routes/exceptions.py`
- **Change**: Now reads from PostgreSQL using `ExceptionRepository`
- **Fallback**: Falls back to in-memory store if PostgreSQL read fails (for backward compatibility)
- **Features**:
  - Maps database Exception model to ExceptionRecord
  - Retrieves events for audit trail
  - Builds pipeline result from events

### 2. Updated GET /ui/status/{tenant_id}
- **File**: `src/api/routes/ui_status.py`
- **Change**: Now reads from PostgreSQL using `ExceptionRepository.list_exceptions()`
- **Fallback**: Falls back to in-memory store if PostgreSQL read fails
- **Features**:
  - Supports filtering by status
  - Supports pagination
  - Maps database models to ExceptionRecord format

## Domain Packs and Tenant Packs

**Important**: Domain Packs and Tenant Packs are **NOT required** for reading/displaying data in the UI.

- **Domain Packs**: Used for processing/normalization during ingestion
- **Tenant Packs**: Used for policy decisions during pipeline execution
- **UI Display**: Only requires data in PostgreSQL - no packs needed

The UI will display:
- All exceptions stored in PostgreSQL
- Domain information (from `exception.domain` column)
- Status, severity, timestamps, etc. (from database columns)

## Testing

After restarting the API server:

1. **Verify data appears in UI**:
   ```powershell
   # Seed data
   python scripts/seed_postgres_via_api.py --tenant-id TENANT_FINANCE_001 --count 50
   
   # Check UI endpoint
   curl http://localhost:8000/ui/status/TENANT_FINANCE_001
   ```

2. **Verify individual exception**:
   ```powershell
   # Get exception ID from database
   docker exec sentinai-postgres psql -U postgres -d sentinai -c "SELECT exception_id FROM exception LIMIT 1;"
   
   # Check exception endpoint
   curl http://localhost:8000/exceptions/TENANT_FINANCE_001/{exception_id}
   ```

## Notes

- The API still supports the in-memory store as a fallback for backward compatibility
- All new data should be persisted to PostgreSQL via the ingestion endpoint
- The UI will automatically show data from PostgreSQL once the API server is restarted

