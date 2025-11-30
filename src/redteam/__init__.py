"""
Red-Team Test Harness module for Phase 3.

Provides adversarial testing capabilities for LLM prompts and outputs,
including domain-specific adversarial suites for finance and healthcare.
"""

from src.redteam.adversarial_suites import (
    build_finance_adversarial_suite,
    build_healthcare_adversarial_suite,
    get_adversarial_suite_by_domain,
)
from src.redteam.data_generators import (
    generate_exception_from_dict,
    generate_finance_exception_edge_cases,
    generate_healthcare_exception_edge_cases,
)
from src.redteam.harness import (
    AttackType,
    ExpectedOutcome,
    RedTeamHarness,
    RedTeamResult,
    RedTeamScenario,
)
from src.redteam.reporting import generate_report, write_json_report, write_markdown_report, write_reports
from src.redteam.scenarios import (
    get_default_scenarios,
    get_scenarios_by_agent,
    get_scenarios_by_severity,
)

__all__ = [
    # Core harness
    "AttackType",
    "ExpectedOutcome",
    "RedTeamHarness",
    "RedTeamResult",
    "RedTeamScenario",
    # Reporting
    "generate_report",
    "write_json_report",
    "write_markdown_report",
    "write_reports",
    # Default scenarios
    "get_default_scenarios",
    "get_scenarios_by_agent",
    "get_scenarios_by_severity",
    # Phase 3: Adversarial suites
    "build_finance_adversarial_suite",
    "build_healthcare_adversarial_suite",
    "get_adversarial_suite_by_domain",
    # Phase 3: Data generators
    "generate_exception_from_dict",
    "generate_finance_exception_edge_cases",
    "generate_healthcare_exception_edge_cases",
]

