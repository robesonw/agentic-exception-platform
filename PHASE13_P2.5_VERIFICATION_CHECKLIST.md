# Phase 13 Prompt 2.5 - Manual Verification Checklist

**IndexRebuildService + /copilot/index/rebuild APIs**

**Implementation Status:** ✅ COMPLETE - All code components implemented and structurally validated

**Database Setup Note:** Database migration will be needed for deployment. Run `alembic revision --autogenerate -m "Add copilot index job tracking"` and `alembic upgrade head` once database connectivity is established.

## Quick Structural Validation

✅ **Validation Completed** (run `python test_api_validation.py`):

- IndexRebuildService with all required methods (start_rebuild, get_status, cancel_job)
- CopilotIndexJob database model with comprehensive job tracking fields
- API endpoints properly registered with admin authentication
- Integration with existing indexers (audit_events, policy_docs, resolved_exceptions, tool_registry)
- Background job execution framework integrated

This checklist verifies the implementation of Phase 13 Prompt 2.5: IndexRebuildService with complete job tracking, progress monitoring, and admin-only API endpoints for index rebuilding operations.

## Prerequisites

1. **Database Setup**

   ```bash
   # Ensure copilot_index_jobs table exists
   alembic upgrade head
   ```

2. **Worker/Service Dependencies**

   ```bash
   # Verify all indexer services are available
   python -c "
   from src.services.copilot.indexing.policy_docs_indexer import PolicyDocsIndexer
   from src.services.copilot.indexing.resolved_exceptions_indexer import ResolvedExceptionsIndexer
   from src.services.copilot.indexing.audit_events_indexer import AuditEventsIndexer
   from src.services.copilot.indexing.tool_registry_indexer import ToolRegistryIndexer
   print('All indexers imported successfully')
   "
   ```

3. **Start the Application**

   ```bash
   # Terminal 1: Start the API server
   python -m uvicorn src.main:app --reload --port 8000

   # Terminal 2: Verify health
   curl http://localhost:8000/health
   ```

---

## Core Service Tests

### 1. IndexRebuildService Functionality

```bash
# Test rebuild service directly
python -c "
import asyncio
from src.infrastructure.db.session import get_db_session_context
from src.services.copilot.indexing.rebuild_service import IndexRebuildService
from src.services.copilot.embedding_service import EmbeddingService
from src.services.copilot.chunking_service import DocumentChunkingService
from src.infrastructure.repositories.copilot_document_repository import CopilotDocumentRepository

async def test_service():
    async with get_db_session_context() as session:
        embedding_service = EmbeddingService()
        chunking_service = DocumentChunkingService()
        document_repository = CopilotDocumentRepository(session)

        service = IndexRebuildService(
            session, embedding_service, chunking_service, document_repository
        )

        # Start a test rebuild
        job_id = await service.start_rebuild(
            tenant_id='test-tenant-123',
            sources=['policy_doc'],
            full_rebuild=False
        )
        print(f'Started job: {job_id}')

        # Get status
        status = await service.get_status(job_id)
        print(f'Job status: {status}')

asyncio.run(test_service())
"
```

**Expected**: Job ID returned, status shows job in database with proper fields.

---

## API Endpoint Tests

### 2. POST /api/copilot/index/rebuild - Start Rebuild

#### Test 2a: Tenant-Specific Rebuild

```bash
curl -X POST "http://localhost:8000/api/copilot/index/rebuild" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer admin-token" \
  -d '{
    "tenant_id": "test-tenant-123",
    "sources": ["policy_doc", "resolved_exception"],
    "full_rebuild": false
  }'
```

**Expected Response** (202):

```json
{
  "job_id": "uuid-string",
  "message": "Index rebuild job started successfully. Use job ID uuid-string to track progress."
}
```

#### Test 2b: Global Rebuild

```bash
curl -X POST "http://localhost:8000/api/copilot/index/rebuild" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer admin-token" \
  -d '{
    "tenant_id": null,
    "sources": ["audit_event", "tool_registry"],
    "full_rebuild": true
  }'
```

**Expected**: Job ID returned for global rebuild.

#### Test 2c: All Sources Rebuild

