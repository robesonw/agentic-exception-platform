"""
Tests for Operational Runbooks (P3-27).

Tests runbook loading, suggestion logic, and execution tracking.
"""

import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from src.operations.runbooks import (
    Runbook,
    RunbookExecution,
    RunbookLoader,
    RunbookSuggester,
    RunbookExecutor,
    RunbookStatus,
    RunbookStep,
)
from src.safety.incidents import Incident, IncidentStatus


class TestRunbook:
    """Tests for Runbook model."""

    def test_runbook_creation(self):
        """Test creating a runbook."""
        runbook = Runbook(
            id="rb_001",
            name="Test Runbook",
            description="A test runbook",
            triggers=["error_code_123"],
            steps=[
                {
                    "title": "Step 1",
                    "description": "First step",
                    "action": "check_logs",
                }
            ],
            severity="HIGH",
            owner="ops_team",
            tags=["incident", "error"],
            component="api",
            error_codes=["ERR_001"],
        )
        
        assert runbook.id == "rb_001"
        assert runbook.name == "Test Runbook"
        assert runbook.severity == "HIGH"
        assert len(runbook.tags) == 2

    def test_runbook_get_steps(self):
        """Test converting steps to RunbookStep objects."""
        runbook = Runbook(
            id="rb_001",
            name="Test Runbook",
            description="A test runbook",
            steps=[
                {
                    "title": "Step 1",
                    "description": "First step",
                    "action": "check_logs",
                    "expected_outcome": "Logs show error",
                    "timeout_seconds": 60,
                    "requires_approval": True,
                },
                {
                    "title": "Step 2",
                    "description": "Second step",
                    "action": "restart_service",
                },
            ],
        )
        
        steps = runbook.get_steps()
        assert len(steps) == 2
        assert steps[0].step_number == 1
        assert steps[0].title == "Step 1"
        assert steps[0].requires_approval is True
        assert steps[1].step_number == 2
        assert steps[1].action == "restart_service"


class TestRunbookLoader:
    """Tests for RunbookLoader."""

    def test_load_runbooks_from_yaml(self, tmp_path):
        """Test loading runbooks from YAML files."""
        import yaml
        
        config_dir = tmp_path / "runbooks"
        config_dir.mkdir()
        
        # Create sample runbook YAML
        runbook_file = config_dir / "test_runbook.yaml"
        runbook_data = {
            "id": "rb_test_001",
            "name": "Test Runbook",
            "description": "A test runbook",
            "triggers": ["error_code_123"],
            "steps": [
                {
                    "title": "Step 1",
                    "description": "First step",
                    "action": "check_logs",
                }
            ],
            "severity": "HIGH",
            "owner": "ops_team",
            "tags": ["incident", "error"],
            "component": "api",
            "error_codes": ["ERR_001"],
        }
        
        with open(runbook_file, "w", encoding="utf-8") as f:
            yaml.dump(runbook_data, f)
        
        loader = RunbookLoader(config_dir=str(config_dir))
        
        runbook = loader.get_runbook("rb_test_001")
        assert runbook is not None
        assert runbook.name == "Test Runbook"
        assert runbook.severity == "HIGH"

    def test_load_multiple_runbooks(self, tmp_path):
        """Test loading multiple runbooks."""
        import yaml
        
        config_dir = tmp_path / "runbooks"
        config_dir.mkdir()
        
        # Create multiple runbook files
        for i in range(3):
            runbook_file = config_dir / f"runbook_{i}.yaml"
            runbook_data = {
                "id": f"rb_{i}",
                "name": f"Runbook {i}",
                "description": f"Description {i}",
                "steps": [],
            }
            with open(runbook_file, "w", encoding="utf-8") as f:
                yaml.dump(runbook_data, f)
        
        loader = RunbookLoader(config_dir=str(config_dir))
        
        runbooks = loader.list_runbooks()
        assert len(runbooks) == 3

    def test_load_runbooks_list_format(self, tmp_path):
        """Test loading runbooks in list format."""
        import yaml
        
        config_dir = tmp_path / "runbooks"
        config_dir.mkdir()
        
        runbook_file = config_dir / "runbooks.yaml"
        runbooks_data = [
            {
                "id": "rb_001",
                "name": "Runbook 1",
                "description": "Description 1",
                "steps": [],
            },
            {
                "id": "rb_002",
                "name": "Runbook 2",
                "description": "Description 2",
                "steps": [],
            },
        ]
        
        with open(runbook_file, "w", encoding="utf-8") as f:
            yaml.dump(runbooks_data, f)
        
        loader = RunbookLoader(config_dir=str(config_dir))
        
        runbooks = loader.list_runbooks()
        assert len(runbooks) == 2


