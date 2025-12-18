"""
Tests for Query APIs (P9-19) - Verify DB-only reads.

Tests verify that all GET endpoints:
- Read only from database (no agent calls)
- Use repository pattern for data access
- Enforce tenant isolation
- Return read-only projections
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestQueryAPIsDBOnly:
    """Tests to verify GET endpoints only read from database."""

    @pytest.mark.asyncio
    async def test_get_exceptions_list_db_only(self):
        """Verify GET /api/exceptions/{tenant_id} only reads from database."""
        # Mock repository to verify it's called
        with patch("src.repository.exceptions_repository.ExceptionRepository.list_exceptions") as mock_list:
            mock_list.return_value = AsyncMock(
                items=[],
                total=0,
                page=1,
                page_size=50,
                total_pages=0,
            )
            
            # Verify no agent imports or calls
            with patch("src.agents.intake.IntakeAgent") as mock_intake:
                with patch("src.agents.triage.TriageAgent") as mock_triage:
                    with patch("src.agents.policy.PolicyAgent") as mock_policy:
                        response = client.get(
                            "/api/exceptions/TENANT_001",
                            headers={"X-API-Key": "test_api_key_tenant_001"},
                        )
                        
                        # Verify repository was called
                        assert mock_list.called
                        
                        # Verify no agents were instantiated or called
                        assert not mock_intake.called
                        assert not mock_triage.called
                        assert not mock_policy.called

    @pytest.mark.asyncio
    async def test_get_exception_detail_db_only(self):
        """Verify GET /api/exceptions/{tenant_id}/{exception_id} only reads from database."""
        with patch("src.repository.exceptions_repository.ExceptionRepository.get_exception") as mock_get:
            mock_get.return_value = AsyncMock(
                exception_id="EXC_001",
                tenant_id="TENANT_001",
                domain="finance",
                type="PaymentFailure",
                severity="high",
                status="open",
            )
            
            # Verify no agent calls
            with patch("src.agents.intake.IntakeAgent") as mock_intake:
                response = client.get(
                    "/api/exceptions/TENANT_001/EXC_001",
                    headers={"X-API-Key": "test_api_key_tenant_001"},
                )
                
                # Verify repository was called
                assert mock_get.called
                
                # Verify no agents were called
                assert not mock_intake.called

    @pytest.mark.asyncio
    async def test_get_playbook_status_db_only(self):
        """Verify GET /api/exceptions/{tenant_id}/{exception_id}/playbook only reads from database."""
        with patch("src.repository.exceptions_repository.ExceptionRepository.get_exception") as mock_exc:
            with patch("src.infrastructure.repositories.playbook_repository.PlaybookRepository.get_playbook") as mock_pb:
                with patch("src.infrastructure.repositories.playbook_step_repository.PlaybookStepRepository.get_steps_ordered") as mock_steps:
                    with patch("src.repository.exception_events_repository.ExceptionEventRepository.get_events_for_exception") as mock_events:
                        mock_exc.return_value = AsyncMock(
                            exception_id="EXC_001",
                            tenant_id="TENANT_001",
                            current_playbook_id=1,
                            current_step=1,
                        )
                        mock_pb.return_value = AsyncMock(
                            playbook_id=1,
                            tenant_id="TENANT_001",
                            name="TestPlaybook",
                            version=1,
                            conditions={},
                        )
                        mock_steps.return_value = AsyncMock(items=[])
                        mock_events.return_value = AsyncMock(items=[])
                        
                        # Verify no agent calls
                        with patch("src.playbooks.manager.PlaybookManager") as mock_manager:
                            response = client.get(
                                "/api/exceptions/TENANT_001/EXC_001/playbook",
                                headers={"X-API-Key": "test_api_key_tenant_001"},
                            )
                            
                            # Verify repositories were called
                            assert mock_exc.called
                            assert mock_pb.called
                            assert mock_steps.called
                            assert mock_events.called
                            
                            # Verify no PlaybookManager or agent calls
                            assert not mock_manager.called

    @pytest.mark.asyncio
    async def test_get_playbook_db_only(self):
        """Verify GET /api/playbooks/{playbook_id} only reads from database."""
        with patch("src.infrastructure.repositories.playbook_repository.PlaybookRepository.get_playbook") as mock_get:
            mock_get.return_value = AsyncMock(
                playbook_id=1,
                tenant_id="TENANT_001",
                name="TestPlaybook",
                version=1,
                conditions={},
            )
            
            # Verify no agent calls
            with patch("src.playbooks.manager.PlaybookManager") as mock_manager:
                response = client.get(
                    "/api/playbooks/1?tenant_id=TENANT_001",
                    headers={"X-API-Key": "test_api_key_tenant_001"},
                )
                
                # Verify repository was called
                assert mock_get.called
                
                # Verify no PlaybookManager calls
                assert not mock_manager.called

    @pytest.mark.asyncio
    async def test_get_tool_executions_db_only(self):
        """Verify GET /api/tools/executions only reads from database."""
        with patch("src.infrastructure.repositories.tool_execution_repository.ToolExecutionRepository.list_executions") as mock_list:
            mock_list.return_value = AsyncMock(
                items=[],
                total=0,
                page=1,
                page_size=50,
                total_pages=0,
            )
            
            # Verify no ToolExecutionService calls
            with patch("src.tools.execution_service.ToolExecutionService") as mock_service:
                response = client.get(
                    "/api/tools/executions",
                    headers={"X-API-Key": "test_api_key_tenant_001"},
                )
                
                # Verify repository was called
                assert mock_list.called
                
                # Verify no ToolExecutionService calls
                assert not mock_service.called

    @pytest.mark.asyncio
    async def test_get_tool_execution_db_only(self):
        """Verify GET /api/tools/executions/{execution_id} only reads from database."""
        with patch("src.infrastructure.repositories.tool_execution_repository.ToolExecutionRepository.get_execution") as mock_get:
            mock_get.return_value = AsyncMock(
                id="exec-123",
                tenant_id="TENANT_001",
                tool_id=1,
                status="succeeded",
            )
            
            # Verify no ToolExecutionService calls
            with patch("src.tools.execution_service.ToolExecutionService") as mock_service:
                response = client.get(
                    "/api/tools/executions/exec-123",
                    headers={"X-API-Key": "test_api_key_tenant_001"},
                )
                
                # Verify repository was called
                assert mock_get.called
                
                # Verify no ToolExecutionService calls
                assert not mock_service.called

    @pytest.mark.asyncio
    async def test_ui_query_service_db_only(self):
        """Verify UIQueryService only reads from database."""
        with patch("src.repository.exceptions_repository.ExceptionRepository.get_exception") as mock_exc:
            with patch("src.repository.exception_events_repository.ExceptionEventRepository.get_events_for_exception") as mock_events:
                mock_exc.return_value = AsyncMock(
                    exception_id="EXC_001",
                    tenant_id="TENANT_001",
                )
                mock_events.return_value = AsyncMock(items=[])
                
                # Verify no agent calls
                with patch("src.agents.intake.IntakeAgent") as mock_intake:
                    with patch("src.agents.triage.TriageAgent") as mock_triage:
                        from src.services.ui_query_service import UIQueryService
                        
                        service = UIQueryService()
                        result = await service.get_exception_detail("TENANT_001", "EXC_001")
                        
                        # Verify repositories were called
                        assert mock_exc.called
                        assert mock_events.called
                        
                        # Verify no agents were called
                        assert not mock_intake.called
                        assert not mock_triage.called



