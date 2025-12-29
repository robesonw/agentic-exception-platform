"""
Admin API routes for Domain Pack Management.

Phase 2: Domain Pack upload, validation, storage, versioning, and rollback.

Matches specification from phase2-mvp-issues.md Issue 37.
"""

import asyncio
import json
import logging
from typing import Any

import yaml
from fastapi import APIRouter, File, HTTPException, Path, UploadFile
from pydantic import BaseModel, Field

from src.domainpack.loader import (
    DomainPackRegistry,
    DomainPackValidationError,
    load_domain_pack,
)
from src.domainpack.storage import DomainPackStorage
from src.domainpack.test_runner import DomainPackTestRunner, TestSuiteReport, get_test_runner
from src.models.domain_pack import DomainPack
from src.tenantpack.loader import load_tenant_policy
from src.services.copilot.indexing.rebuild_service import IndexRebuildService, IndexRebuildError
from src.services.copilot.chunking_service import DocumentChunkingService
from src.services.copilot.embedding_service import EmbeddingService
from src.infrastructure.repositories.copilot_document_repository import CopilotDocumentRepository
from src.infrastructure.db.session import get_db_session_context
from src.audit.logger import AuditLogger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/domainpacks", tags=["admin-domainpacks"])

# Global instances (would be injected via dependency in production)
_domain_pack_storage: DomainPackStorage | None = None
_domain_pack_registry: DomainPackRegistry | None = None


def set_domain_pack_storage(storage: DomainPackStorage) -> None:
    """Set the domain pack storage (for dependency injection)."""
    global _domain_pack_storage
    _domain_pack_storage = storage


def set_domain_pack_registry(registry: DomainPackRegistry) -> None:
    """Set the domain pack registry (for dependency injection)."""
    global _domain_pack_registry
    _domain_pack_registry = registry


def get_domain_pack_storage() -> DomainPackStorage:
    """Get the domain pack storage instance."""
    global _domain_pack_storage
    if _domain_pack_storage is None:
        _domain_pack_storage = DomainPackStorage()
    return _domain_pack_storage


def get_domain_pack_registry() -> DomainPackRegistry:
    """Get the domain pack registry instance."""
    global _domain_pack_registry
    if _domain_pack_registry is None:
        _domain_pack_registry = DomainPackRegistry()
    return _domain_pack_registry


class DomainPackUploadResponse(BaseModel):
    """Response for domain pack upload."""

    domain_name: str = Field(..., alias="domainName")
    version: str
    message: str
    stored: bool = Field(..., description="Whether pack was stored successfully")
    registered: bool = Field(..., description="Whether pack was registered successfully")


class DomainPackInfo(BaseModel):
    """Information about a domain pack."""

    domain_name: str = Field(..., alias="domainName")
    versions: list[str]
    latest_version: str = Field(..., alias="latestVersion")
    usage_count: int = Field(..., alias="usageCount")
    last_used_timestamp: str | None = Field(None, alias="lastUsedTimestamp")


class DomainPackListResponse(BaseModel):
    """Response for listing domain packs."""

    tenant_id: str = Field(..., alias="tenantId")
    packs: list[DomainPackInfo]
    total: int


class RollbackRequest(BaseModel):
    """Request for rolling back domain pack version."""

    domain_name: str = Field(..., alias="domainName")
    target_version: str = Field(..., alias="targetVersion")


class RollbackResponse(BaseModel):
    """Response for rollback operation."""

    domain_name: str = Field(..., alias="domainName")
    previous_version: str = Field(..., alias="previousVersion")
    new_version: str = Field(..., alias="newVersion")
    success: bool
    message: str


class TestSuiteExecutionResponse(BaseModel):
    """Response for test suite execution."""

    domain_name: str = Field(..., alias="domainName")
    tenant_id: str = Field(..., alias="tenantId")
    total_tests: int = Field(..., alias="totalTests")
    passed_tests: int = Field(..., alias="passedTests")
    failed_tests: int = Field(..., alias="failedTests")
    execution_time_seconds: float = Field(..., alias="executionTimeSeconds")
    test_results: list[dict[str, Any]] = Field(..., alias="testResults")
    errors: list[str] = Field(default_factory=list)


