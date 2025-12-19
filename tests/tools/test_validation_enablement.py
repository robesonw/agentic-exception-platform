"""
Unit tests for ToolValidationService enablement checks.

Tests verify that enablement is enforced via repository.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.infrastructure.repositories.tool_definition_repository import ToolDefinitionRepository
from src.infrastructure.repositories.tool_enablement_repository import ToolEnablementRepository
from src.tools.validation import ToolValidationService, ToolValidationError


@pytest.fixture
def mock_tool_repository():
    """Create mock tool repository."""
    repo = MagicMock(spec=ToolDefinitionRepository)
    tool_def = MagicMock()
    tool_def.tool_id = 1
    tool_def.name = "test_tool"
    tool_def.config = {}
    repo.get_tool = AsyncMock(return_value=tool_def)
    return repo


@pytest.fixture
def mock_enablement_repository():
    """Create mock enablement repository."""
    repo = MagicMock(spec=ToolEnablementRepository)
    return repo


@pytest.fixture
def validation_service_with_repo(mock_tool_repository, mock_enablement_repository):
    """Create validation service with enablement repository."""
    return ToolValidationService(mock_tool_repository, mock_enablement_repository)


@pytest.fixture
def validation_service_without_repo(mock_tool_repository):
    """Create validation service without enablement repository (backward compatibility)."""
    return ToolValidationService(mock_tool_repository)


class TestToolValidationServiceEnablement:
    """Tests for tool enablement checking in ToolValidationService."""

    @pytest.mark.asyncio
    async def test_check_tool_enabled_with_repository(
        self, validation_service_with_repo, mock_enablement_repository
    ):
        """Test enablement check using repository."""
        mock_enablement_repository.is_enabled = AsyncMock(return_value=True)
        
        is_enabled = await validation_service_with_repo.check_tool_enabled("TENANT_001", 1)
        
        assert is_enabled is True
        mock_enablement_repository.is_enabled.assert_called_once_with("TENANT_001", 1)

    @pytest.mark.asyncio
    async def test_check_tool_enabled_disabled(
        self, validation_service_with_repo, mock_enablement_repository
    ):
        """Test enablement check when tool is disabled."""
        mock_enablement_repository.is_enabled = AsyncMock(return_value=False)
        
        is_enabled = await validation_service_with_repo.check_tool_enabled("TENANT_001", 1)
        
        assert is_enabled is False

    @pytest.mark.asyncio
    async def test_check_tool_enabled_fallback(
        self, validation_service_without_repo
    ):
        """Test enablement check falls back to in-memory dict when no repository."""
        # Should default to enabled
        is_enabled = await validation_service_without_repo.check_tool_enabled("TENANT_001", 1)
        assert is_enabled is True

    @pytest.mark.asyncio
    async def test_check_tool_enabled_tool_not_found(
        self, validation_service_with_repo, mock_tool_repository
    ):
        """Test enablement check when tool is not found."""
        mock_tool_repository.get_tool = AsyncMock(return_value=None)
        
        is_enabled = await validation_service_with_repo.check_tool_enabled("TENANT_001", 999)
        
        assert is_enabled is False

    @pytest.mark.asyncio
    async def test_check_tool_enabled_invalid_tenant_id(
        self, validation_service_with_repo
    ):
        """Test error when tenant_id is empty."""
        with pytest.raises(ValueError) as exc_info:
            await validation_service_with_repo.check_tool_enabled("", 1)
        
        assert "tenant_id is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_check_tool_enabled_invalid_tool_id(
        self, validation_service_with_repo
    ):
        """Test error when tool_id is invalid."""
        with pytest.raises(ValueError) as exc_info:
            await validation_service_with_repo.check_tool_enabled("TENANT_001", 0)
        
        assert "Invalid tool_id" in str(exc_info.value)








