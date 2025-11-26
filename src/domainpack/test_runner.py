"""
Domain Pack Test Suite Execution.

Phase 2: Domain Pack Test Suite Execution (Issue 46)
- Run test cases from Domain Pack testSuites
- Validate test results against expected outputs
- Check expectedPlaybookId
- Generate test reports

Matches specification from docs/05-domain-pack-schema.md and phase2-mvp-issues.md Issue 46.
"""

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from src.models.domain_pack import DomainPack, TestCase
from src.models.tenant_policy import TenantPolicyPack
from src.orchestrator.runner import run_pipeline

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result of a single test case execution."""

    test_index: int
    passed: bool
    error_message: Optional[str] = None
    actual_output: Optional[dict[str, Any]] = None
    expected_output: Optional[dict[str, Any]] = None
    validation_details: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestSuiteReport:
    """Report for a test suite execution."""

    domain_name: str
    tenant_id: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    test_results: list[TestResult] = field(default_factory=list)
    execution_time_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


class DomainPackTestRunner:
    """
    Executes test suites from Domain Packs.
    
    Runs test cases through the orchestrator and validates results
    against expected outputs, including playbook ID validation.
    """

    def __init__(self):
        """Initialize the test runner."""
        pass

    async def run_test_suites(
        self,
        domain_pack: DomainPack,
        tenant_policy: TenantPolicyPack,
        orchestrator: Optional[Any] = None,
    ) -> TestSuiteReport:
        """
        Run all test suites from a Domain Pack.
        
        Args:
            domain_pack: Domain Pack containing test suites
            tenant_policy: Tenant Policy Pack for execution context
            orchestrator: Optional orchestrator instance (uses run_pipeline if None)
            
        Returns:
            TestSuiteReport with pass/fail results
        """
        import time
        
        start_time = time.time()
        domain_name = domain_pack.domain_name
        tenant_id = tenant_policy.tenant_id
        
        logger.info(
            f"Running test suites for domain '{domain_name}' tenant '{tenant_id}': "
            f"{len(domain_pack.test_suites)} test cases"
        )
        
        test_results: list[TestResult] = []
        errors: list[str] = []
        
        # Run each test case
        for idx, test_case in enumerate(domain_pack.test_suites):
            try:
                result = await self._run_test_case(
                    test_case=test_case,
                    test_index=idx,
                    domain_pack=domain_pack,
                    tenant_policy=tenant_policy,
                    orchestrator=orchestrator,
                )
                test_results.append(result)
            except Exception as e:
                error_msg = f"Test case {idx} execution failed: {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)
                test_results.append(
                    TestResult(
                        test_index=idx,
                        passed=False,
                        error_message=error_msg,
                    )
                )
        
        execution_time = time.time() - start_time
        passed_count = sum(1 for r in test_results if r.passed)
        failed_count = len(test_results) - passed_count
        
        report = TestSuiteReport(
            domain_name=domain_name,
            tenant_id=tenant_id,
            total_tests=len(test_results),
            passed_tests=passed_count,
            failed_tests=failed_count,
            test_results=test_results,
            execution_time_seconds=execution_time,
            errors=errors,
        )
        
        logger.info(
            f"Test suite execution completed: {passed_count}/{len(test_results)} tests passed "
            f"in {execution_time:.2f}s"
        )
        
        return report

    async def _run_test_case(
        self,
        test_case: TestCase,
        test_index: int,
        domain_pack: DomainPack,
        tenant_policy: TenantPolicyPack,
        orchestrator: Optional[Any] = None,
    ) -> TestResult:
        """
        Run a single test case.
        
        Args:
            test_case: TestCase to execute
            test_index: Index of test case in suite
            domain_pack: Domain Pack
            tenant_policy: Tenant Policy Pack
            orchestrator: Optional orchestrator instance
            
        Returns:
            TestResult with pass/fail status
        """
        # Prepare input exception
        input_data = test_case.input.copy()
        
        # Ensure tenantId is set
        if "tenantId" not in input_data:
            input_data["tenantId"] = tenant_policy.tenant_id
        
        # Ensure domainName is set
        if "domainName" not in input_data:
            input_data["domainName"] = domain_pack.domain_name
        
        # Run through orchestrator
        try:
            if orchestrator is not None:
                # Use provided orchestrator (for testing/mocking)
                pipeline_result = await orchestrator(
                    domain_pack=domain_pack,
                    tenant_policy=tenant_policy,
                    exceptions_batch=[input_data],
                )
            else:
                # Use actual run_pipeline
                pipeline_result = await run_pipeline(
                    domain_pack=domain_pack,
                    tenant_policy=tenant_policy,
                    exceptions_batch=[input_data],
                    enable_parallel=False,  # Sequential for test cases
                )
        except Exception as e:
            return TestResult(
                test_index=test_index,
                passed=False,
                error_message=f"Pipeline execution failed: {str(e)}",
            )
        
        # Extract actual output from pipeline result
        actual_output = self._extract_output_from_pipeline_result(pipeline_result)
        
        # Validate against expected output
        validation_result = self._validate_output(
            actual_output=actual_output,
            expected_output=test_case.expected_output,
            domain_pack=domain_pack,
        )
        
        return TestResult(
            test_index=test_index,
            passed=validation_result["passed"],
            error_message=validation_result.get("error_message"),
            actual_output=actual_output,
            expected_output=test_case.expected_output,
            validation_details=validation_result.get("details", {}),
        )

    def _extract_output_from_pipeline_result(
        self, pipeline_result: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Extract relevant output from pipeline result for validation.
        
        Args:
            pipeline_result: Result from run_pipeline
            
        Returns:
            Dictionary with extracted output fields
        """
        output = {}
        
        # Extract from first result (test cases run one exception at a time)
        results = pipeline_result.get("results", [])
        if results:
            first_result = results[0]
            
            # Extract exception ID
            output["exceptionId"] = first_result.get("exceptionId")
            
            # Extract stages decisions
            stages = first_result.get("stages", {})
            output["stages"] = {}
            
            for stage_name, decision in stages.items():
                if decision:
                    output["stages"][stage_name] = {
                        "decision": decision.get("decision") if isinstance(decision, dict) else str(decision),
                        "confidence": decision.get("confidence") if isinstance(decision, dict) else None,
                        "nextStep": decision.get("nextStep") if isinstance(decision, dict) else None,
                    }
            
            # Extract exception record
            exception = first_result.get("exception")
            if exception:
                if isinstance(exception, dict):
                    output["exception"] = {
                        "exception_type": exception.get("exception_type") or exception.get("exceptionType"),
                        "severity": exception.get("severity"),
                        "domain_name": exception.get("domain_name") or exception.get("domainName"),
                        "tenant_id": exception.get("tenant_id") or exception.get("tenantId"),
                    }
                else:
                    # ExceptionRecord object
                    output["exception"] = {
                        "exception_type": getattr(exception, "exception_type", None),
                        "severity": str(getattr(exception, "severity", "")) if hasattr(exception, "severity") else None,
                        "domain_name": getattr(exception, "domain_name", None),
                        "tenant_id": getattr(exception, "tenant_id", None),
                    }
            
            # Extract playbook ID from resolution stage
            resolution_stage = output.get("stages", {}).get("resolution", {})
            if resolution_stage:
                # Check for playbook ID in evidence or decision details
                resolution_decision = stages.get("resolution")
                if resolution_decision and isinstance(resolution_decision, dict):
                    evidence = resolution_decision.get("evidence", [])
                    for item in evidence:
                        if isinstance(item, str) and "playbook" in item.lower():
                            # Try to extract playbook ID
                            import re
                            match = re.search(r"playbook[:\s]+([^\s,]+)", item, re.IGNORECASE)
                            if match:
                                output["playbookId"] = match.group(1)
                                break
                    
                    # Also check in decision details
                    if "playbookId" not in output:
                        decision_details = resolution_decision.get("details", {})
                        if isinstance(decision_details, dict):
                            output["playbookId"] = decision_details.get("playbookId") or decision_details.get("playbook_id")
        
        return output

    def _validate_output(
        self,
        actual_output: dict[str, Any],
        expected_output: dict[str, Any],
        domain_pack: DomainPack,
    ) -> dict[str, Any]:
        """
        Validate actual output against expected output.
        
        Args:
            actual_output: Actual output from pipeline
            expected_output: Expected output from test case
            domain_pack: Domain Pack for reference
            
        Returns:
            Dictionary with validation result
        """
        details: dict[str, Any] = {}
        errors: list[str] = []
        
        # Check expectedPlaybookId if specified
        expected_playbook_id = expected_output.get("expectedPlaybookId") or expected_output.get("expected_playbook_id")
        if expected_playbook_id:
            actual_playbook_id = actual_output.get("playbookId")
            if actual_playbook_id != expected_playbook_id:
                errors.append(
                    f"Playbook ID mismatch: expected '{expected_playbook_id}', got '{actual_playbook_id}'"
                )
                details["playbookId_mismatch"] = {
                    "expected": expected_playbook_id,
                    "actual": actual_playbook_id,
                }
            else:
                details["playbookId_match"] = True
        
        # Check expected exception type if specified
        expected_exception_type = expected_output.get("expectedExceptionType") or expected_output.get("expected_exception_type")
        if expected_exception_type:
            actual_exception = actual_output.get("exception", {})
            actual_exception_type = actual_exception.get("exception_type")
            if actual_exception_type != expected_exception_type:
                errors.append(
                    f"Exception type mismatch: expected '{expected_exception_type}', got '{actual_exception_type}'"
                )
                details["exceptionType_mismatch"] = {
                    "expected": expected_exception_type,
                    "actual": actual_exception_type,
                }
            else:
                details["exceptionType_match"] = True
        
        # Check expected severity if specified
        expected_severity = expected_output.get("expectedSeverity") or expected_output.get("expected_severity")
        if expected_severity:
            actual_exception = actual_output.get("exception", {})
            actual_severity = actual_exception.get("severity")
            if actual_severity != expected_severity:
                errors.append(
                    f"Severity mismatch: expected '{expected_severity}', got '{actual_severity}'"
                )
                details["severity_mismatch"] = {
                    "expected": expected_severity,
                    "actual": actual_severity,
                }
            else:
                details["severity_match"] = True
        
        # Check expected decision for stages if specified
        expected_stages = expected_output.get("expectedStages") or expected_output.get("expected_stages")
        if expected_stages:
            actual_stages = actual_output.get("stages", {})
            for stage_name, expected_stage in expected_stages.items():
                actual_stage = actual_stages.get(stage_name, {})
                expected_decision = expected_stage.get("decision")
                if expected_decision:
                    actual_decision = actual_stage.get("decision")
                    if actual_decision != expected_decision:
                        errors.append(
                            f"Stage '{stage_name}' decision mismatch: expected '{expected_decision}', got '{actual_decision}'"
                        )
                        details[f"stage_{stage_name}_mismatch"] = {
                            "expected": expected_decision,
                            "actual": actual_decision,
                        }
                    else:
                        details[f"stage_{stage_name}_match"] = True
        
        # Check for any other expected fields
        for key, expected_value in expected_output.items():
            if key in ["expectedPlaybookId", "expected_playbook_id", "expectedExceptionType", "expected_exception_type", 
                      "expectedSeverity", "expected_severity", "expectedStages", "expected_stages"]:
                continue  # Already checked
            
            # Try to find in actual output
            actual_value = self._get_nested_value(actual_output, key)
            if actual_value != expected_value:
                errors.append(
                    f"Field '{key}' mismatch: expected '{expected_value}', got '{actual_value}'"
                )
                details[f"{key}_mismatch"] = {
                    "expected": expected_value,
                    "actual": actual_value,
                }
        
        passed = len(errors) == 0
        
        return {
            "passed": passed,
            "error_message": "; ".join(errors) if errors else None,
            "details": details,
        }

    def _get_nested_value(self, data: dict[str, Any], key: str) -> Any:
        """
        Get nested value from dictionary using dot notation.
        
        Args:
            data: Dictionary to search
            key: Key path (e.g., "stages.resolution.decision")
            
        Returns:
            Value at key path or None
        """
        keys = key.split(".")
        value = data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None
            if value is None:
                return None
        return value


# Global test runner instance
_test_runner: Optional[DomainPackTestRunner] = None


def get_test_runner() -> DomainPackTestRunner:
    """
    Get the global test runner instance.
    
    Returns:
        DomainPackTestRunner instance
    """
    global _test_runner
    if _test_runner is None:
        _test_runner = DomainPackTestRunner()
    return _test_runner