@router.post("/{tenant_id}", response_model=DomainPackUploadResponse)
async def upload_domain_pack(
    tenant_id: str = Path(..., description="Tenant identifier"),
    file: UploadFile = File(..., description="Domain Pack file (JSON or YAML)"),
    version: str | None = None,
) -> DomainPackUploadResponse:
    """
    Upload and register a Domain Pack for a tenant.
    
    Supports JSON and YAML formats. The pack is validated, stored, and registered.
    
    Args:
        tenant_id: Tenant identifier
        file: Uploaded Domain Pack file (JSON or YAML)
        version: Optional version string. If not provided, defaults to "1.0.0"
        
    Returns:
        DomainPackUploadResponse with upload status
        
    Raises:
        HTTPException: If upload, validation, or storage fails
    """
    storage = get_domain_pack_storage()
    registry = get_domain_pack_registry()
    
    # Read file content
    try:
        content = await file.read()
        file_content = content.decode("utf-8")
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read uploaded file: {str(e)}"
        )
    
    # Parse based on file extension or content
    file_extension = file.filename.split(".")[-1].lower() if file.filename else ""
    
    try:
        if file_extension in ("json",):
            data = json.loads(file_content)
        elif file_extension in ("yaml", "yml"):
            data = yaml.safe_load(file_content)
            if data is None:
                raise HTTPException(status_code=400, detail="YAML file is empty or contains no data")
        else:
            # Try to auto-detect format
            try:
                data = json.loads(file_content)
            except json.JSONDecodeError:
                try:
                    data = yaml.safe_load(file_content)
                    if data is None:
                        raise HTTPException(status_code=400, detail="File content is empty or invalid")
                except yaml.YAMLError:
                    raise HTTPException(
                        status_code=400,
                        detail="File format not recognized. Expected JSON or YAML."
                    )
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
    
    # Validate and create DomainPack
    try:
        pack = DomainPack.model_validate(data)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Domain Pack schema validation failed: {str(e)}"
        )
    
    # Determine version (DomainPack doesn't have version field, use provided or default)
    pack_version = version or "1.0.0"
    
    # Store pack
    stored = False
    try:
        storage.store_pack(tenant_id=tenant_id, pack=pack, version=pack_version)
        stored = True
        logger.info(
            f"Stored Domain Pack '{pack.domain_name}' version {pack_version} "
            f"for tenant '{tenant_id}'"
        )
    except Exception as e:
        logger.error(f"Failed to store Domain Pack: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store Domain Pack: {str(e)}"
        )
    
    # Register pack
    registered = False
    try:
        registry.register(pack=pack, version=pack_version, tenant_id=tenant_id)
        registered = True
        logger.info(
            f"Registered Domain Pack '{pack.domain_name}' version {pack_version} "
            f"for tenant '{tenant_id}'"
        )
    except DomainPackValidationError as e:
        logger.error(f"Failed to register Domain Pack: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Domain Pack validation failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to register Domain Pack: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register Domain Pack: {str(e)}"
        )
    
    # Trigger async policy docs indexing (non-blocking)
    if registered:
        asyncio.create_task(
            _trigger_policy_docs_indexing(
                tenant_id=tenant_id,
                domain=pack.domain_name,
                pack_version=pack_version,
                operation="domain_pack_import"
            )
        )

    storage = get_domain_pack_storage()
    registry = get_domain_pack_registry()
    
    # Get list of domains for tenant
    domains = registry.list_domains(tenant_id=tenant_id)
    
    # Build pack info with versions and usage stats
    pack_infos = []
    for domain_name in domains:
        # Get versions
        versions = storage.list_versions(tenant_id=tenant_id, domain_name=domain_name)
        if not versions:
            continue
        
        # Get latest version
        latest_version = versions[-1] if versions else None
        
        # Get usage stats from storage
        usage_stats = storage.get_usage_stats(tenant_id=tenant_id, domain_name=domain_name)
        
        # Find stats for latest version
        usage_count = 0
        last_used = None
        if latest_version:
            stats_key = f"{domain_name}:{latest_version}"
            if stats_key in usage_stats:
                stats = usage_stats[stats_key]
                usage_count = stats.get("usage_count", 0)
                last_used = stats.get("last_used")
        
        pack_info = DomainPackInfo(
            domainName=domain_name,
            versions=sorted(versions),
            latestVersion=latest_version or "unknown",
            usageCount=usage_count,
            lastUsedTimestamp=last_used,
        )
        pack_infos.append(pack_info)
    
    return DomainPackListResponse(
        tenantId=tenant_id,
        packs=pack_infos,
        total=len(pack_infos),
    )


