"""
Pytest configuration and shared fixtures.
"""

import pytest


@pytest.fixture
def sample_tenant_id():
    """Sample tenant ID for testing."""
    return "test_tenant_001"


@pytest.fixture
def sample_exception_id():
    """Sample exception ID for testing."""
    return "exc_001"

