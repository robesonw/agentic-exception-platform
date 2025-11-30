"""
Strict JSON schema validation and sanitization for LLM agent outputs.

Provides:
- validate_llm_output() - Parse JSON and validate against schema
- sanitize_llm_output() - Strip unknown fields, clamp values, ensure required fields
- Fallback JSON parsing for almost-JSON (extra text around JSON)

Matches Phase 3 requirements from phase3-mvp-issues.md P3-5.
"""

import json
import logging
import re
from typing import Any, Optional

from pydantic import ValidationError as PydanticValidationError

from src.llm.schemas import BaseAgentLLMOutput, get_schema_model

logger = logging.getLogger(__name__)


class LLMValidationError(Exception):
    """Raised when LLM output validation fails."""

    def __init__(
        self,
        message: str,
        schema_name: Optional[str] = None,
        error_type: Optional[str] = None,
        raw_text: Optional[str] = None,
        validation_errors: Optional[list[str]] = None,
    ):
        """
        Initialize validation error.
        
        Args:
            message: Error message
            schema_name: Name of schema that failed validation
            error_type: Type of error (e.g., "JSON_PARSE", "SCHEMA_VALIDATION", "SANITIZATION")
            raw_text: Raw text that failed to parse (truncated if too long)
            validation_errors: List of detailed validation error messages
        """
        super().__init__(message)
        self.schema_name = schema_name
        self.error_type = error_type
        self.raw_text = raw_text[:500] if raw_text and len(raw_text) > 500 else raw_text
        self.validation_errors = validation_errors or []