class TestRunbookSuggester:
    """Tests for RunbookSuggester."""

    def test_suggest_by_severity(self, tmp_path):
        """Test suggesting runbooks by severity."""
        import yaml
        
        config_dir = tmp_path / "runbooks"
        config_dir.mkdir()
        
        # Create runbooks with different severities
        runbook_file = config_dir / "runbooks.yaml"
        runbooks_data = [
            {
                "id": "rb_high",
                "name": "High Severity Runbook",
                "description": "For high severity incidents",
                "severity": "HIGH",
                "steps": [],
            },
            {
                "id": "rb_medium",
                "name": "Medium Severity Runbook",
                "description": "For medium severity incidents",
                "severity": "MEDIUM",
                "steps": [],
            },
        ]
        
        with open(runbook_file, "w", encoding="utf-8") as f:
            yaml.dump(runbooks_data, f)
        
        loader = RunbookLoader(config_dir=str(config_dir))
        suggester = RunbookSuggester(runbook_loader=loader)
        
        # Suggest for high severity incident
        incident = {"violation_type": "policy"}
        suggested = suggester.suggest_runbooks_for_incident(incident, severity="HIGH")
        
        assert len(suggested) == 1
        assert suggested[0].id == "rb_high"

    def test_suggest_by_component(self, tmp_path):
        """Test suggesting runbooks by component."""
        import yaml
        
        config_dir = tmp_path / "runbooks"
        config_dir.mkdir()
        
        runbook_file = config_dir / "runbooks.yaml"
        runbooks_data = [
            {
                "id": "rb_api",
                "name": "API Runbook",
                "description": "For API incidents",
                "component": "api",
                "steps": [],
            },
            {
                "id": "rb_db",
                "name": "Database Runbook",
                "description": "For database incidents",
                "component": "database",
                "steps": [],
            },
        ]
        
        with open(runbook_file, "w", encoding="utf-8") as f:
            yaml.dump(runbooks_data, f)
        
        loader = RunbookLoader(config_dir=str(config_dir))
        suggester = RunbookSuggester(runbook_loader=loader)
        
        # Suggest for API component
        incident = {"violation_type": "error"}
        suggested = suggester.suggest_runbooks_for_incident(
            incident, component="api", severity="MEDIUM"
        )
        
        assert len(suggested) == 1
        assert suggested[0].id == "rb_api"

    def test_suggest_by_error_code(self, tmp_path):
        """Test suggesting runbooks by error code."""
        import yaml
        
        config_dir = tmp_path / "runbooks"
        config_dir.mkdir()
        
        runbook_file = config_dir / "runbooks.yaml"
        runbooks_data = [
            {
                "id": "rb_err_001",
                "name": "Error 001 Runbook",
                "description": "For ERR_001 errors",
                "error_codes": ["ERR_001"],
                "steps": [],
            },
            {
                "id": "rb_err_002",
                "name": "Error 002 Runbook",
                "description": "For ERR_002 errors",
                "error_codes": ["ERR_002"],
                "steps": [],
            },
        ]
        
        with open(runbook_file, "w", encoding="utf-8") as f:
            yaml.dump(runbooks_data, f)
        
        loader = RunbookLoader(config_dir=str(config_dir))
        suggester = RunbookSuggester(runbook_loader=loader)
        
        # Suggest for ERR_001
        incident = {"violation_type": "error"}
        suggested = suggester.suggest_runbooks_for_incident(
            incident, error_code="ERR_001", severity="MEDIUM"
        )
        
        assert len(suggested) == 1
        assert suggested[0].id == "rb_err_001"

    def test_suggest_by_tags(self, tmp_path):
        """Test suggesting runbooks by tags."""
        import yaml
        
        config_dir = tmp_path / "runbooks"
        config_dir.mkdir()
        
        runbook_file = config_dir / "runbooks.yaml"
        runbooks_data = [
            {
                "id": "rb_incident",
                "name": "Incident Runbook",
                "description": "For incidents",
                "tags": ["incident", "error"],
                "steps": [],
            },
            {
                "id": "rb_maintenance",
                "name": "Maintenance Runbook",
                "description": "For maintenance",
                "tags": ["maintenance"],
                "steps": [],
            },
        ]
        
        with open(runbook_file, "w", encoding="utf-8") as f:
            yaml.dump(runbooks_data, f)
        
        loader = RunbookLoader(config_dir=str(config_dir))
        suggester = RunbookSuggester(runbook_loader=loader)
        
        # Suggest for incident tags
        incident = {"violation_type": "error"}
        suggested = suggester.suggest_runbooks_for_incident(
            incident, tags=["incident", "error"], severity="MEDIUM"
        )
        
        assert len(suggested) == 1
        assert suggested[0].id == "rb_incident"

    def test_suggest_ranking(self, tmp_path):
        """Test that suggestions are ranked by relevance."""
        import yaml
        
        config_dir = tmp_path / "runbooks"
        config_dir.mkdir()
        
        runbook_file = config_dir / "runbooks.yaml"
        runbooks_data = [
            {
                "id": "rb_exact_match",
                "name": "Exact Match",
                "description": "Exact match runbook",
                "component": "api",
                "error_codes": ["ERR_001"],
                "tags": ["incident"],
                "severity": "HIGH",
                "steps": [],
            },
            {
                "id": "rb_partial_match",
                "name": "Partial Match",
                "description": "Partial match runbook",
                "component": "api",
                "severity": "HIGH",
                "steps": [],
            },
        ]
        
        with open(runbook_file, "w", encoding="utf-8") as f:
            yaml.dump(runbooks_data, f)
        
        loader = RunbookLoader(config_dir=str(config_dir))
        suggester = RunbookSuggester(runbook_loader=loader)
        
        # Suggest with multiple matching criteria
        incident = {"violation_type": "error"}
        suggested = suggester.suggest_runbooks_for_incident(
            incident,
            component="api",
            error_code="ERR_001",
            tags=["incident"],
            severity="HIGH",
        )
        
        # Exact match should be first (higher score)
        assert len(suggested) >= 1
        assert suggested[0].id == "rb_exact_match"


