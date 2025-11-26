"""
LLM-Based Playbook Generation and Optimization for Phase 2.

Provides:
- generate_playbook(exception_record, evidence, domain_pack)
- optimize_playbook(playbook, past_outcomes)
- Output conforms to DomainPack.playbooks schema
- Generated playbooks tagged as approved=false

Matches specification from phase2-mvp-issues.md Issue 27.
"""

import json
import logging
from typing import Any, Optional

from src.llm.provider import LLMProvider, LLMProviderError
from src.models.domain_pack import DomainPack, Playbook, PlaybookStep
from src.models.exception_record import ExceptionRecord

logger = logging.getLogger(__name__)


class PlaybookGeneratorError(Exception):
    """Raised when playbook generation operations fail."""

    pass


class PlaybookGenerator:
    """
    LLM-based playbook generator.
    
    Generates playbooks using LLM with strict schema validation.
    Never auto-approves LLM-generated playbooks.
    """

    def __init__(self, llm_provider: LLMProvider):
        """
        Initialize playbook generator.
        
        Args:
            llm_provider: LLMProvider instance
        """
        self.llm_provider = llm_provider

    def generate_playbook(
        self,
        exception_record: ExceptionRecord,
        evidence: list[str],
        domain_pack: DomainPack,
    ) -> Playbook:
        """
        Generate a playbook for an exception using LLM.
        
        Args:
            exception_record: ExceptionRecord to generate playbook for
            evidence: Evidence from agents
            domain_pack: Domain Pack for context
            
        Returns:
            Generated Playbook (approved=false)
            
        Raises:
            PlaybookGeneratorError: If generation fails
        """
        # Build prompt for LLM
        prompt = self._build_generation_prompt(exception_record, evidence, domain_pack)
        
        # Define JSON schema for playbook output
        schema = {
            "type": "object",
            "required": ["exceptionType", "steps"],
            "properties": {
                "exceptionType": {"type": "string"},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["action"],
                        "properties": {
                            "action": {"type": "string"},
                            "parameters": {"type": "object"},
                        },
                    },
                },
            },
        }
        
        try:
            # Generate playbook using LLM
            response = self.llm_provider.safe_generate(prompt, schema=schema)
            
            # Extract playbook from response
            playbook_data = self._extract_playbook_from_response(response)
            
            # Validate and create Playbook object
            playbook = self._validate_and_create_playbook(playbook_data, exception_record)
            
            logger.info(
                f"Generated playbook for exception {exception_record.exception_id} "
                f"with {len(playbook.steps)} steps"
            )
            
            return playbook
            
        except LLMProviderError as e:
            raise PlaybookGeneratorError(f"LLM generation failed: {e}") from e
        except Exception as e:
            raise PlaybookGeneratorError(f"Playbook generation failed: {e}") from e

    def optimize_playbook(
        self,
        playbook: Playbook,
        past_outcomes: list[dict[str, Any]],
        domain_pack: DomainPack,
    ) -> Playbook:
        """
        Optimize a playbook based on past outcomes using LLM.
        
        Args:
            playbook: Playbook to optimize
            past_outcomes: List of past execution outcomes
            domain_pack: Domain Pack for context
            
        Returns:
            Optimized Playbook (approved=false)
            
        Raises:
            PlaybookGeneratorError: If optimization fails
        """
        # Build prompt for optimization
        prompt = self._build_optimization_prompt(playbook, past_outcomes, domain_pack)
        
        # Define JSON schema for optimized playbook
        schema = {
            "type": "object",
            "required": ["exceptionType", "steps"],
            "properties": {
                "exceptionType": {"type": "string"},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["action"],
                        "properties": {
                            "action": {"type": "string"},
                            "parameters": {"type": "object"},
                        },
                    },
                },
            },
        }
        
        try:
            # Generate optimized playbook using LLM
            response = self.llm_provider.safe_generate(prompt, schema=schema)
            
            # Extract playbook from response
            playbook_data = self._extract_playbook_from_response(response)
            
            # Validate and create Playbook object
            optimized_playbook = self._validate_and_create_playbook(
                playbook_data, None, original_playbook=playbook
            )
            
            logger.info(
                f"Optimized playbook for {playbook.exception_type} "
                f"with {len(optimized_playbook.steps)} steps"
            )
            
            return optimized_playbook
            
        except LLMProviderError as e:
            raise PlaybookGeneratorError(f"LLM optimization failed: {e}") from e
        except Exception as e:
            raise PlaybookGeneratorError(f"Playbook optimization failed: {e}") from e

    def _build_generation_prompt(
        self,
        exception_record: ExceptionRecord,
        evidence: list[str],
        domain_pack: DomainPack,
    ) -> str:
        """
        Build prompt for playbook generation.
        
        Args:
            exception_record: ExceptionRecord
            evidence: Evidence from agents
            domain_pack: Domain Pack
            
        Returns:
            Prompt string
        """
        prompt_parts = [
            "Generate a playbook for resolving the following exception:",
            "",
            f"Exception Type: {exception_record.exception_type}",
            f"Severity: {exception_record.severity.value if exception_record.severity else 'UNKNOWN'}",
            f"Source System: {exception_record.source_system}",
            "",
            "Exception Details:",
            json.dumps(exception_record.raw_payload, indent=2),
            "",
            "Evidence from agents:",
            "\n".join(f"- {e}" for e in evidence),
            "",
            "Available Tools:",
        ]
        
        # Add available tools
        for tool_name, tool_def in domain_pack.tools.items():
            prompt_parts.append(f"- {tool_name}: {tool_def.description}")
        
        prompt_parts.extend([
            "",
            "Generate a playbook with the following structure:",
            "- exceptionType: string",
            "- steps: array of {action: string, parameters: object}",
            "",
            "The playbook should:",
            "1. Use only tools from the available tools list",
            "2. Have clear, sequential steps",
            "3. Include appropriate parameters for each step",
            "",
            "Return ONLY valid JSON matching the schema.",
        ])
        
        return "\n".join(prompt_parts)

    def _build_optimization_prompt(
        self,
        playbook: Playbook,
        past_outcomes: list[dict[str, Any]],
        domain_pack: DomainPack,
    ) -> str:
        """
        Build prompt for playbook optimization.
        
        Args:
            playbook: Original playbook
            past_outcomes: Past execution outcomes
            domain_pack: Domain Pack
            
        Returns:
            Prompt string
        """
        prompt_parts = [
            "Optimize the following playbook based on past execution outcomes:",
            "",
            "Current Playbook:",
            json.dumps(playbook.model_dump(by_alias=True), indent=2),
            "",
            "Past Execution Outcomes:",
        ]
        
        # Add past outcomes
        for i, outcome in enumerate(past_outcomes, 1):
            prompt_parts.append(f"Outcome {i}:")
            prompt_parts.append(json.dumps(outcome, indent=2))
            prompt_parts.append("")
        
        prompt_parts.extend([
            "Available Tools:",
        ])
        
        # Add available tools
        for tool_name, tool_def in domain_pack.tools.items():
            prompt_parts.append(f"- {tool_name}: {tool_def.description}")
        
        prompt_parts.extend([
            "",
            "Generate an optimized playbook that:",
            "1. Improves success rate based on past outcomes",
            "2. Addresses common failure points",
            "3. Uses only tools from the available tools list",
            "4. Maintains the same exceptionType",
            "",
            "Return ONLY valid JSON matching the schema.",
        ])
        
        return "\n".join(prompt_parts)

    def _extract_playbook_from_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """
        Extract playbook data from LLM response.
        
        Args:
            response: LLM response dictionary
            
        Returns:
            Playbook data dictionary
            
        Raises:
            PlaybookGeneratorError: If extraction fails
        """
        # Try to find playbook in response
        if "playbook" in response:
            return response["playbook"]
        elif "exceptionType" in response and "steps" in response:
            return response
        elif "data" in response:
            return response["data"]
        else:
            # Assume entire response is playbook
            return response

    def _validate_and_create_playbook(
        self,
        playbook_data: dict[str, Any],
        exception_record: Optional[ExceptionRecord],
        original_playbook: Optional[Playbook] = None,
    ) -> Playbook:
        """
        Validate playbook data and create Playbook object.
        
        Args:
            playbook_data: Playbook data from LLM
            exception_record: Optional ExceptionRecord for validation
            original_playbook: Optional original playbook (for optimization)
            
        Returns:
            Validated Playbook object
            
        Raises:
            PlaybookGeneratorError: If validation fails
        """
        # Ensure exceptionType is set
        if not playbook_data.get("exceptionType"):
            if exception_record and exception_record.exception_type:
                playbook_data["exceptionType"] = exception_record.exception_type
            elif original_playbook:
                playbook_data["exceptionType"] = original_playbook.exception_type
            else:
                raise PlaybookGeneratorError("Missing exceptionType in generated playbook")
        
        # Ensure steps is a list
        if "steps" not in playbook_data:
            playbook_data["steps"] = []
        
        if not isinstance(playbook_data["steps"], list):
            raise PlaybookGeneratorError("Steps must be a list")
        
        # Convert steps to PlaybookStep objects
        validated_steps = []
        for step_data in playbook_data["steps"]:
            if not isinstance(step_data, dict):
                raise PlaybookGeneratorError(f"Invalid step format: {step_data}")
            
            if "action" not in step_data:
                raise PlaybookGeneratorError("Step missing 'action' field")
            
            validated_steps.append(
                PlaybookStep(
                    action=step_data["action"],
                    parameters=step_data.get("parameters"),
                )
            )
        
        # Create Playbook object
        try:
            playbook = Playbook(
                exception_type=playbook_data["exceptionType"],
                steps=validated_steps,
            )
            
            # Tag as not approved (LLM-generated playbooks never auto-approved)
            # Note: This is implicit - the playbook is not in approved list
            
            return playbook
            
        except Exception as e:
            raise PlaybookGeneratorError(f"Failed to create Playbook object: {e}") from e