def extract_json_from_text(text: str) -> Optional[str]:
    """
    Attempt to extract JSON block from text that may have extra content.
    
    Heuristic approach:
    1. Try to find JSON object/array boundaries
    2. Look for balanced braces/brackets
    3. Extract the innermost or first complete JSON structure
    
    Args:
        text: Text that may contain JSON with extra content
        
    Returns:
        Extracted JSON string if found, None otherwise
    """
    if not text:
        return None
    
    # Try direct JSON parse first
    try:
        json.loads(text)
        return text
    except (json.JSONDecodeError, ValueError):
        pass
    
    # Look for JSON object boundaries
    # Find first { and try to match with last }
    first_brace = text.find("{")
    if first_brace != -1:
        # Find matching closing brace
        brace_count = 0
        for i in range(first_brace, len(text)):
            if text[i] == "{":
                brace_count += 1
            elif text[i] == "}":
                brace_count -= 1
                if brace_count == 0:
                    # Found complete JSON object
                    json_candidate = text[first_brace : i + 1]
                    try:
                        json.loads(json_candidate)
                        return json_candidate
                    except (json.JSONDecodeError, ValueError):
                        pass
    
    # Look for JSON array boundaries
    first_bracket = text.find("[")
    if first_bracket != -1:
        bracket_count = 0
        for i in range(first_bracket, len(text)):
            if text[i] == "[":
                bracket_count += 1
            elif text[i] == "]":
                bracket_count -= 1
                if bracket_count == 0:
                    json_candidate = text[first_bracket : i + 1]
                    try:
                        json.loads(json_candidate)
                        return json_candidate
                    except (json.JSONDecodeError, ValueError):
                        pass
    
    # Try regex to find JSON-like structures
    # Look for patterns like ```json ... ``` or ``` ... ```
    json_block_pattern = r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```"
    match = re.search(json_block_pattern, text, re.DOTALL)
    if match:
        try:
            json.loads(match.group(1))
            return match.group(1)
        except (json.JSONDecodeError, ValueError):
            pass
    
    return None


def validate_llm_output(schema_name: str, raw_text: str) -> dict[str, Any]:
    """
    Parse JSON from raw text and validate against schema.
    
    Args:
        schema_name: Name of the schema to validate against (e.g., "triage", "policy")
        raw_text: Raw text output from LLM (may contain JSON with extra text)
        
    Returns:
        Parsed and validated dictionary
        
    Raises:
        LLMValidationError: If parsing or validation fails
    """
    if not raw_text or not raw_text.strip():
        raise LLMValidationError(
            message="Empty or whitespace-only raw text",
            schema_name=schema_name,
            error_type="EMPTY_INPUT",
            raw_text=raw_text,
        )
    
    # Try direct JSON parse first
    parsed: Optional[dict[str, Any]] = None
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        # Try fallback extraction
        logger.debug(f"Direct JSON parse failed, attempting fallback extraction: {e}")
        extracted_json = extract_json_from_text(raw_text)
        if extracted_json:
            try:
                parsed = json.loads(extracted_json)
                logger.info(f"Successfully extracted JSON from text using fallback parsing")
            except json.JSONDecodeError as e2:
                raise LLMValidationError(
                    message=f"Failed to parse JSON even after extraction: {e2}",
                    schema_name=schema_name,
                    error_type="JSON_PARSE",
                    raw_text=raw_text,
                    validation_errors=[str(e), str(e2)],
                ) from e2
        else:
            raise LLMValidationError(
                message=f"Failed to parse JSON: {e}",
                schema_name=schema_name,
                error_type="JSON_PARSE",
                raw_text=raw_text,
                validation_errors=[str(e)],
            ) from e
    
    if not isinstance(parsed, dict):
        raise LLMValidationError(
            message=f"Parsed JSON is not a dictionary (got {type(parsed).__name__})",
            schema_name=schema_name,
            error_type="INVALID_TYPE",
            raw_text=raw_text,
        )
    
    # Validate against schema
    try:
        schema_model = get_schema_model(schema_name)
    except ValueError as e:
        # Unknown schema name
        raise LLMValidationError(
            message=f"Unknown schema name: {e}",
            schema_name=schema_name,
            error_type="UNKNOWN_SCHEMA",
            raw_text=raw_text,
        ) from e
    
    # First strip extra fields (but don't apply defaults), then validate
    # This allows validation to catch missing required fields
    schema_json = schema_model.model_json_schema()
    allowed_fields = set(schema_json.get("properties", {}).keys())
    stripped = {k: v for k, v in parsed.items() if k in allowed_fields}
    
    try:
        validated = schema_model.model_validate(stripped)
        return validated.model_dump()
    except PydanticValidationError as e:
        # Schema validation failed
        error_messages = []
        for error in e.errors():
            error_msg = f"{'.'.join(str(loc) for loc in error['loc'])}: {error['msg']}"
            error_messages.append(error_msg)
        
        raise LLMValidationError(
            message=f"Schema validation failed: {e}",
            schema_name=schema_name,
            error_type="SCHEMA_VALIDATION",
            raw_text=raw_text,
            validation_errors=error_messages,
        ) from e


def sanitize_llm_output(schema_name: str, parsed: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize parsed LLM output.
    
    Operations:
    - Strip unknown fields (fields not in schema)
    - Clamp numeric values to safe ranges (confidence scores, etc.)
    - Ensure required fields exist (or apply safe defaults)
    
    Args:
        schema_name: Name of the schema to sanitize against
        parsed: Parsed dictionary (may have extra fields or invalid values)
        
    Returns:
        Sanitized dictionary conforming to schema
    """
    try:
        schema_model = get_schema_model(schema_name)
    except ValueError as e:
        raise LLMValidationError(
            message=f"Unknown schema name for sanitization: {e}",
            schema_name=schema_name,
            error_type="UNKNOWN_SCHEMA",
        ) from e
    
    # Get schema JSON to understand field constraints
    schema_json = schema_model.model_json_schema()
    
    # Create a copy to avoid mutating input
    sanitized = parsed.copy()
    
    # Get allowed fields from schema
    allowed_fields = set(schema_json.get("properties", {}).keys())
    
    # Strip unknown fields
    fields_to_remove = [key for key in sanitized.keys() if key not in allowed_fields]
    if fields_to_remove:
        logger.debug(f"Stripping unknown fields: {fields_to_remove}")
        for field in fields_to_remove:
            sanitized.pop(field, None)
    
    # Clamp numeric values to safe ranges
    # Confidence scores should be between 0.0 and 1.0
    confidence_fields = ["confidence", "severity_confidence", "classification_confidence"]
    for field in confidence_fields:
        if field in sanitized and isinstance(sanitized[field], (int, float)):
            sanitized[field] = max(0.0, min(1.0, float(sanitized[field])))
    
    # Clamp relevance_score if present
    if "evidence_references" in sanitized and isinstance(sanitized["evidence_references"], list):
        for ref in sanitized["evidence_references"]:
            if isinstance(ref, dict) and "relevance_score" in ref:
                if isinstance(ref["relevance_score"], (int, float)):
                    ref["relevance_score"] = max(0.0, min(1.0, float(ref["relevance_score"])))
    
    # Note: We do NOT apply defaults for missing required fields here
    # This allows validation to catch missing required fields properly
    # If defaults are needed, they should be applied in the schema definition
    # or by the LLM provider itself
    
    # Validate the sanitized output
    try:
        validated = schema_model.model_validate(sanitized)
        return validated.model_dump()
    except PydanticValidationError as e:
        # If sanitization still fails, raise error
        error_messages = []
        for error in e.errors():
            error_msg = f"{'.'.join(str(loc) for loc in error['loc'])}: {error['msg']}"
            error_messages.append(error_msg)
        
        raise LLMValidationError(
            message=f"Sanitization failed: {e}",
            schema_name=schema_name,
            error_type="SANITIZATION",
            validation_errors=error_messages,
        ) from e