class TestRunbookExecutor:
    """Tests for RunbookExecutor."""

    def test_start_execution(self, tmp_path):
        """Test starting a runbook execution."""
        executor = RunbookExecutor(storage_dir=str(tmp_path))
        
        runbook = Runbook(
            id="rb_001",
            name="Test Runbook",
            description="A test runbook",
            steps=[],
        )
        
        execution = executor.start_execution(
            runbook=runbook,
            incident_id="inc_001",
            tenant_id="tenant_001",
            executed_by="ops_team",
        )
        
        assert execution.runbook_id == "rb_001"
        assert execution.incident_id == "inc_001"
        assert execution.status == RunbookStatus.IN_PROGRESS
        assert execution.tenant_id == "tenant_001"
        assert execution.executed_by == "ops_team"

    def test_complete_execution(self, tmp_path):
        """Test completing a runbook execution."""
        executor = RunbookExecutor(storage_dir=str(tmp_path))
        
        runbook = Runbook(
            id="rb_001",
            name="Test Runbook",
            description="A test runbook",
            steps=[],
        )
        
        execution = executor.start_execution(
            runbook=runbook,
            incident_id="inc_001",
        )
        
        success = executor.complete_execution(
            execution_id=execution.id,
            status=RunbookStatus.COMPLETED,
            notes="Execution completed successfully",
        )
        
        assert success is True
        
        # Verify execution was updated
        updated = executor.get_execution(execution.id)
        assert updated is not None
        assert updated.status == RunbookStatus.COMPLETED
        assert updated.notes == "Execution completed successfully"
        assert updated.end_time is not None

    def test_get_executions_for_incident(self, tmp_path):
        """Test getting executions for an incident."""
        executor = RunbookExecutor(storage_dir=str(tmp_path))
        
        runbook = Runbook(
            id="rb_001",
            name="Test Runbook",
            description="A test runbook",
            steps=[],
        )
        
        # Create multiple executions for same incident
        exec1 = executor.start_execution(runbook=runbook, incident_id="inc_001")
        exec2 = executor.start_execution(runbook=runbook, incident_id="inc_001")
        exec3 = executor.start_execution(runbook=runbook, incident_id="inc_002")
        
        # Get executions for inc_001
        executions = executor.get_executions_for_incident("inc_001")
        
        assert len(executions) == 2
        assert exec1.id in [e.id for e in executions]
        assert exec2.id in [e.id for e in executions]
        assert exec3.id not in [e.id for e in executions]

