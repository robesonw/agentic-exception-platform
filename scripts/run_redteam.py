#!/usr/bin/env python3
"""
Red-Team Test Harness CLI Entrypoint (P3-21).

Can be called from CI to run default scenario suite and fail build on critical violations.

Usage:
    python scripts/run_redteam.py [--agent AGENT_NAME] [--severity SEVERITY] [--fail-on-critical]
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.llm.provider import LLMClientFactory, LLMProviderFactory
from src.redteam.harness import RedTeamHarness
from src.redteam.reporting import write_reports
from src.redteam.adversarial_suites import get_adversarial_suite_by_domain
from src.redteam.scenarios import (
    get_default_scenarios,
    get_scenarios_by_agent,
    get_scenarios_by_severity,
)
from src.safety.rules import get_safety_enforcer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for red-team test harness."""
    parser = argparse.ArgumentParser(
        description="Run red-team security tests against LLM system"
    )
    parser.add_argument(
        "--agent",
        type=str,
        help="Filter scenarios by agent name (e.g., TriageAgent)",
    )
    parser.add_argument(
        "--severity",
        type=str,
        choices=["low", "medium", "high", "critical"],
        help="Filter scenarios by severity level",
    )
    parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        help="Exit with non-zero code if any critical scenarios fail",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./runtime/redteam",
        help="Output directory for reports (default: ./runtime/redteam)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="openai",
        choices=["openai", "grok"],
        help="LLM provider to use (default: openai)",
    )
    parser.add_argument(
        "--domain",
        type=str,
        choices=["finance", "healthcare", "all"],
        help="Run domain-specific adversarial suite (finance=FINRA, healthcare=HIPAA, all=both)",
    )
    
    args = parser.parse_args()
    
    # Get scenarios
    scenarios: list = []
    
    if args.domain:
        # Phase 3: Run domain-specific adversarial suite
        scenarios = get_adversarial_suite_by_domain(args.domain)
        logger.info(f"Running {len(scenarios)} adversarial scenarios for domain: {args.domain}")
    elif args.agent:
        scenarios = get_scenarios_by_agent(args.agent)
        logger.info(f"Filtered to {len(scenarios)} scenarios for agent {args.agent}")
    elif args.severity:
        scenarios = get_scenarios_by_severity(args.severity)
        logger.info(f"Filtered to {len(scenarios)} scenarios with severity {args.severity}")
    else:
        scenarios = get_default_scenarios()
        logger.info(f"Running all {len(scenarios)} default scenarios")
    
    if not scenarios:
        logger.warning("No scenarios to run")
        return 0
    
    # Initialize LLM client
    logger.info(f"Initializing LLM provider: {args.provider}")
    llm_client = LLMClientFactory.create_client(provider_type=args.provider)
    
    # Initialize safety enforcer
    safety_enforcer = get_safety_enforcer()
    
    # Create harness
    harness = RedTeamHarness(
        llm_client=llm_client,
        safety_enforcer=safety_enforcer,
        tenant_id="redteam_test",
    )
    
    # Run scenarios
    logger.info("Starting red-team test suite...")
    results = harness.run_suite(scenarios)
    
    # Generate reports
    logger.info("Generating reports...")
    json_file, md_file = write_reports(results, args.output_dir)
    
    logger.info(f"Reports written:")
    logger.info(f"  JSON: {json_file}")
    logger.info(f"  Markdown: {md_file}")
    
    # Check for critical failures
    critical_failures = [
        r for r in results
        if not r.passed and r.metadata.get("severity") == "critical"
    ]
    
    if critical_failures:
        logger.error(f"Found {len(critical_failures)} critical failures:")
        for failure in critical_failures:
            logger.error(f"  - {failure.scenario_name} (ID: {failure.scenario_id})")
            logger.error(f"    Violations: {', '.join(failure.violations)}")
        
        if args.fail_on_critical:
            logger.error("Exiting with error code due to critical failures")
            return 1
    
    # Summary
    passed_count = sum(1 for r in results if r.passed)
    failed_count = len(results) - passed_count
    pass_rate = passed_count / len(results) if results else 0.0
    
    logger.info(f"\nTest Suite Summary:")
    logger.info(f"  Total: {len(results)}")
    logger.info(f"  Passed: {passed_count}")
    logger.info(f"  Failed: {failed_count}")
    logger.info(f"  Pass Rate: {pass_rate:.1%}")
    
    if failed_count > 0:
        logger.warning(f"  Critical Failures: {len(critical_failures)}")
    
    # Return non-zero if any failures and fail-on-critical is set
    if args.fail_on_critical and critical_failures:
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

