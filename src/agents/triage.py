"""
TriageAgent implementation for MVP and Phase 3.
Classifies exceptions and assigns severity using domain pack rules.
Phase 3: Enhanced with LLM reasoning and explainability.

Matches specification from:
- docs/04-agent-templates.md
- phase3-mvp-issues.md P3-1
"""

import json
import logging
from typing import Any, Optional

from src.audit.logger import AuditLogger
from src.llm.fallbacks import llm_or_rules
from src.llm.provider import LLMClient
from src.models.agent_contracts import AgentDecision
from src.models.domain_pack import DomainPack, ExceptionTypeDefinition
from src.models.exception_record import ExceptionRecord, Severity
from src.models.tenant_policy import TenantPolicyPack
from src.memory.index import MemoryIndexRegistry
from src.memory.rag import HybridSearchFilters, HybridSearchResult, hybrid_search

logger = logging.getLogger(__name__)


class TriageAgentError(Exception):
    """Raised when TriageAgent operations fail."""

    pass


# Severity priority mapping for comparison
SEVERITY_PRIORITY = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


class TriageAgent:
    """
    TriageAgent classifies exceptions and assigns severity.
    
    Responsibilities:
    - Classify exceptionType using domain pack taxonomy
    - Score severity using severityRules from domain pack
    - Select highest matching severity or use defaultSeverity
    - Produce AgentDecision with classification, severity, next stage = "policy"
    - Log triage decision with AuditLogger
    """

    def __init__(
        self,
        domain_pack: DomainPack,
        audit_logger: Optional[AuditLogger] = None,
        memory_index: Optional[MemoryIndexRegistry] = None,
        llm_client: Optional[LLMClient] = None,
        playbook_matching_service: Optional[Any] = None,
        tenant_policy: Optional[TenantPolicyPack] = None,
    ):
        """
        Initialize TriageAgent.
        
        Args:
            domain_pack: Domain Pack containing exception types and severity rules
            audit_logger: Optional AuditLogger for logging
            memory_index: Optional MemoryIndexRegistry for RAG similarity search
            llm_client: Optional LLMClient for Phase 3 LLM-enhanced reasoning
            playbook_matching_service: Optional PlaybookMatchingService for playbook suggestions (Phase 7)
            tenant_policy: Optional Tenant Policy Pack for custom severity overrides
        """
        self.domain_pack = domain_pack
        self.audit_logger = audit_logger
        self.memory_index = memory_index
        self.llm_client = llm_client
        self.playbook_matching_service = playbook_matching_service
        self.tenant_policy = tenant_policy

    async def process(
        self,
        exception: ExceptionRecord,
        context: Optional[dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Classify exception, score severity, and generate diagnostic summary.
        
        Phase 3: Enhanced with LLM reasoning and explainability.
        Falls back to rule-based logic if LLM unavailable.
        
        Args:
            exception: Normalized ExceptionRecord from IntakeAgent
            context: Optional context from previous agents
            
        Returns:
            AgentDecision with triage results (includes structured reasoning if LLM used)
            
        Raises:
            TriageAgentError: If classification fails
        """
        # Phase 2: Advanced semantic search with hybrid search
        hybrid_search_results = []
        if self.memory_index:
            try:
                # Use hybrid search for better results
                from src.memory.rag import EmbeddingProvider
                
                # Get embedding provider from memory index
                embedding_provider = self.memory_index.embedding_provider
                
                # Perform hybrid search
                hybrid_search_results = hybrid_search(
                    exception_record=exception,
                    memory_index_registry=self.memory_index,
                    embedding_provider=embedding_provider,
                    k=5,
                    filters=None,  # Could add filters based on domain_pack
                )
                
                if hybrid_search_results:
                    logger.debug(
                        f"Found {len(hybrid_search_results)} similar exceptions via hybrid search"
                    )
            except Exception as e:
                # Gracefully handle search failures
                logger.warning(f"Hybrid search failed: {e}")
        
        # Phase 3: Use LLM-enhanced reasoning if available, otherwise fallback to rule-based
        if self.llm_client:
            try:
                # Build prompt with exception, RAG evidence, and rules evidence
                prompt = self.build_triage_prompt(exception, hybrid_search_results)
                
                # Get rule-based classification for fallback
                rule_based_type = self._classify_exception_type(exception)
                rule_based_severity = self._evaluate_severity(exception, rule_based_type)
                matched_rules = self._get_matched_severity_rules(exception, rule_based_type)
                
                # Call LLM with fallback to rule-based logic
                llm_result = llm_or_rules(
                    llm_client=self.llm_client,
                    agent_name="TriageAgent",
                    tenant_id=exception.tenant_id,
                    schema_name="triage",
                    prompt=prompt,
                    rule_based_fn=lambda: self._create_rule_based_triage_result(
                        exception, rule_based_type, rule_based_severity, matched_rules
                    ),
                    audit_logger=self.audit_logger,
                )
                
                # Phase 3: Record RAG evidence (P3-29)
                if hybrid_search_results:
                    try:
                        from src.explainability.evidence_integration import record_rag_evidence
                        
                        evidence_ids = record_rag_evidence(
                            exception_id=exception.exception_id,
                            tenant_id=exception.tenant_id,
                            search_results=hybrid_search_results,
                            agent_name="TriageAgent",
                            stage_name="triage",
                        )
                        logger.debug(f"Recorded {len(evidence_ids)} RAG evidence items for triage")
                    except Exception as e:
                        logger.warning(f"Failed to record RAG evidence: {e}")
                
                # Merge LLM result with rule-based and RAG evidence
                final_type, final_severity, confidence, reasoning = self._merge_triage_results(
                    exception,
                    llm_result,
                    rule_based_type,
                    rule_based_severity,
                    hybrid_search_results,
                    matched_rules,
                )
                
                # Update exception with final classification and severity
                exception.exception_type = final_type
                exception.severity = final_severity
                
                # Phase 7: Suggest playbook via matching service (P7-11)
                suggested_playbook_id = None
                playbook_reasoning = None
                if self.playbook_matching_service:
                    try:
                        from src.models.tenant_policy import TenantPolicyPack
                        # Try to get tenant_policy from context if available
                        tenant_policy = context.get("tenant_policy") if context else None
                        matching_result = await self.playbook_matching_service.match_playbook(
                            tenant_id=exception.tenant_id,
                            exception=exception,
                            tenant_policy=tenant_policy,
                        )
                        if matching_result.playbook:
                            suggested_playbook_id = matching_result.playbook.playbook_id
                            playbook_reasoning = matching_result.reasoning
                            logger.debug(
                                f"TriageAgent suggested playbook {suggested_playbook_id} "
                                f"for exception {exception.exception_id}: {playbook_reasoning}"
                            )
                        else:
                            logger.debug(
                                f"TriageAgent: No playbook match found for exception {exception.exception_id}"
                            )
                    except Exception as e:
                        # Gracefully handle matching service errors - don't fail triage
                        logger.warning(f"Playbook matching failed during triage: {e}")
                        playbook_reasoning = f"Playbook matching error: {str(e)}"
                
                # Create agent decision with structured reasoning
                context_with_search = (context or {}).copy()
                context_with_search["hybrid_search_results"] = hybrid_search_results
                context_with_search["llm_result"] = llm_result
                context_with_search["suggested_playbook_id"] = suggested_playbook_id
                context_with_search["playbook_reasoning"] = playbook_reasoning
                decision = self._create_decision_with_reasoning(
                    exception,
                    final_type,
                    final_severity,
                    confidence,
                    reasoning,
                    context=context_with_search,
                )
                
            except Exception as e:
                logger.warning(f"LLM-enhanced triage failed: {e}, falling back to rule-based")
                # Fall through to rule-based logic
                return await self._process_rule_based(exception, context, hybrid_search_results)
        else:
            # No LLM client, use rule-based logic
            # Phase 3: Record RAG evidence even in rule-based path (P3-29)
            if hybrid_search_results:
                try:
                    from src.explainability.evidence_integration import record_rag_evidence
                    
                    evidence_ids = record_rag_evidence(
                        exception_id=exception.exception_id,
                        tenant_id=exception.tenant_id,
                        search_results=hybrid_search_results,
                        agent_name="TriageAgent",
                        stage_name="triage",
                    )
                    logger.debug(f"Recorded {len(evidence_ids)} RAG evidence items for triage (rule-based)")
                except Exception as e:
                    logger.warning(f"Failed to record RAG evidence: {e}")
            
            return await self._process_rule_based(exception, context, hybrid_search_results)
        
        # Log the event
        if self.audit_logger:
            input_data = {
                "exception": exception.model_dump(),
                "context": context or {},
            }
            self.audit_logger.log_agent_event("TriageAgent", input_data, decision, exception.tenant_id)
        
        return decision

    def _classify_exception_type(self, exception: ExceptionRecord) -> str:
        """
        Classify exception type from domain pack taxonomy.
        
        If exception type is already set, validates it exists in domain pack.
        Otherwise, attempts to infer from raw payload or uses first available type.
        
        Args:
            exception: ExceptionRecord to classify
            
        Returns:
            Classified exception type name
            
        Raises:
            TriageAgentError: If classification fails
        """
        # If exception type is already set, validate it exists
        if exception.exception_type:
            # Allow "Unknown" type if domain pack has no exception types defined
            # or if it's explicitly in the domain pack
            if exception.exception_type == "Unknown" and not self.domain_pack.exception_types:
                logger.warning(
                    f"Exception type is 'Unknown' and domain pack has no exception types defined. "
                    f"Proceeding with 'Unknown' type."
                )
                return "Unknown"
            
            if exception.exception_type in self.domain_pack.exception_types:
                return exception.exception_type
            else:
                # If domain pack has no types defined, allow any type (including Unknown)
                if not self.domain_pack.exception_types:
                    logger.warning(
                        f"Domain pack has no exception types defined. "
                        f"Allowing exception type '{exception.exception_type}'."
                    )
                    return exception.exception_type
                
                raise TriageAgentError(
                    f"Exception type '{exception.exception_type}' not found in domain pack. "
                    f"Valid types: {sorted(self.domain_pack.exception_types.keys())}"
                )
        
        # Try to infer from raw payload
        # Look for common fields that might indicate exception type
        raw_payload = exception.raw_payload
        
        # Check for explicit exception type in payload
        payload_type = raw_payload.get("exceptionType") or raw_payload.get("exception_type")
        if payload_type and payload_type in self.domain_pack.exception_types:
            return payload_type
        
        # Check for error messages or codes that might match exception type descriptions
        error_msg = str(raw_payload.get("error", "")).upper()
        error_code = str(raw_payload.get("errorCode", "")).upper()
        
        # Try to match against exception type names
        for exc_type, exc_def in self.domain_pack.exception_types.items():
            if exc_type.upper() in error_msg or exc_type.upper() in error_code:
                return exc_type
        
        # If no match found, raise error (cannot proceed without classification)
        raise TriageAgentError(
            f"Could not classify exception type. Available types: {sorted(self.domain_pack.exception_types.keys())}"
        )

    def _evaluate_severity(
        self, exception: ExceptionRecord, exception_type: str
    ) -> Severity:
        """
        Evaluate severity using domain pack severity rules, then apply tenant policy overrides.
        
        Process:
        1. Evaluate domain pack severity rules to get base severity
        2. Check tenant policy customSeverityOverrides for matching exception type
        3. If override exists, use override severity; otherwise use domain pack severity
        4. Fall back to inferred severity if no rules match
        
        Args:
            exception: ExceptionRecord to evaluate
            exception_type: Classified exception type
            
        Returns:
            Severity enum value
        """
        matching_severities = []
        
        # Step 1: Evaluate domain pack severity rules
        for rule in self.domain_pack.severity_rules:
            if self._evaluate_rule_condition(rule.condition, exception, exception_type):
                matching_severities.append(rule.severity)
        
        # Select highest severity from matching domain pack rules
        domain_severity = None
        if matching_severities:
            highest = max(matching_severities, key=lambda s: SEVERITY_PRIORITY.get(s.upper(), 0))
            domain_severity = Severity(highest.upper())
        
        # Step 2: Check tenant policy customSeverityOverrides
        logger.debug(f"_evaluate_severity: exception_type={repr(exception_type)}, domain_severity={domain_severity}, has_tenant_policy={self.tenant_policy is not None}")
        if self.tenant_policy and self.tenant_policy.custom_severity_overrides:
            # Normalize exception type for matching (uppercase, no leading colons/spaces)
            normalized_exc_type = exception_type.strip().lstrip(":").strip().upper()
            logger.debug(f"_evaluate_severity: normalized_exc_type={repr(normalized_exc_type)}, num_overrides={len(self.tenant_policy.custom_severity_overrides)}")
            
            for override in self.tenant_policy.custom_severity_overrides:
                # Normalize override exception type for matching
                override_type = override.exception_type.strip().upper()
                logger.debug(f"_evaluate_severity: checking override {repr(override_type)} -> {override.severity} (matches: {override_type == normalized_exc_type})")
                
                if override_type == normalized_exc_type:
                    # Match found - use override severity
                    override_severity = Severity(override.severity.upper())
                    logger.info(
                        f"Applied tenant policy severity override: {exception_type} -> {override.severity} "
                        f"(domain pack would have been: {domain_severity})"
                    )
                    return override_severity
        elif self.tenant_policy is None:
            logger.warning(f"_evaluate_severity: No tenant policy available for severity override check")
        elif not self.tenant_policy.custom_severity_overrides:
            logger.debug(f"_evaluate_severity: Tenant policy exists but has no custom_severity_overrides")
        
        # Step 3: Use domain pack severity if we found one
        if domain_severity:
            return domain_severity
        
        # Step 4: Fall back to inferred severity from exception type name patterns
        exc_type_upper = exception_type.upper()
        if "CRITICAL" in exc_type_upper or "BREAK" in exc_type_upper:
            return Severity.CRITICAL
        elif "HIGH" in exc_type_upper or "FAIL" in exc_type_upper:
            return Severity.HIGH
        elif "LOW" in exc_type_upper or "MISMATCH" in exc_type_upper:
            return Severity.LOW
        
        # Default fallback
        return Severity.MEDIUM

    def _evaluate_rule_condition(
        self, condition: str, exception: ExceptionRecord, exception_type: str
    ) -> bool:
        """
        Evaluate a severity rule condition.
        
        Supports simple conditions like:
        - exceptionType == "SomeType"
        - exceptionType == "SomeType" && rawPayload.field == value
        
        Args:
            condition: Condition string to evaluate (may use "if" format from samples)
            exception: ExceptionRecord to evaluate against
            exception_type: Classified exception type
            
        Returns:
            True if condition matches, False otherwise
        """
        # Handle "if" format from sample files (e.g., "if: exceptionType == 'X'")
        # Extract the actual condition if it starts with "if:"
        if condition.strip().startswith("if:"):
            condition = condition.strip()[3:].strip()
        
        # Simple condition evaluation
        # Handle common patterns from sample files
        
        # Handle simple equality checks with exceptionType
        if "exceptionType" in condition and "==" in condition:
            # Pattern: exceptionType == "SomeType"
            parts = condition.split("==")
            if len(parts) == 2:
                right = parts[1].strip().strip('"').strip("'")
                return exception_type == right
        
        # Handle && (AND) conditions
        if "&&" in condition:
            parts = condition.split("&&")
            return all(self._evaluate_rule_condition(p.strip(), exception, exception_type) for p in parts)
        
        # Handle || (OR) conditions
        if "||" in condition:
            parts = condition.split("||")
            return any(self._evaluate_rule_condition(p.strip(), exception, exception_type) for p in parts)
        
        # Handle rawPayload field access (e.g., rawPayload.impact == 'ECONOMIC')
        if "rawPayload" in condition and "==" in condition:
            # Extract field path and value
            # Pattern: rawPayload.field == value
            if "rawPayload." in condition:
                field_part = condition.split("rawPayload.")[1].split("==")[0].strip()
                value_part = condition.split("==")[1].strip().strip('"').strip("'")
                field_value = exception.raw_payload.get(field_part)
                return str(field_value) == value_part
        
        # Default: try simple string matching
        return exception_type in condition

    def _create_decision(
        self,
        exception: ExceptionRecord,
        exception_type: str,
        severity: Severity,
        context: Optional[dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Create agent decision from triage results.
        
        Args:
            exception: ExceptionRecord with classification and severity
            exception_type: Classified exception type
            severity: Assigned severity
            
        Returns:
            AgentDecision
        """
        # Build evidence list
        evidence = []
        evidence.append(f"Classified as: {exception_type}")
        evidence.append(f"Severity: {severity.value}")
        
        # Add exception type description if available
        exc_type_def = self.domain_pack.exception_types.get(exception_type)
        if exc_type_def:
            evidence.append(f"Description: {exc_type_def.description}")
        
        # Add matched severity rules
        matched_rules = []
        for rule in self.domain_pack.severity_rules:
            if self._evaluate_rule_condition(rule.condition, exception, exception_type):
                matched_rules.append(f"{rule.condition} -> {rule.severity}")
        
        if matched_rules:
            evidence.append(f"Matched severity rules: {len(matched_rules)}")
            evidence.extend(matched_rules)
        else:
            evidence.append("No severity rules matched (using default)")
        
        # Phase 2: Add similar exceptions info from hybrid search
        if context and "hybrid_search_results" in context:
            hybrid_results = context["hybrid_search_results"]
            if hybrid_results:
                evidence.append(f"Found {len(hybrid_results)} similar cases via hybrid search:")
                for i, result in enumerate(hybrid_results[:3], 1):  # Top 3 as evidence
                    evidence.append(
                        f"  {i}. Case {result.exception_id}: "
                        f"score={result.combined_score:.2f} ({result.explanation})"
                    )

        # Phase 7: Add playbook suggestion to evidence (P7-11)
        if context and "suggested_playbook_id" in context:
            suggested_playbook_id = context.get("suggested_playbook_id")
            playbook_reasoning = context.get("playbook_reasoning")
            if suggested_playbook_id:
                evidence.append(f"Suggested playbook: {suggested_playbook_id}")
                if playbook_reasoning:
                    evidence.append(f"Playbook reasoning: {playbook_reasoning}")
            elif playbook_reasoning:
                # Include reasoning even if no playbook matched
                evidence.append(f"Playbook matching: {playbook_reasoning}")

        # Calculate confidence
        # Higher confidence if exception type was already set and severity rules matched
        if exception.exception_type == exception_type and matched_rules:
            confidence = 0.9
        elif matched_rules:
            confidence = 0.85
        elif exception.exception_type == exception_type:
            confidence = 0.8
        else:
            confidence = 0.7  # Lower if we had to infer type

        decision_text = f"Triaged {exception_type} {severity.value}"

        return AgentDecision(
            decision=decision_text,
            confidence=confidence,
            evidence=evidence,
            nextStep="ProceedToPolicy",
        )

    def build_triage_prompt(
        self,
        exception: ExceptionRecord,
        rag_evidence: list[HybridSearchResult],
        rules_evidence: Optional[list[str]] = None,
    ) -> str:
        """
        Build prompt for LLM triage reasoning.
        
        Combines exception details, RAG evidence, and rules evidence into a structured prompt.
        
        Args:
            exception: ExceptionRecord to classify
            rag_evidence: List of HybridSearchResult from RAG similarity search
            rules_evidence: Optional list of matched severity rules
            
        Returns:
            Formatted prompt string for LLM
        """
        prompt_parts = []
        
        # Base prompt from agent template
        prompt_parts.append(
            "You are the TriageAgent. Given the normalized exception and Domain Pack, "
            "classify exceptionType, score severity using severityRules, identify root cause "
            "via RAG query, generate diagnostic summary. Confidence based on match strength."
        )
        
        # Exception details
        prompt_parts.append("\n## Exception Details:")
        prompt_parts.append(f"- Exception ID: {exception.exception_id}")
        prompt_parts.append(f"- Tenant ID: {exception.tenant_id}")
        prompt_parts.append(f"- Source System: {exception.source_system}")
        prompt_parts.append(f"- Timestamp: {exception.timestamp}")
        
        if exception.exception_type:
            prompt_parts.append(f"- Current Exception Type: {exception.exception_type}")
        
        if exception.severity:
            prompt_parts.append(f"- Current Severity: {exception.severity.value}")
        
        # Raw payload summary
        prompt_parts.append("\n## Raw Payload:")
        payload_summary = json.dumps(exception.raw_payload, indent=2)
        if len(payload_summary) > 500:
            payload_summary = payload_summary[:500] + "... (truncated)"
        prompt_parts.append(payload_summary)
        
        # Domain pack context
        prompt_parts.append("\n## Available Exception Types:")
        for exc_type, exc_def in list(self.domain_pack.exception_types.items())[:10]:  # Limit to first 10
            prompt_parts.append(f"- {exc_type}: {exc_def.description}")
        if len(self.domain_pack.exception_types) > 10:
            prompt_parts.append(f"... and {len(self.domain_pack.exception_types) - 10} more types")
        
        # Severity rules
        prompt_parts.append("\n## Severity Rules:")
        for rule in self.domain_pack.severity_rules[:10]:  # Limit to first 10
            prompt_parts.append(f"- {rule.condition} -> {rule.severity}")
        if len(self.domain_pack.severity_rules) > 10:
            prompt_parts.append(f"... and {len(self.domain_pack.severity_rules) - 10} more rules")
        
        # RAG evidence
        if rag_evidence:
            prompt_parts.append("\n## Similar Historical Exceptions (RAG Evidence):")
            for i, result in enumerate(rag_evidence[:5], 1):  # Top 5
                prompt_parts.append(
                    f"{i}. Exception {result.exception_id}: "
                    f"similarity={result.combined_score:.2f} ({result.explanation})"
                )
                if result.metadata:
                    exc_type = result.metadata.get("exception_type", "unknown")
                    severity = result.metadata.get("severity", "unknown")
                    prompt_parts.append(f"   Type: {exc_type}, Severity: {severity}")
        else:
            prompt_parts.append("\n## Similar Historical Exceptions: None found")
        
        # Rules evidence
        if rules_evidence:
            prompt_parts.append("\n## Matched Severity Rules:")
            for rule in rules_evidence:
                prompt_parts.append(f"- {rule}")
        
        # Instructions
        prompt_parts.append(
            "\n## Instructions:"
            "\nAnalyze the exception and provide:"
            "\n1. Predicted exception type (must be one of the available types)"
            "\n2. Predicted severity (LOW, MEDIUM, HIGH, or CRITICAL)"
            "\n3. Confidence scores for both classification and severity"
            "\n4. Root cause hypothesis based on RAG evidence and rules"
            "\n5. List of matched severity rules"
            "\n6. Detailed diagnostic summary"
            "\n7. Structured reasoning steps explaining your decision"
            "\n8. Evidence references (which RAG results and rules influenced the decision)"
        )
        
        return "\n".join(prompt_parts)

    def _get_matched_severity_rules(
        self, exception: ExceptionRecord, exception_type: str
    ) -> list[str]:
        """
        Get list of matched severity rules.
        
        Args:
            exception: ExceptionRecord to evaluate
            exception_type: Classified exception type
            
        Returns:
            List of matched rule descriptions
        """
        matched_rules = []
        for rule in self.domain_pack.severity_rules:
            if self._evaluate_rule_condition(rule.condition, exception, exception_type):
                matched_rules.append(f"{rule.condition} -> {rule.severity}")
        return matched_rules

    def _create_rule_based_triage_result(
        self,
        exception: ExceptionRecord,
        exception_type: str,
        severity: Severity,
        matched_rules: list[str],
    ) -> dict[str, Any]:
        """
        Create rule-based triage result in LLM output format.
        
        This is used as fallback when LLM is unavailable.
        
        Args:
            exception: ExceptionRecord
            exception_type: Classified exception type
            severity: Assigned severity
            matched_rules: List of matched severity rules
            
        Returns:
            Dictionary in TriageLLMOutput format
        """
        # Calculate confidence based on rule matching
        if matched_rules:
            confidence = 0.85
        elif exception.exception_type == exception_type:
            confidence = 0.80
        else:
            confidence = 0.70
        
        return {
            "predicted_exception_type": exception_type,
            "predicted_severity": severity.value,
            "severity_confidence": confidence,
            "classification_confidence": confidence,
            "root_cause_hypothesis": "Rule-based classification (no LLM reasoning available)",
            "matched_rules": matched_rules,
            "diagnostic_summary": f"Exception classified as {exception_type} with {severity.value} severity using rule-based logic.",
            "reasoning_steps": [
                {
                    "step_number": 1,
                    "description": "Classified exception type using domain pack taxonomy",
                    "evidence_used": ["Domain Pack exception types"],
                    "conclusion": f"Exception type: {exception_type}",
                },
                {
                    "step_number": 2,
                    "description": "Evaluated severity using severity rules",
                    "evidence_used": matched_rules if matched_rules else ["Default severity"],
                    "conclusion": f"Severity: {severity.value}",
                },
            ],
            "evidence_references": [
                {
                    "source": "Domain Pack",
                    "description": f"Exception type definition: {exception_type}",
                }
            ],
            "confidence": confidence,
            "natural_language_summary": f"This exception was classified as {exception_type} with {severity.value} severity using rule-based classification.",
        }

    def _merge_triage_results(
        self,
        exception: ExceptionRecord,
        llm_result: dict[str, Any],
        rule_based_type: str,
        rule_based_severity: Severity,
        rag_evidence: list[HybridSearchResult],
        matched_rules: list[str],
    ) -> tuple[str, Severity, float, dict[str, Any]]:
        """
        Merge LLM result with rule-based and RAG evidence.
        
        Combines:
        - LLM predictions (if available and valid)
        - Rule-based classification (as validation/fallback)
        - RAG evidence (for confidence adjustment)
        
        Args:
            exception: ExceptionRecord
            llm_result: LLM output dictionary (may have _metadata if fallback was used)
            rule_based_type: Rule-based classification
            rule_based_severity: Rule-based severity
            rag_evidence: RAG search results
            matched_rules: Matched severity rules
            
        Returns:
            Tuple of (final_type, final_severity, confidence, reasoning_dict)
        """
        # Check if LLM was used or fallback was triggered
        used_llm = not llm_result.get("_metadata", {}).get("llm_fallback", False)
        
        if used_llm:
            # Use LLM predictions, but validate against rules
            llm_type = llm_result.get("predicted_exception_type", rule_based_type)
            llm_severity_str = llm_result.get("predicted_severity", rule_based_severity.value)
            
            # Validate exception type exists in domain pack
            if llm_type not in self.domain_pack.exception_types:
                logger.warning(
                    f"LLM predicted invalid exception type '{llm_type}', "
                    f"using rule-based type '{rule_based_type}'"
                )
                final_type = rule_based_type
            else:
                final_type = llm_type
            
            # Validate severity
            try:
                final_severity = Severity(llm_severity_str.upper())
            except (ValueError, AttributeError):
                logger.warning(
                    f"LLM predicted invalid severity '{llm_severity_str}', "
                    f"using rule-based severity '{rule_based_severity.value}'"
                )
                final_severity = rule_based_severity
            
            # Use LLM confidence, but adjust based on agreement with rules
            llm_confidence = llm_result.get("confidence", 0.7)
            if final_type == rule_based_type and final_severity == rule_based_severity:
                # Agreement increases confidence
                confidence = min(1.0, llm_confidence + 0.1)
            elif final_type == rule_based_type or final_severity == rule_based_severity:
                # Partial agreement
                confidence = llm_confidence
            else:
                # Disagreement decreases confidence
                confidence = max(0.5, llm_confidence - 0.1)
            
            # Extract reasoning from LLM result
            reasoning = {
                "reasoning_steps": llm_result.get("reasoning_steps", []),
                "evidence_references": llm_result.get("evidence_references", []),
                "natural_language_summary": llm_result.get("natural_language_summary", ""),
            }
            
        else:
            # Fallback to rule-based
            final_type = rule_based_type
            final_severity = rule_based_severity
            confidence = 0.75 if matched_rules else 0.65
            
            reasoning = {
                "reasoning_steps": llm_result.get("reasoning_steps", []),
                "evidence_references": llm_result.get("evidence_references", []),
                "natural_language_summary": llm_result.get("natural_language_summary", ""),
            }
        
        return final_type, final_severity, confidence, reasoning

    def _create_decision_with_reasoning(
        self,
        exception: ExceptionRecord,
        exception_type: str,
        severity: Severity,
        confidence: float,
        reasoning: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Create agent decision with structured reasoning from LLM.
        
        Args:
            exception: ExceptionRecord with classification and severity
            exception_type: Classified exception type
            severity: Assigned severity
            confidence: Confidence score
            reasoning: Dictionary with reasoning_steps, evidence_references, natural_language_summary
            context: Optional context (includes hybrid_search_results, llm_result)
            
        Returns:
            AgentDecision with enhanced evidence including reasoning
        """
        # Build evidence list
        evidence = []
        evidence.append(f"Classified as: {exception_type}")
        evidence.append(f"Severity: {severity.value}")
        evidence.append(f"Confidence: {confidence:.2f}")
        
        # Add natural language summary
        if reasoning.get("natural_language_summary"):
            evidence.append(f"Summary: {reasoning['natural_language_summary']}")
        
        # Add exception type description if available
        exc_type_def = self.domain_pack.exception_types.get(exception_type)
        if exc_type_def:
            evidence.append(f"Description: {exc_type_def.description}")
        
        # Add reasoning steps
        if reasoning.get("reasoning_steps"):
            evidence.append("Reasoning steps:")
            for step in reasoning["reasoning_steps"]:
                step_desc = step.get("description", "")
                step_conc = step.get("conclusion", "")
                evidence.append(f"  - {step_desc}")
                if step_conc:
                    evidence.append(f"    Conclusion: {step_conc}")
        
        # Add evidence references
        if reasoning.get("evidence_references"):
            evidence.append("Evidence sources:")
            for ref in reasoning["evidence_references"]:
                source = ref.get("source", "Unknown")
                desc = ref.get("description", "")
                evidence.append(f"  - {source}: {desc}")
        
        # Add RAG evidence
        if context and "hybrid_search_results" in context:
            hybrid_results = context["hybrid_search_results"]
            if hybrid_results:
                evidence.append(f"Found {len(hybrid_results)} similar cases via RAG:")
                for i, result in enumerate(hybrid_results[:3], 1):  # Top 3
                    evidence.append(
                        f"  {i}. Case {result.exception_id}: "
                        f"score={result.combined_score:.2f} ({result.explanation})"
                    )
        
        # Add LLM metadata if available
        if context and "llm_result" in context:
            llm_result = context["llm_result"]
            if llm_result.get("_metadata", {}).get("llm_fallback"):
                evidence.append("Note: Used rule-based fallback (LLM unavailable)")
            else:
                evidence.append("Note: Used LLM-enhanced reasoning")
        
        # Phase 7: Add playbook suggestion to evidence (P7-11)
        if context and "suggested_playbook_id" in context:
            suggested_playbook_id = context.get("suggested_playbook_id")
            playbook_reasoning = context.get("playbook_reasoning")
            if suggested_playbook_id:
                evidence.append(f"Suggested playbook: {suggested_playbook_id}")
                if playbook_reasoning:
                    evidence.append(f"Playbook reasoning: {playbook_reasoning}")
            elif playbook_reasoning:
                # Include reasoning even if no playbook matched
                evidence.append(f"Playbook matching: {playbook_reasoning}")
        
        decision_text = f"Triaged {exception_type} {severity.value}"

        return AgentDecision(
            decision=decision_text,
            confidence=confidence,
            evidence=evidence,
            nextStep="ProceedToPolicy",
        )

    async def _process_rule_based(
        self,
        exception: ExceptionRecord,
        context: Optional[dict[str, Any]],
        hybrid_search_results: list[HybridSearchResult],
    ) -> AgentDecision:
        """
        Process exception using rule-based logic (Phase 1 fallback).
        
        This preserves the original Phase 1 behavior when LLM is unavailable.
        
        Args:
            exception: ExceptionRecord to process
            context: Optional context from previous agents
            hybrid_search_results: RAG search results
            
        Returns:
            AgentDecision with rule-based triage results
        """
        # Classify exception type if not already set
        classified_type = self._classify_exception_type(exception)
        
        # Evaluate severity rules
        severity = self._evaluate_severity(exception, classified_type)
        
        # Update exception with classification and severity
        exception.exception_type = classified_type
        exception.severity = severity
        
        # Phase 7: Suggest playbook via matching service (P7-11)
        suggested_playbook_id = None
        playbook_reasoning = None
        if self.playbook_matching_service:
            try:
                from src.models.tenant_policy import TenantPolicyPack
                # Try to get tenant_policy from context if available
                tenant_policy = context.get("tenant_policy") if context else None
                matching_result = await self.playbook_matching_service.match_playbook(
                    tenant_id=exception.tenant_id,
                    exception=exception,
                    tenant_policy=tenant_policy,
                )
                if matching_result.playbook:
                    suggested_playbook_id = matching_result.playbook.playbook_id
                    playbook_reasoning = matching_result.reasoning
                    logger.debug(
                        f"TriageAgent suggested playbook {suggested_playbook_id} "
                        f"for exception {exception.exception_id}: {playbook_reasoning}"
                    )
                else:
                    # No playbook matched, but still capture reasoning
                    playbook_reasoning = matching_result.reasoning
                    logger.debug(
                        f"TriageAgent: No playbook match found for exception {exception.exception_id}: {playbook_reasoning}"
                    )
            except Exception as e:
                # Gracefully handle matching service errors - don't fail triage
                logger.warning(f"Playbook matching failed during triage: {e}")
                playbook_reasoning = f"Playbook matching error: {str(e)}"
        
        # Create agent decision (pass hybrid_search_results via context)
        context_with_search = (context or {}).copy()
        context_with_search["hybrid_search_results"] = hybrid_search_results
        context_with_search["suggested_playbook_id"] = suggested_playbook_id
        context_with_search["playbook_reasoning"] = playbook_reasoning
        decision = self._create_decision(
            exception, classified_type, severity, context=context_with_search
        )
        
        # Log the event
        if self.audit_logger:
            input_data = {
                "exception": exception.model_dump(),
                "context": context or {},
            }
            self.audit_logger.log_agent_event("TriageAgent", input_data, decision, exception.tenant_id)
        
        return decision
