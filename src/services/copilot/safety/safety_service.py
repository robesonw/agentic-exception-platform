"""
Copilot Safety Service for Phase 13 Intelligence MVP.

This service evaluates and enforces safety constraints for Copilot responses,
ensuring read-only behavior and blocking potentially unsafe actions.

Key responsibilities:
1. Enforce READ_ONLY mode as default safety constraint
2. Detect and block language that implies tool execution or configuration changes
3. Redact sensitive information (API keys, tokens, credentials)
4. Rewrite unsafe responses to be advisory-only
5. Validate tenant policies for additional safety constraints

Phase 13 Prompt 3.6: Safety evaluation with blocker rules and redaction.
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SafetyEvaluation:
    """
    Result of safety evaluation for a Copilot response.
    
    Attributes:
        is_safe: Whether the response meets safety requirements
        mode: Safety mode (always READ_ONLY)
        actions_allowed: List of allowed actions (always empty for read-only)
        modified_answer: Rewritten answer if original was unsafe
        redacted_content: Whether sensitive content was redacted
        violations: List of safety violations detected
        warnings: List of safety warnings (non-blocking)
    """
    is_safe: bool
    mode: str = "READ_ONLY"
    actions_allowed: List[str] = None
    modified_answer: Optional[str] = None
    redacted_content: bool = False
    violations: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.actions_allowed is None:
            self.actions_allowed = []
        if self.violations is None:
            self.violations = []
        if self.warnings is None:
            self.warnings = []


class CopilotSafetyService:
    """
    Service for evaluating and enforcing Copilot response safety.
    
    Ensures all responses maintain read-only behavior and blocks
    potentially unsafe actions or suggestions.
    """
    
    def __init__(self):
        """Initialize the safety service."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Patterns that indicate tool execution or configuration changes
        self.unsafe_action_patterns = [
            r'\b(execute|run|start|stop|restart|kill)\s+(?:this|the|a|an)?\s*(?:command|tool|script|service|fix|patch|update)?',
            r'\b(modify|change|update|edit|delete|create)\s+(?:this|the|a|an)?\s*(?:config|configuration|setting|file|database|record)?',
            r'\b(install|uninstall|deploy|remove)\s+(?:this|the|a|an)?\s*(?:package|software|component|patch)?',
            r'\b(grant|revoke|change)\s+(?:permission|access|role)',
            r'\bdelete\s+(?:this|the|a|an)?\s*(?:record|entry|exception|data|file|corrupted)?',
            r'\bupdate\s+(?:this|the|a|an)?\s*(?:database|record|status|field|config)?',
            r'\bcreate\s+(?:a|an)?\s*(?:user|tenant|policy|rule|account)?',
            r'\b(enable|disable)\s+(?:this|the|a|an)?\s*(?:feature|setting|service)?',
            r'\b(reset|clear)\s+(?:this|the|a|an)?\s*(?:cache|data|configuration)?',
            r'\bapply\s+(?:this|the|a|an)?\s*(?:fix|patch|change|update)?',
        ]
        
        # Patterns for sensitive information that should be redacted
        self.sensitive_patterns = [
            (r'\b[A-Za-z0-9]{15,}\b', '[REDACTED_TOKEN]'),  # Potential API tokens
            (r'\b(?:api[_-]?key|access[_-]?token|secret[_-]?key)[:\s=]\s*[A-Za-z0-9+/=]{8,}', '[REDACTED_API_KEY]'),
            (r'\bpassword[:\s=]\s*\S+', 'password=[REDACTED]'),
            (r'\bclient[_-]?secret[:\s=]\s*[A-Za-z0-9+/=]{8,}', 'client_secret=[REDACTED]'),
            (r'\bbearer\s+[A-Za-z0-9+/=]{12,}', 'Bearer [REDACTED]'),
            (r'\bbasic\s+[A-Za-z0-9+/=]{8,}', 'Basic [REDACTED]'),
        ]
        
        # Advisory language to replace unsafe instructions
        self.advisory_replacements = {
            'execute': 'consider executing',
            'run': 'consider running',
            'modify': 'review and modify',
            'change': 'consider changing',
            'update': 'review and update',
            'delete': 'review for deletion',
            'create': 'consider creating',
            'install': 'consider installing',
            'enable': 'consider enabling',
            'disable': 'consider disabling',
            'apply': 'consider applying',
            'restart': 'consider restarting',
        }

    def evaluate(
        self,
        intent: str,
        response_payload: Dict[str, Any],
        tenant_policy: Optional[Dict[str, Any]] = None
    ) -> SafetyEvaluation:
        """
        Evaluate a Copilot response for safety and apply necessary modifications.
        
        Args:
            intent: User intent (summary, explain, similar, recommend, etc.)
            response_payload: Generated response payload to evaluate
            tenant_policy: Optional tenant-specific safety policies
            
        Returns:
            SafetyEvaluation with safety assessment and modifications
        """
        try:
            self.logger.info(f"Evaluating safety for intent: {intent}")
            
            # Handle invalid/empty response payload
            if not response_payload:
                return SafetyEvaluation(
                    is_safe=False,
                    mode="READ_ONLY",
                    actions_allowed=[],
                    violations=["Invalid or empty response payload"],
                    modified_answer="I cannot provide a safe response to this request."
                )
            
            # Initialize evaluation with safe defaults
            evaluation = SafetyEvaluation(
                is_safe=True,
                mode="READ_ONLY",
                actions_allowed=[]
            )
            
            # Extract answer text for evaluation
            answer = response_payload.get('answer', '')
            
            # Check for unsafe action patterns
            unsafe_actions = self._detect_unsafe_actions(answer)
            if unsafe_actions:
                evaluation.violations.extend(unsafe_actions)
                evaluation.modified_answer = self._rewrite_unsafe_answer(answer)
                evaluation.warnings.append("Response rewritten to be advisory-only")
                evaluation.is_safe = False

            # Apply redaction for sensitive content
            redacted_answer, redacted = self._redact_sensitive_content(
                evaluation.modified_answer or answer
            )
            if redacted:
                evaluation.modified_answer = redacted_answer
                evaluation.redacted_content = True
                evaluation.warnings.append("Sensitive content redacted")
                # Redacted content doesn't make the response unsafe, but it's modified

            # Check bullet points for unsafe actions
            bullets = response_payload.get('bullets', [])
            for i, bullet in enumerate(bullets, 1):
                bullet_unsafe_actions = self._detect_unsafe_actions(bullet)
                if bullet_unsafe_actions:
                    evaluation.warnings.append(f"Bullet {i} contains action-oriented language")

            # Apply tenant-specific policies if provided
            if tenant_policy:
                self._apply_tenant_policies(evaluation, response_payload, tenant_policy)

            # Always ensure READ_ONLY mode
            self._enforce_read_only_mode(evaluation, response_payload)
            
            self.logger.debug(
                f"Safety evaluation complete: safe={evaluation.is_safe}, "
                f"violations={len(evaluation.violations)}, "
                f"redacted={evaluation.redacted_content}"
            )
            
            return evaluation
            
        except Exception as e:
            self.logger.error(f"Error during safety evaluation: {e}")
            # Return safe fallback
            return SafetyEvaluation(
                is_safe=False,
                mode="READ_ONLY",
                actions_allowed=[],
                violations=[f"Safety evaluation error: {str(e)}"],
                modified_answer="I cannot provide a safe response at this time. Please try rephrasing your question."
            )
    
    def _detect_unsafe_actions(self, text: str) -> List[str]:
        """
        Detect patterns in text that suggest unsafe actions.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of detected unsafe action descriptions
        """
        violations = []
        
        for pattern in self.unsafe_action_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                violations.append(f"Unsafe action detected: '{match}'")
        
        return violations
    
    def _rewrite_unsafe_answer(self, answer: str) -> str:
        """
        Rewrite answer to remove unsafe language and make it advisory.
        
        Args:
            answer: Original answer text
            
        Returns:
            Rewritten advisory-only answer
        """
        rewritten = answer
        
        # Replace imperative language with advisory language
        for unsafe_term, advisory_term in self.advisory_replacements.items():
            pattern = r'\b' + re.escape(unsafe_term) + r'\b'
            rewritten = re.sub(pattern, advisory_term, rewritten, flags=re.IGNORECASE)
        
        # Replace common unsafe phrases more comprehensively
        phrase_replacements = {
            r'\b(execute|run)\s+(the|this)?\s*(script|command|tool)': 'consider reviewing the script',
            r'\b(modify|change|edit)\s+(the|this)?\s*(configuration|config|file)': 'consider reviewing the configuration',
            r'\b(delete|remove)\s+(the|this)?\s*(old|corrupted)?\s*(records?|files?|entries?)': 'review for deletion of affected items',
            r'\b(restart|start|stop)\s+(the|this)?\s*(service|process)': 'consider restarting the service',
            r'\b(create|add)\s+(new|a)?\s*(user|account|rule)': 'consider creating the necessary resource',
            r'\b(install|deploy)\s+(the|this)?\s*(patch|update|package)': 'consider installing the appropriate solution'
        }
        
        for pattern, replacement in phrase_replacements.items():
            rewritten = re.sub(pattern, replacement, rewritten, flags=re.IGNORECASE)
        
        # Add advisory disclaimer if not present
        if not any(advisory in rewritten.lower() for advisory in ['consider', 'review', 'advisory', 'recommend']):
            rewritten = f"Advisory guidance: {rewritten}"
        
        # Ensure read-only language is prominent
        if 'read-only' not in rewritten.lower() and 'review' not in rewritten.lower():
            rewritten += " Please review and approve any changes before taking action."
        
        return rewritten
    
    def _redact_sensitive_content(self, text: str) -> Tuple[str, bool]:
        """
        Redact sensitive information from text.
        
        Args:
            text: Text to redact
            
        Returns:
            Tuple of (redacted_text, was_redacted)
        """
        redacted_text = text
        was_redacted = False
        
        for pattern, replacement in self.sensitive_patterns:
            matches = re.findall(pattern, redacted_text, re.IGNORECASE)
            if matches:
                redacted_text = re.sub(pattern, replacement, redacted_text, flags=re.IGNORECASE)
                was_redacted = True
        
        return redacted_text, was_redacted
    
    def _apply_tenant_policies(
        self,
        evaluation: SafetyEvaluation,
        response_payload: Dict[str, Any],
        tenant_policy: Dict[str, Any]
    ) -> None:
        """
        Apply tenant-specific safety policies to the evaluation.
        
        Args:
            evaluation: Current safety evaluation to modify
            response_payload: Response payload being evaluated
            tenant_policy: Tenant-specific safety policies
        """
        # Check for tenant-specific blocked terms
        blocked_terms = tenant_policy.get('blocked_terms', [])
        if blocked_terms:
            answer = evaluation.modified_answer or response_payload.get('answer', '')
            for term in blocked_terms:
                if term.lower() in answer.lower():
                    evaluation.violations.append(f"Blocked term detected: '{term}'")
                    evaluation.modified_answer = answer.replace(term, '[BLOCKED_TERM]')
                    evaluation.is_safe = False
        
        # Check for tenant-specific safety level
        safety_level = tenant_policy.get('safety_level', 'standard')
        if safety_level == 'high':
            # More restrictive safety checks for high-security tenants
            evaluation.warnings.append("High security mode: additional restrictions apply")
        
        # Check for tenant-specific allowed actions (should always be empty for read-only)
        allowed_actions = tenant_policy.get('allowed_actions', [])
        if allowed_actions:
            evaluation.warnings.append("Tenant policy specifies allowed actions, but Copilot remains read-only")
    
    def _enforce_read_only_mode(
        self,
        evaluation: SafetyEvaluation,
        response_payload: Dict[str, Any]
    ) -> None:
        """
        Ensure the response maintains read-only safety constraints.
        
        Args:
            evaluation: Safety evaluation to enforce constraints on
            response_payload: Response payload to validate
        """
        # Always enforce READ_ONLY mode
        evaluation.mode = "READ_ONLY"
        evaluation.actions_allowed = []
        
        # Validate that safety section in response is properly configured
        safety_section = response_payload.get('safety', {})
        if safety_section.get('mode') != 'READ_ONLY':
            evaluation.violations.append("Response safety mode must be READ_ONLY")
            evaluation.is_safe = False
        
        if safety_section.get('actions_allowed', []):
            evaluation.violations.append("Response must not allow any actions in read-only mode")
            evaluation.is_safe = False
    
    def apply_safety_modifications(
        self,
        response_payload: Dict[str, Any],
        evaluation: SafetyEvaluation
    ) -> Dict[str, Any]:
        """
        Apply safety modifications to a response payload.
        
        Args:
            response_payload: Original response payload
            evaluation: Safety evaluation with modifications
            
        Returns:
            Modified response payload with safety constraints applied
        """
        modified_payload = response_payload.copy()
        
        # Apply answer modifications if needed
        if evaluation.modified_answer:
            modified_payload['answer'] = evaluation.modified_answer
        
        # Ensure safety section is properly configured
        modified_payload['safety'] = {
            'mode': evaluation.mode,
            'actions_allowed': evaluation.actions_allowed.copy()
        }
        
        # Add safety metadata if violations or warnings exist
        if evaluation.violations or evaluation.warnings:
            modified_payload['_safety_meta'] = {
                'violations': evaluation.violations.copy(),
                'warnings': evaluation.warnings.copy(),
                'redacted_content': evaluation.redacted_content
            }
        
        return modified_payload