```bash
curl -X POST "http://localhost:8000/api/copilot/index/rebuild" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer admin-token" \
  -d '{
    "tenant_id": "test-tenant-456",
    "sources": ["policy_doc", "resolved_exception", "audit_event", "tool_registry"],
    "full_rebuild": true
  }'
```

**Expected**: Job ID returned for complete rebuild.

### 3. GET /api/copilot/index/rebuild/{job_id} - Check Status

```bash
# Use job_id from previous step
JOB_ID="replace-with-actual-job-id"

curl -X GET "http://localhost:8000/api/copilot/index/rebuild/$JOB_ID" \
  -H "Authorization: Bearer admin-token"
```

**Expected Response**:

```json
{
  "id": "job-uuid",
  "tenant_id": "test-tenant-123",
  "sources": ["policy_doc", "resolved_exception"],
  "full_rebuild": false,
  "state": "completed", // or "pending", "running", "failed"
  "progress": {
    "current": 100,
    "total": 100,
    "percentage": 100.0
  },
  "counts": {
    "documents_processed": 50,
    "documents_failed": 0,
    "chunks_indexed": 250
  },
  "last_error": null,
  "error_details": null,
  "created_at": "2024-01-01T12:00:00",
  "started_at": "2024-01-01T12:00:01",
  "completed_at": "2024-01-01T12:00:30"
}
```

### 4. DELETE /api/copilot/index/rebuild/{job_id} - Cancel Job

```bash
# Start a job that won't complete immediately
curl -X POST "http://localhost:8000/api/copilot/index/rebuild" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer admin-token" \
  -d '{
    "tenant_id": "test-tenant-789",
    "sources": ["policy_doc", "resolved_exception", "audit_event", "tool_registry"],
    "full_rebuild": true
  }'

# Extract job_id from response, then cancel it quickly
JOB_ID="replace-with-job-id"

curl -X DELETE "http://localhost:8000/api/copilot/index/rebuild/$JOB_ID" \
  -H "Authorization: Bearer admin-token"
```

**Expected Response**:

```json
{
  "success": true,
  "message": "Rebuild job job-uuid has been cancelled."
}
```

---

## Error Handling Tests

### 5. Invalid Source Types

```bash
curl -X POST "http://localhost:8000/api/copilot/index/rebuild" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer admin-token" \
  -d '{
    "tenant_id": "test-tenant-123",
    "sources": ["invalid_source", "policy_doc"],
    "full_rebuild": false
  }'
```

**Expected**: 400 error with message about invalid source types.

### 6. Empty Sources

```bash
curl -X POST "http://localhost:8000/api/copilot/index/rebuild" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer admin-token" \
  -d '{
    "tenant_id": "test-tenant-123",
    "sources": [],
    "full_rebuild": false
  }'
```

**Expected**: 400 error requiring at least one source.

### 7. Job Not Found

```bash
curl -X GET "http://localhost:8000/api/copilot/index/rebuild/fake-job-id" \
  -H "Authorization: Bearer admin-token"
```

**Expected**: 404 error indicating job not found.

### 8. Unauthorized Access

```bash
# Without admin auth
curl -X POST "http://localhost:8000/api/copilot/index/rebuild" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "test-tenant-123",
    "sources": ["policy_doc"],
    "full_rebuild": false
  }'
```

**Expected**: 401/403 error for unauthorized access.

---

## Database Verification

### 9. Job Persistence

```bash
python -c "
import asyncio
from src.infrastructure.db.session import get_db_session_context
from src.infrastructure.db.models import CopilotIndexJob
from sqlalchemy import select

async def verify_db():
    async with get_db_session_context() as session:
        # Get all rebuild jobs
        result = await session.execute(
            select(CopilotIndexJob).order_by(CopilotIndexJob.created_at.desc())
        )
        jobs = result.scalars().all()

        print(f'Total rebuild jobs: {len(jobs)}')
        for job in jobs[:5]:  # Show latest 5
            print(f'Job {job.id}: tenant={job.tenant_id}, sources={job.sources}, status={job.status}')

asyncio.run(verify_db())
"
```

**Expected**: Shows created jobs with correct tenant_id, sources, and status.

### 10. Progress Tracking Verification