@router.post("/{tenant_id}/rollback", response_model=RollbackResponse)
async def rollback_domain_pack(
    tenant_id: str = Path(..., description="Tenant identifier"),
    request: RollbackRequest = ...,
) -> RollbackResponse:
    """
    Rollback Domain Pack to a previous version.
    
    Args:
        tenant_id: Tenant identifier
        request: Rollback request with domain name and target version
        
    Returns:
        RollbackResponse with rollback status
        
    Raises:
        HTTPException: If rollback fails
    """
    storage = get_domain_pack_storage()
    registry = get_domain_pack_registry()
    
    domain_name = request.domain_name
    target_version = request.target_version
    
    # Get current version
    versions = storage.list_versions(tenant_id=tenant_id, domain_name=domain_name)
    if not versions:
        raise HTTPException(
            status_code=404,
            detail=f"Domain Pack '{domain_name}' not found for tenant '{tenant_id}'"
        )
    
    previous_version = versions[-1]  # Latest version
    
    # Verify target version exists
    if target_version not in versions:
        raise HTTPException(
            status_code=404,
            detail=f"Version '{target_version}' not found for Domain Pack '{domain_name}'. "
                   f"Available versions: {', '.join(versions)}"
        )
    
    # Get the target version pack
    target_pack = storage.get_pack(
        tenant_id=tenant_id,
        domain_name=domain_name,
        version=target_version,
    )
    
    if not target_pack:
        raise HTTPException(
            status_code=404,
            detail=f"Failed to load version '{target_version}' for Domain Pack '{domain_name}'"
        )
    
    # Re-register the target version as the latest (rollback)
    try:
        registry.register(
            pack=target_pack,
            version=target_version,
            tenant_id=tenant_id,
        )
        
        logger.info(
            f"Rolled back Domain Pack '{domain_name}' from version {previous_version} "
            f"to version {target_version} for tenant '{tenant_id}'"
        )
        
        return RollbackResponse(
            domainName=domain_name,
            previousVersion=previous_version,
            newVersion=target_version,
            success=True,
            message=f"Successfully rolled back to version {target_version}",
        )
    except Exception as e:
        logger.error(f"Failed to rollback Domain Pack: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to rollback Domain Pack: {str(e)}"
        )


