"""
Red-Team Test Reporting (P3-21).

Generates reports from red-team test results in JSON and Markdown formats.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.redteam.harness import RedTeamResult

logger = logging.getLogger(__name__)


def generate_report(results: list[RedTeamResult]) -> dict[str, Any]:
    """
    Generate a comprehensive report from red-team test results.
    
    Phase 3: Enhanced with domain-specific sections for finance and healthcare.
    
    Args:
        results: List of RedTeamResult instances
        
    Returns:
        Dictionary containing report data
    """
    total_scenarios = len(results)
    passed_count = sum(1 for r in results if r.passed)
    failed_count = total_scenarios - passed_count
    
    # Group by severity
    critical_failures = [
        r for r in results
        if not r.passed and r.metadata.get("severity") == "critical"
    ]
    high_failures = [
        r for r in results
        if not r.passed and r.metadata.get("severity") == "high"
    ]
    medium_failures = [
        r for r in results
        if not r.passed and r.metadata.get("severity") == "medium"
    ]
    low_failures = [
        r for r in results
        if not r.passed and r.metadata.get("severity") == "low"
    ]
    
    # Group by attack type
    by_attack_type: dict[str, list[RedTeamResult]] = {}
    for result in results:
        attack_type = result.metadata.get("attack_type", "unknown")
        if attack_type not in by_attack_type:
            by_attack_type[attack_type] = []
        by_attack_type[attack_type].append(result)
    
    # Calculate pass rates by attack type
    attack_type_stats: dict[str, dict[str, Any]] = {}
    for attack_type, type_results in by_attack_type.items():
        type_passed = sum(1 for r in type_results if r.passed)
        attack_type_stats[attack_type] = {
            "total": len(type_results),
            "passed": type_passed,
            "failed": len(type_results) - type_passed,
            "pass_rate": type_passed / len(type_results) if type_results else 0.0,
        }
    
    # Phase 3: Group by domain
    by_domain: dict[str, list[RedTeamResult]] = {}
    for result in results:
        domain = result.metadata.get("domain", "general")
        if domain not in by_domain:
            by_domain[domain] = []
        by_domain[domain].append(result)
    
    # Calculate domain-specific statistics
    domain_stats: dict[str, dict[str, Any]] = {}
    for domain, domain_results in by_domain.items():
        domain_passed = sum(1 for r in domain_results if r.passed)
        domain_failed = len(domain_results) - domain_passed
        domain_critical = sum(1 for r in domain_results if not r.passed and r.metadata.get("severity") == "critical")
        
        # Extract regulatory violations
        regulatory_violations = [
            r for r in domain_results
            if not r.passed and r.metadata.get("regulation")
        ]
        
        domain_stats[domain] = {
            "total": len(domain_results),
            "passed": domain_passed,
            "failed": domain_failed,
            "pass_rate": domain_passed / len(domain_results) if domain_results else 0.0,
            "critical_failures": domain_critical,
            "regulatory_violations": len(regulatory_violations),
            "regulation": domain_results[0].metadata.get("regulation") if domain_results else None,
        }
    
    # Overall statistics
    pass_rate = passed_count / total_scenarios if total_scenarios > 0 else 0.0
    
    report = {
        "summary": {
            "total_scenarios": total_scenarios,
            "passed": passed_count,
            "failed": failed_count,
            "pass_rate": pass_rate,
            "critical_failures": len(critical_failures),
            "high_failures": len(high_failures),
            "medium_failures": len(medium_failures),
            "low_failures": len(low_failures),
        },
        "by_attack_type": attack_type_stats,
        "by_domain": domain_stats,  # Phase 3: Domain-specific stats
        "critical_failures": [r.to_dict() for r in critical_failures],
        "high_failures": [r.to_dict() for r in high_failures],
        "all_results": [r.to_dict() for r in results],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    return report


def write_json_report(report: dict[str, Any], output_dir: str = "./runtime/redteam") -> Path:
    """
    Write report to JSON file.
    
    Args:
        report: Report dictionary from generate_report()
        output_dir: Output directory for reports
        
    Returns:
        Path to written JSON file
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_file = output_path / f"{timestamp}_report.json"
    
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    
    logger.info(f"Wrote JSON report to {json_file}")
    return json_file