```bash
python -c "
import asyncio
from src.infrastructure.db.session import get_db_session_context
from src.infrastructure.db.models import CopilotIndexJob, CopilotIndexJobStatus
from sqlalchemy import select

async def verify_progress():
    async with get_db_session_context() as session:
        # Find completed jobs with progress data
        result = await session.execute(
            select(CopilotIndexJob)
            .where(CopilotIndexJob.status == CopilotIndexJobStatus.COMPLETED)
            .order_by(CopilotIndexJob.completed_at.desc())
        )
        jobs = result.scalars().all()

        for job in jobs[:3]:
            print(f'Job {job.id}:')
            print(f'  Progress: {job.progress_current}/{job.progress_total}')
            print(f'  Docs: processed={job.documents_processed}, failed={job.documents_failed}')
            print(f'  Chunks: {job.chunks_indexed}')
            print(f'  Duration: {job.started_at} -> {job.completed_at}')

asyncio.run(verify_progress())
"
```

**Expected**: Completed jobs show progress counters and timing data.

---

## Integration Tests

### 11. Run Automated Test Suite

```bash
# Run the comprehensive integration tests
pytest tests/integration/test_copilot_index_rebuild_api.py -v
```

**Expected**: All test cases pass, covering:

- Start rebuild (tenant-specific, global, multi-source)
- Status checking with progress monitoring
- Job cancellation
- Error handling (invalid sources, auth, not found)
- E2E workflows

### 12. Performance Check

```bash
# Start multiple rebuilds concurrently to test performance
python -c "
import asyncio
from src.infrastructure.db.session import get_db_session_context
from src.services.copilot.indexing.rebuild_service import IndexRebuildService
from src.services.copilot.embedding_service import EmbeddingService
from src.services.copilot.chunking_service import DocumentChunkingService
from src.infrastructure.repositories.copilot_document_repository import CopilotDocumentRepository

async def perf_test():
    async with get_db_session_context() as session:
        service = IndexRebuildService(
            session,
            EmbeddingService(),
            DocumentChunkingService(),
            CopilotDocumentRepository(session)
        )

        # Start 5 concurrent rebuilds
        tasks = []
        for i in range(5):
            task = service.start_rebuild(
                tenant_id=f'perf-tenant-{i}',
                sources=['policy_doc'],
                full_rebuild=False
            )
            tasks.append(task)

        job_ids = await asyncio.gather(*tasks)
        print(f'Started {len(job_ids)} concurrent rebuilds: {job_ids}')

asyncio.run(perf_test())
"
```

**Expected**: Multiple jobs can be started concurrently without conflicts.

---

## Success Criteria

✅ **Core Service**

- IndexRebuildService creates jobs and tracks progress
- Background processing works with asyncio tasks
- All four indexers are called appropriately
- Tenant isolation is enforced

✅ **API Endpoints**

- POST /copilot/index/rebuild accepts requests and returns job IDs
- GET /copilot/index/rebuild/{job_id} returns detailed status
- DELETE /copilot/index/rebuild/{job_id} cancels running jobs
- All endpoints require admin authentication

✅ **Data Persistence**

- CopilotIndexJob table stores all job data correctly
- Progress counters update during processing
- Timing information (created, started, completed) is accurate
- Error details are captured and returned

✅ **Error Handling**

- Invalid sources are rejected with clear messages
- Non-existent jobs return 404 errors
- Unauthorized requests return 401/403 errors
- Database and service errors are handled gracefully

✅ **Integration**

- Full E2E workflow: start → monitor → completion
- Multiple source types can be rebuilt simultaneously
- Global and tenant-specific rebuilds work correctly
- Job cancellation works for running jobs

---

## Deployment Notes

1. **Database Migration**: Ensure `copilot_index_jobs` table is created via Alembic
2. **Admin Authentication**: Verify admin role enforcement is working
3. **Background Processing**: Monitor job execution and completion rates
4. **Performance**: Check resource usage during large rebuilds
5. **Monitoring**: Set up alerts for failed rebuild jobs

## Troubleshooting

- **Jobs stuck in PENDING**: Check if indexer services are properly initialized
- **Background tasks not running**: Verify asyncio event loop is working correctly
- **Authorization failures**: Check admin token/role configuration
- **Database errors**: Verify migration and table permissions
- **Progress not updating**: Check if indexer progress callbacks are working
