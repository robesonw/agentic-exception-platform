"""
Tests for worker configuration (P9-26).

Tests verify:
- Environment-driven worker configuration
- Worker type validation
- Concurrency and group ID configuration
- Stateless worker design
"""

import os
import pytest
from unittest.mock import patch

from src.workers.config import WorkerConfig, get_worker_class_name, SUPPORTED_WORKER_TYPES


class TestWorkerConfig:
    """Tests for WorkerConfig class."""

    def test_from_env_with_all_vars(self):
        """Test loading configuration from environment variables."""
        with patch.dict(
            os.environ,
            {
                "WORKER_TYPE": "intake",
                "CONCURRENCY": "4",
                "GROUP_ID": "intake-workers-1",
            },
        ):
            config = WorkerConfig.from_env()
            assert config.worker_type == "intake"
            assert config.concurrency == 4
            assert config.group_id == "intake-workers-1"

    def test_from_env_with_defaults(self):
        """Test loading configuration with defaults."""
        with patch.dict(
            os.environ,
            {
                "WORKER_TYPE": "triage",
            },
        ):
            config = WorkerConfig.from_env()
            assert config.worker_type == "triage"
            assert config.concurrency == 1  # Default
            assert config.group_id == "triage"  # Defaults to worker_type

    def test_from_env_missing_worker_type(self):
        """Test that missing WORKER_TYPE raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="WORKER_TYPE environment variable is required"):
                WorkerConfig.from_env()

    def test_invalid_concurrency(self):
        """Test that invalid concurrency raises ValueError."""
        with patch.dict(
            os.environ,
            {
                "WORKER_TYPE": "intake",
                "CONCURRENCY": "0",
            },
        ):
            with pytest.raises(ValueError, match="CONCURRENCY must be >= 1"):
                WorkerConfig.from_env()

    def test_negative_concurrency(self):
        """Test that negative concurrency raises ValueError."""
        with patch.dict(
            os.environ,
            {
                "WORKER_TYPE": "intake",
                "CONCURRENCY": "-1",
            },
        ):
            with pytest.raises(ValueError, match="CONCURRENCY must be >= 1"):
                WorkerConfig.from_env()

    def test_explicit_parameters(self):
        """Test creating config with explicit parameters."""
        config = WorkerConfig(
            worker_type="policy",
            concurrency=8,
            group_id="policy-workers-2",
        )
        assert config.worker_type == "policy"
        assert config.concurrency == 8
        assert config.group_id == "policy-workers-2"

    def test_repr(self):
        """Test string representation."""
        config = WorkerConfig(
            worker_type="intake",
            concurrency=4,
            group_id="intake-workers",
        )
        repr_str = repr(config)
        assert "intake" in repr_str
        assert "4" in repr_str
        assert "intake-workers" in repr_str


class TestWorkerClassMapping:
    """Tests for worker class name mapping."""

    def test_get_worker_class_name_valid(self):
        """Test getting worker class name for valid worker types."""
        assert get_worker_class_name("intake") == "IntakeWorker"
        assert get_worker_class_name("triage") == "TriageWorker"
        assert get_worker_class_name("policy") == "PolicyWorker"
        assert get_worker_class_name("playbook") == "PlaybookWorker"
        assert get_worker_class_name("tool") == "ToolWorker"
        assert get_worker_class_name("feedback") == "FeedbackWorker"
        assert get_worker_class_name("sla_monitor") == "SLAMonitorWorker"

    def test_get_worker_class_name_case_insensitive(self):
        """Test that worker type is case-insensitive."""
        assert get_worker_class_name("INTAKE") == "IntakeWorker"
        assert get_worker_class_name("Triage") == "TriageWorker"

    def test_get_worker_class_name_invalid(self):
        """Test that invalid worker type returns None."""
        assert get_worker_class_name("invalid") is None
        assert get_worker_class_name("unknown") is None

    def test_supported_worker_types(self):
        """Test that all supported worker types are defined."""
        assert len(SUPPORTED_WORKER_TYPES) == 7
        assert "intake" in SUPPORTED_WORKER_TYPES
        assert "triage" in SUPPORTED_WORKER_TYPES
        assert "policy" in SUPPORTED_WORKER_TYPES
        assert "playbook" in SUPPORTED_WORKER_TYPES
        assert "tool" in SUPPORTED_WORKER_TYPES
        assert "feedback" in SUPPORTED_WORKER_TYPES
        assert "sla_monitor" in SUPPORTED_WORKER_TYPES


class TestWorkerStatelessness:
    """Tests to verify workers are stateless."""

    def test_worker_config_no_shared_state(self):
        """Test that WorkerConfig instances don't share state."""
        config1 = WorkerConfig(
            worker_type="intake",
            concurrency=2,
            group_id="group-1",
        )
        config2 = WorkerConfig(
            worker_type="triage",
            concurrency=4,
            group_id="group-2",
        )
        
        # Verify they are independent
        assert config1.worker_type != config2.worker_type
        assert config1.concurrency != config2.concurrency
        assert config1.group_id != config2.group_id