@router.post("/{tenant_id}/{domain_name}/run-tests", response_model=TestSuiteExecutionResponse)
async def run_domain_pack_tests(
    tenant_id: str = Path(..., description="Tenant identifier"),
    domain_name: str = Path(..., description="Domain name"),
) -> TestSuiteExecutionResponse:
    """
    Run test suites for a domain pack.
    
    POST /admin/domainpacks/{tenantId}/{domainName}/run-tests
    
    Executes all test cases from the domain pack's testSuites and validates
    results against expected outputs, including playbook ID validation.
    
    Returns:
        TestSuiteExecutionResponse with pass/fail results
    """
    try:
        # Get domain pack from registry
        registry = get_domain_pack_registry()
        domain_pack = registry.get_latest(tenant_id, domain_name)
        
        if not domain_pack:
            raise HTTPException(
                status_code=404,
                detail=f"Domain pack '{domain_name}' not found for tenant '{tenant_id}'",
            )
        
        # Check if domain pack has test suites
        if not domain_pack.test_suites:
            raise HTTPException(
                status_code=400,
                detail=f"Domain pack '{domain_name}' has no test suites defined",
            )
        
        # Load tenant policy
        try:
            # Try to load from tenantpacks directory
            from pathlib import Path
            
            tenant_pack_path = Path(f"tenantpacks/tenant_{domain_name}.sample.json")
            if not tenant_pack_path.exists():
                tenant_pack_path = Path(f"tenantpacks/{domain_name}.sample.json")
            
            if tenant_pack_path.exists():
                tenant_policy = load_tenant_policy(str(tenant_pack_path))
            else:
                # Create minimal tenant policy
                tenant_policy = TenantPolicyPack(
                    tenant_id=tenant_id,
                    domain_name=domain_name,
                    approved_tools=list(domain_pack.tools.keys()) if domain_pack.tools else [],
                )
        except Exception as e:
            logger.warning(f"Failed to load tenant policy, creating minimal: {e}")
            tenant_policy = TenantPolicyPack(
                tenant_id=tenant_id,
                domain_name=domain_name,
                approved_tools=list(domain_pack.tools.keys()) if domain_pack.tools else [],
            )
        
        # Run test suites
        test_runner = get_test_runner()
        report = await test_runner.run_test_suites(
            domain_pack=domain_pack,
            tenant_policy=tenant_policy,
        )
        
        # Convert test results to dict for JSON serialization
        test_results_dict = []
        for result in report.test_results:
            test_results_dict.append({
                "testIndex": result.test_index,
                "passed": result.passed,
                "errorMessage": result.error_message,
                "validationDetails": result.validation_details,
            })
        
        return TestSuiteExecutionResponse(
            domain_name=report.domain_name,
            tenant_id=report.tenant_id,
            total_tests=report.total_tests,
            passed_tests=report.passed_tests,
            failed_tests=report.failed_tests,
            execution_time_seconds=report.execution_time_seconds,
            test_results=test_results_dict,
            errors=report.errors,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to run test suites: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run test suites: {str(e)}",
        )


async def _trigger_policy_docs_indexing(
    tenant_id: str,
    domain: str,
    pack_version: str,
    operation: str,
) -> None:
    """
    Trigger async policy docs indexing for a tenant/domain/version.
    
    This function runs in the background and does not block the HTTP response.
    
    Args:
        tenant_id: Tenant identifier
        domain: Domain name  
        pack_version: Pack version
        operation: Operation type (domain_pack_import, tenant_policy_activation, etc.)
    """
    try:
        # Create indexing service
        async with get_db_session_context() as db_session:
            # Initialize required services
            chunking_service = DocumentChunkingService()
            embedding_service = EmbeddingService()
            document_repository = CopilotDocumentRepository()
            
            rebuild_service = IndexRebuildService(
                db_session=db_session,
                embedding_service=embedding_service,
                chunking_service=chunking_service,
                document_repository=document_repository,
            )
            
            # Start indexing job for policy_doc source only
            job_id = await rebuild_service.start_rebuild(
                tenant_id=tenant_id,
                sources=["policy_doc"],
                full_rebuild=False,  # Incremental by default
            )
            
            logger.info(
                f"Started policy docs indexing job {job_id} for tenant {tenant_id}, "
                f"domain {domain}, version {pack_version}, operation {operation}"
            )
            
            # Record audit event
            try:
                audit_logger = AuditLogger()
                await audit_logger.log_event(
                    event_type="POLICY_INDEX_TRIGGERED",
                    tenant_id=tenant_id,
                    details={
                        "job_id": job_id,
                        "domain": domain,
                        "pack_version": pack_version,
                        "operation": operation,
                        "source_types": ["policy_doc"],
                    },
                    result="success",
                )
            except Exception as audit_error:
                # Don't fail the indexing if audit logging fails
                logger.warning(f"Failed to record audit event: {audit_error}")
                
    except IndexRebuildError as e:
        logger.error(
            f"Failed to start policy docs indexing for tenant {tenant_id}, "
            f"domain {domain}, version {pack_version}: {e}"
        )
        # Record audit failure
        try:
            audit_logger = AuditLogger()
            await audit_logger.log_event(
                event_type="POLICY_INDEX_TRIGGERED",
                tenant_id=tenant_id,
                details={
                    "domain": domain,
                    "pack_version": pack_version,
                    "operation": operation,
                    "error": str(e),
                },
                result="failure",
            )
        except Exception:
            pass  # Ignore audit logging failures
            
    except Exception as e:
        logger.error(
            f"Unexpected error triggering policy docs indexing for tenant {tenant_id}: {e}",
            exc_info=True
        )