def write_markdown_report(report: dict[str, Any], output_dir: str = "./runtime/redteam") -> Path:
    """
    Write report to Markdown file.
    
    Args:
        report: Report dictionary from generate_report()
        output_dir: Output directory for reports
        
    Returns:
        Path to written Markdown file
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    md_file = output_path / f"{timestamp}_report.md"
    
    summary = report["summary"]
    
    with open(md_file, "w", encoding="utf-8") as f:
        f.write("# Red-Team Test Report\n\n")
        f.write(f"**Generated:** {report['timestamp']}\n\n")
        
        # Summary section
        f.write("## Summary\n\n")
        f.write(f"- **Total Scenarios:** {summary['total_scenarios']}\n")
        f.write(f"- **Passed:** {summary['passed']}\n")
        f.write(f"- **Failed:** {summary['failed']}\n")
        f.write(f"- **Pass Rate:** {summary['pass_rate']:.1%}\n\n")
        
        # Severity breakdown
        f.write("### Failures by Severity\n\n")
        f.write(f"- **Critical:** {summary['critical_failures']}\n")
        f.write(f"- **High:** {summary['high_failures']}\n")
        f.write(f"- **Medium:** {summary['medium_failures']}\n")
        f.write(f"- **Low:** {summary['low_failures']}\n\n")
        
        # Attack type statistics
        f.write("## Statistics by Attack Type\n\n")
        f.write("| Attack Type | Total | Passed | Failed | Pass Rate |\n")
        f.write("|-------------|-------|--------|--------|-----------|\n")
        
        for attack_type, stats in report["by_attack_type"].items():
            f.write(
                f"| {attack_type} | {stats['total']} | {stats['passed']} | "
                f"{stats['failed']} | {stats['pass_rate']:.1%} |\n"
            )
        
        f.write("\n")
        
        # Phase 3: Domain-specific sections
        if "by_domain" in report and report["by_domain"]:
            f.write("## Domain-Specific Results\n\n")
            
            for domain, domain_stats in report["by_domain"].items():
                regulation = domain_stats.get("regulation", "N/A")
                f.write(f"### {domain.capitalize()} Domain ({regulation})\n\n")
                f.write(f"- **Total Scenarios:** {domain_stats['total']}\n")
                f.write(f"- **Passed:** {domain_stats['passed']}\n")
                f.write(f"- **Failed:** {domain_stats['failed']}\n")
                f.write(f"- **Pass Rate:** {domain_stats['pass_rate']:.1%}\n")
                f.write(f"- **Critical Failures:** {domain_stats['critical_failures']}\n")
                f.write(f"- **Regulatory Violations:** {domain_stats['regulatory_violations']}\n\n")
                
                # List regulatory violations for this domain
                domain_results = [
                    r for r in report["all_results"]
                    if r.get("metadata", {}).get("domain") == domain
                ]
                regulatory_failures = [
                    r for r in domain_results
                    if not r["passed"] and r.get("metadata", {}).get("regulation")
                ]
                
                if regulatory_failures:
                    f.write("#### Regulatory Violations\n\n")
                    for failure in regulatory_failures:
                        reg_req = failure.get("metadata", {}).get("regulatory_requirement", "N/A")
                        f.write(f"- **{failure['scenario_name']}** (ID: {failure['scenario_id']})\n")
                        f.write(f"  - Requirement: {reg_req}\n")
                        f.write(f"  - Violations: {', '.join(failure['violations'])}\n\n")
            
            f.write("\n")
        
        # Critical failures
        if report["critical_failures"]:
            f.write("## Critical Failures\n\n")
            for failure in report["critical_failures"]:
                f.write(f"### {failure['scenario_name']} (ID: {failure['scenario_id']})\n\n")
                f.write(f"- **Violations:** {', '.join(failure['violations'])}\n")
                if failure.get("error_message"):
                    f.write(f"- **Error:** {failure['error_message']}\n")
                f.write("\n")
        
        # High failures
        if report["high_failures"]:
            f.write("## High Severity Failures\n\n")
            for failure in report["high_failures"]:
                f.write(f"### {failure['scenario_name']} (ID: {failure['scenario_id']})\n\n")
                f.write(f"- **Violations:** {', '.join(failure['violations'])}\n")
                if failure.get("error_message"):
                    f.write(f"- **Error:** {failure['error_message']}\n")
                f.write("\n")
        
        # All results table
        f.write("## All Results\n\n")
        f.write("| Scenario ID | Name | Passed | Violations | Severity |\n")
        f.write("|-------------|------|--------|------------|----------|\n")
        
        for result in report["all_results"]:
            violations_str = ", ".join(result["violations"][:2])  # Show first 2
            if len(result["violations"]) > 2:
                violations_str += f" (+{len(result['violations']) - 2} more)"
            
            status = "✅" if result["passed"] else "❌"
            severity = result.get("metadata", {}).get("severity", "unknown")
            
            f.write(
                f"| {result['scenario_id']} | {result['scenario_name']} | "
                f"{status} | {violations_str or 'None'} | {severity} |\n"
            )
        
        f.write("\n")
        f.write("---\n")
        f.write(f"*Report generated at {report['timestamp']}*\n")
    
    logger.info(f"Wrote Markdown report to {md_file}")
    return md_file


def write_reports(results: list[RedTeamResult], output_dir: str = "./runtime/redteam") -> tuple[Path, Path]:
    """
    Generate and write both JSON and Markdown reports.
    
    Args:
        results: List of RedTeamResult instances
        output_dir: Output directory for reports
        
    Returns:
        Tuple of (json_file_path, markdown_file_path)
    """
    report = generate_report(results)
    json_file = write_json_report(report, output_dir)
    md_file = write_markdown_report(report, output_dir)
    return json_file, md_file

