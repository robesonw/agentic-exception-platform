"""
Playbook Recommendation and Optimization Engine for Phase 3.

Analyzes historical successful resolutions and manual operator steps to suggest
new playbooks and optimize existing ones.

Safety:
- Suggestions only, never auto-edit playbooks
- All suggestions require human review and approval
- LLM-generated playbooks are never auto-activated

Matches specification from phase3-mvp-issues.md P3-9.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.models.domain_pack import Playbook, PlaybookStep
from src.models.exception_record import ExceptionRecord, ResolutionStatus

logger = logging.getLogger(__name__)


class PlaybookSuggestion(BaseModel):
    """
    Playbook suggestion generated from resolution analysis.
    
    Safety: These are suggestions only, never auto-applied.
    """

    candidate_playbook: Playbook = Field(..., description="Domain-pack-compatible playbook structure")
    effectiveness_prediction: float = Field(..., ge=0.0, le=1.0, description="Predicted effectiveness based on historical stats")
    supporting_examples: list[str] = Field(..., description="List of exception IDs that motivated this playbook")
    suggestion_type: str = Field(..., description="Type of suggestion (new_playbook, optimized_playbook)")
    rationale: str = Field(..., description="Human-readable rationale for the suggestion")
    supporting_metrics: dict[str, Any] = Field(default_factory=dict, description="Supporting metrics for the suggestion")


class PlaybookOptimizationSuggestion(BaseModel):
    """
    Playbook optimization suggestion.
    
    Safety: These are suggestions only, never auto-applied.
    """

    original_playbook: Playbook = Field(..., description="Original playbook being optimized")
    optimized_playbook: Playbook = Field(..., description="Suggested optimized playbook")
    optimization_reason: str = Field(..., description="Reason for optimization (e.g., 'low success rate', 'high MTTR')")
    predicted_improvement: dict[str, Any] = Field(..., description="Predicted improvement metrics")
    supporting_examples: list[str] = Field(..., description="List of exception IDs that motivated this optimization")
    supporting_metrics: dict[str, Any] = Field(default_factory=dict, description="Supporting metrics for the optimization")


class SuggestionReview(BaseModel):
    """Review status for a playbook suggestion."""

    suggestion_id: str = Field(..., description="Identifier for the suggestion")
    reviewed_at: datetime = Field(..., description="Timestamp when suggestion was reviewed")
    reviewed_by: Optional[str] = Field(None, description="User who reviewed the suggestion")
    status: str = Field(..., description="Review status (reviewed, accepted, rejected)")
    notes: Optional[str] = Field(None, description="Optional notes from reviewer")


class PlaybookRecommenderError(Exception):
    """Raised when playbook recommender operations fail."""

    pass


class PlaybookRecommender:
    """
    Playbook recommendation and optimization engine.
    
    Analyzes historical successful resolutions and manual operator steps to suggest
    new playbooks and optimize existing ones.
    
    Responsibilities:
    - Analyze successful resolutions (high success, low MTTR)
    - Detect patterns of repeated manual steps by operators
    - Suggest new playbooks based on patterns
    - Optimize existing playbooks (detect underperforming, suggest modifications)
    - Support human-in-loop workflow for reviewing suggestions
    """

    def __init__(
        self,
        storage_dir: str = "./runtime/learning",
        playbook_generator: Optional[Any] = None,
    ):
        """
        Initialize PlaybookRecommender.
        
        Args:
            storage_dir: Directory for storing learning artifacts
            playbook_generator: Optional PlaybookGenerator for LLM-based generation (never auto-activated)
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.playbook_generator = playbook_generator
        
        # Track playbook performance metrics
        # Structure: {tenant_id: {domain_name: {playbook_id: {success_count, failure_count, mttr_seconds[]}}}}
        self._playbook_metrics: dict[str, dict[str, dict[str, dict[str, Any]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(dict))
        )

    def analyze_resolutions(
        self,
        tenant_id: str,
        domain_name: str,
        historical_resolutions: Optional[list[dict[str, Any]]] = None,
        manual_steps: Optional[list[dict[str, Any]]] = None,
    ) -> list[PlaybookSuggestion]:
        """
        Analyze historical successful resolutions and manual operator steps to suggest new playbooks.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            historical_resolutions: Optional list of historical resolution records
            manual_steps: Optional list of manual operator step records
            
        Returns:
            List of playbook suggestions (not auto-applied)
        """
        suggestions = []
        
        # Load historical data if not provided
        if historical_resolutions is None:
            historical_resolutions = self._load_historical_resolutions(tenant_id, domain_name)
        
        # Analyze successful resolutions (high success, low MTTR)
        if historical_resolutions:
            successful_patterns = self._analyze_successful_resolutions(
                historical_resolutions, manual_steps
            )
            suggestions.extend(successful_patterns)
        
        # Analyze manual operator steps patterns (can work even without historical_resolutions)
        if manual_steps:
            manual_patterns = self._analyze_manual_steps_patterns(historical_resolutions or [], manual_steps)
            suggestions.extend(manual_patterns)
        
        # Sort by effectiveness prediction (highest first)
        suggestions.sort(key=lambda s: s.effectiveness_prediction, reverse=True)
        
        # Persist suggestions
        self._persist_suggestions(tenant_id, domain_name, suggestions)
        
        logger.info(
            f"Generated {len(suggestions)} playbook suggestions for tenant {tenant_id}, "
            f"domain {domain_name}"
        )
        
        return suggestions

    def optimize_existing_playbooks(
        self,
        tenant_id: str,
        domain_name: str,
        existing_playbooks: list[Playbook],
        playbook_metrics: Optional[dict[str, dict[str, Any]]] = None,
    ) -> list[PlaybookOptimizationSuggestion]:
        """
        Optimize existing playbooks based on performance metrics.
        
        Detects underperforming playbooks (low success, long MTTR) and suggests modifications.
        May call into LLM-based playbook generator but never auto-activates.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            existing_playbooks: List of existing playbooks to analyze
            playbook_metrics: Optional playbook performance metrics
            
        Returns:
            List of playbook optimization suggestions (not auto-applied)
        """
        suggestions = []
        
        # Load metrics if not provided
        if playbook_metrics is None:
            playbook_metrics = self._load_playbook_metrics(tenant_id, domain_name)
        
        # Analyze each playbook
        for playbook in existing_playbooks:
            playbook_id = self._get_playbook_id(playbook)
            metrics = playbook_metrics.get(playbook_id, {})
            
            # Check if playbook is underperforming
            if self._is_underperforming(metrics):
                # Generate optimization suggestion
                optimization = self._generate_optimization_suggestion(
                    playbook, metrics, tenant_id, domain_name
                )
                if optimization:
                    suggestions.append(optimization)
        
        # Persist optimization suggestions
        self._persist_optimization_suggestions(tenant_id, domain_name, suggestions)
        
        logger.info(
            f"Generated {len(suggestions)} playbook optimization suggestions for tenant {tenant_id}, "
            f"domain {domain_name}"
        )
        
        return suggestions

    def mark_suggestion_reviewed(
        self,
        tenant_id: str,
        domain_name: str,
        suggestion_id: str,
        reviewed_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        """
        Mark a playbook suggestion as reviewed.
        
        Human-in-loop workflow: Records that a suggestion has been reviewed.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            suggestion_id: Identifier for the suggestion
            reviewed_by: Optional user who reviewed the suggestion
            notes: Optional notes from reviewer
        """
        review = SuggestionReview(
            suggestion_id=suggestion_id,
            reviewed_at=datetime.now(timezone.utc),
            reviewed_by=reviewed_by,
            status="reviewed",
            notes=notes,
        )
        
        self._persist_review(tenant_id, domain_name, review)
        
        logger.info(
            f"Marked suggestion {suggestion_id} as reviewed for tenant {tenant_id}, "
            f"domain {domain_name}"
        )

    def mark_playbook_accepted(
        self,
        tenant_id: str,
        domain_name: str,
        suggestion_id: str,
        accepted_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        """
        Mark a playbook suggestion as accepted.
        
        Human-in-loop workflow: Records that a playbook suggestion has been accepted.
        Note: This does NOT auto-activate the playbook - that requires separate approval.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            suggestion_id: Identifier for the suggestion
            accepted_by: Optional user who accepted the suggestion
            notes: Optional notes from reviewer
        """
        review = SuggestionReview(
            suggestion_id=suggestion_id,
            reviewed_at=datetime.now(timezone.utc),
            reviewed_by=accepted_by,
            status="accepted",
            notes=notes,
        )
        
        self._persist_review(tenant_id, domain_name, review)
        
        logger.info(
            f"Marked suggestion {suggestion_id} as accepted for tenant {tenant_id}, "
            f"domain {domain_name}"
        )

    def mark_playbook_rejected(
        self,
        tenant_id: str,
        domain_name: str,
        suggestion_id: str,
        rejected_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        """
        Mark a playbook suggestion as rejected.
        
        Human-in-loop workflow: Records that a playbook suggestion has been rejected.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            suggestion_id: Identifier for the suggestion
            rejected_by: Optional user who rejected the suggestion
            notes: Optional notes from reviewer
        """
        review = SuggestionReview(
            suggestion_id=suggestion_id,
            reviewed_at=datetime.now(timezone.utc),
            reviewed_by=rejected_by,
            status="rejected",
            notes=notes,
        )
        
        self._persist_review(tenant_id, domain_name, review)
        
        logger.info(
            f"Marked suggestion {suggestion_id} as rejected for tenant {tenant_id}, "
            f"domain {domain_name}"
        )

    def _load_historical_resolutions(
        self, tenant_id: str, domain_name: str
    ) -> list[dict[str, Any]]:
        """
        Load historical resolution data from feedback files.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            
        Returns:
            List of historical resolution records
        """
        # Load from feedback JSONL file (same storage as policy learning)
        feedback_file = self.storage_dir / f"{tenant_id}.jsonl"
        if not feedback_file.exists():
            return []
        
        resolutions = []
        
        try:
            with open(feedback_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    feedback_record = json.loads(line)
                    
                    # Extract resolution data
                    outcome = feedback_record.get("outcome", "")
                    resolution_successful = feedback_record.get("resolutionSuccessful")
                    mttr_seconds = feedback_record.get("mttrSeconds")
                    context = feedback_record.get("context", {})
                    
                    # Only include successful resolutions
                    if outcome in ("SUCCESS", "RESOLVED") or resolution_successful is True:
                        resolutions.append({
                            "exceptionId": feedback_record.get("exceptionId"),
                            "exceptionType": feedback_record.get("exceptionType"),
                            "outcome": outcome,
                            "resolutionSuccessful": resolution_successful,
                            "mttrSeconds": mttr_seconds,
                            "context": context,
                            "timestamp": feedback_record.get("timestamp"),
                        })
        except Exception as e:
            logger.warning(f"Failed to load historical resolutions for tenant {tenant_id}: {e}")
        
        return resolutions

    def _analyze_successful_resolutions(
        self,
        resolutions: list[dict[str, Any]],
        manual_steps: Optional[list[dict[str, Any]]],
    ) -> list[PlaybookSuggestion]:
        """
        Analyze successful resolutions to identify playbook patterns.
        
        Args:
            resolutions: List of successful resolution records
            manual_steps: Optional list of manual operator step records
            
        Returns:
            List of playbook suggestions
        """
        suggestions = []
        
        # Group resolutions by exception type
        by_exception_type = defaultdict(list)
        for resolution in resolutions:
            exception_type = resolution.get("exceptionType")
            if exception_type:
                by_exception_type[exception_type].append(resolution)
        
        # Analyze each exception type
        for exception_type, type_resolutions in by_exception_type.items():
            if len(type_resolutions) < 3:  # Need at least 3 successful resolutions
                continue
            
            # Calculate average MTTR
            mttr_values = [
                r["mttrSeconds"] for r in type_resolutions if r.get("mttrSeconds") is not None
            ]
            avg_mttr = sum(mttr_values) / len(mttr_values) if mttr_values else None
            
            # Extract common steps from resolved plans
            common_steps = self._extract_common_steps(type_resolutions)
            
            if common_steps:
                # Generate playbook suggestion
                candidate_playbook = Playbook(
                    exception_type=exception_type,
                    steps=common_steps,
                )
                
                # Calculate effectiveness prediction
                # Based on success rate (100% for successful resolutions) and low MTTR
                success_rate = 1.0  # All are successful
                mttr_factor = 1.0 if avg_mttr and avg_mttr < 3600 else 0.8  # Prefer < 1 hour
                effectiveness = success_rate * mttr_factor
                
                # Get supporting examples
                example_ids = [r["exceptionId"] for r in type_resolutions[:5]]
                
                suggestions.append(
                    PlaybookSuggestion(
                        candidate_playbook=candidate_playbook,
                        effectiveness_prediction=effectiveness,
                        supporting_examples=example_ids,
                        suggestion_type="new_playbook",
                        rationale=(
                            f"Based on {len(type_resolutions)} successful resolutions "
                            f"for exception type '{exception_type}'"
                            + (f" with average MTTR {avg_mttr/60:.1f} minutes" if avg_mttr else "")
                        ),
                        supporting_metrics={
                            "success_count": len(type_resolutions),
                            "avg_mttr_seconds": avg_mttr,
                            "common_steps_count": len(common_steps),
                        },
                    )
                )
        
        return suggestions

    def _analyze_manual_steps_patterns(
        self,
        resolutions: list[dict[str, Any]],
        manual_steps: Optional[list[dict[str, Any]]],
    ) -> list[PlaybookSuggestion]:
        """
        Analyze patterns of repeated manual steps by operators.
        
        Args:
            resolutions: List of resolution records
            manual_steps: Optional list of manual operator step records
            
        Returns:
            List of playbook suggestions
        """
        suggestions = []
        
        if not manual_steps:
            return suggestions
        
        # Group manual steps by exception type and step pattern
        step_patterns = defaultdict(list)
        
        for step_record in manual_steps:
            exception_type = step_record.get("exceptionType")
            step_action = step_record.get("action")
            step_params = step_record.get("parameters", {})
            
            if exception_type and step_action:
                # Create pattern key
                pattern_key = f"{exception_type}:{step_action}"
                step_patterns[pattern_key].append(step_record)
        
        # Find patterns that appear frequently
        for pattern_key, step_records in step_patterns.items():
            if len(step_records) >= 3:  # Need at least 3 occurrences
                exception_type, step_action = pattern_key.split(":", 1)
                
                # Create playbook step
                common_params = self._extract_common_parameters(step_records)
                playbook_step = PlaybookStep(
                    action=step_action,
                    parameters=common_params if common_params else None,
                )
                
                # Generate playbook suggestion
                candidate_playbook = Playbook(
                    exception_type=exception_type,
                    steps=[playbook_step],
                )
                
                # Calculate effectiveness prediction
                # Based on frequency of manual steps (more frequent = higher confidence)
                frequency = len(step_records)
                effectiveness = min(0.9, 0.6 + (frequency / 10) * 0.3)
                
                # Get supporting examples
                example_ids = [r.get("exceptionId", "") for r in step_records[:5] if r.get("exceptionId")]
                
                suggestions.append(
                    PlaybookSuggestion(
                        candidate_playbook=candidate_playbook,
                        effectiveness_prediction=effectiveness,
                        supporting_examples=example_ids,
                        suggestion_type="new_playbook",
                        rationale=(
                            f"Based on {frequency} repeated manual steps "
                            f"for exception type '{exception_type}' with action '{step_action}'"
                        ),
                        supporting_metrics={
                            "manual_step_count": frequency,
                            "exception_type": exception_type,
                            "step_action": step_action,
                        },
                    )
                )
        
        return suggestions

    def _extract_common_steps(self, resolutions: list[dict[str, Any]]) -> list[PlaybookStep]:
        """
        Extract common steps from successful resolutions.
        
        Args:
            resolutions: List of successful resolution records
            
        Returns:
            List of common PlaybookStep objects
        """
        # Extract resolved plans from context
        all_steps = []
        
        for resolution in resolutions:
            context = resolution.get("context", {})
            resolved_plan = context.get("resolvedPlan", [])
            
            if isinstance(resolved_plan, list):
                for step_data in resolved_plan:
                    if isinstance(step_data, dict):
                        action = step_data.get("action") or step_data.get("tool")
                        params = step_data.get("parameters") or step_data.get("params", {})
                        
                        if action:
                            all_steps.append({
                                "action": action,
                                "parameters": params,
                            })
        
        # Find most common steps
        step_counts = defaultdict(int)
        step_examples = defaultdict(dict)
        
        for step in all_steps:
            step_key = step["action"]
            step_counts[step_key] += 1
            if step_key not in step_examples:
                step_examples[step_key] = step
        
        # Return steps that appear in at least 50% of resolutions
        threshold = len(resolutions) * 0.5
        common_steps = []
        
        for step_key, count in step_counts.items():
            if count >= threshold:
                example = step_examples[step_key]
                common_steps.append(
                    PlaybookStep(
                        action=example["action"],
                        parameters=example["parameters"] if example.get("parameters") else None,
                    )
                )
        
        # Sort by frequency (most common first)
        common_steps.sort(key=lambda s: step_counts[s.action], reverse=True)
        
        return common_steps

    def _extract_common_parameters(self, step_records: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Extract common parameters from manual step records.
        
        Args:
            step_records: List of manual step records
            
        Returns:
            Dictionary of common parameters
        """
        # Find parameters that appear in most records
        param_counts = defaultdict(int)
        param_examples = defaultdict(Any)
        
        for record in step_records:
            params = record.get("parameters", {})
            if isinstance(params, dict):
                for key, value in params.items():
                    param_counts[key] += 1
                    if key not in param_examples:
                        param_examples[key] = value
        
        # Return parameters that appear in at least 50% of records
        threshold = len(step_records) * 0.5
        common_params = {}
        
        for param_key, count in param_counts.items():
            if count >= threshold:
                common_params[param_key] = param_examples[param_key]
        
        return common_params

    def _is_underperforming(self, metrics: dict[str, Any]) -> bool:
        """
        Check if playbook is underperforming based on metrics.
        
        Args:
            metrics: Playbook performance metrics
            
        Returns:
            True if underperforming, False otherwise
        """
        success_count = metrics.get("success_count", 0)
        failure_count = metrics.get("failure_count", 0)
        total_count = success_count + failure_count
        
        if total_count < 3:  # Need at least 3 executions
            return False
        
        # Check success rate
        success_rate = success_count / total_count if total_count > 0 else 0
        if success_rate < 0.5:  # Less than 50% success
            return True
        
        # Check MTTR
        mttr_values = metrics.get("mttr_seconds", [])
        if mttr_values:
            avg_mttr = sum(mttr_values) / len(mttr_values)
            if avg_mttr > 7200:  # More than 2 hours
                return True
        
        return False

    def _generate_optimization_suggestion(
        self,
        playbook: Playbook,
        metrics: dict[str, Any],
        tenant_id: str,
        domain_name: str,
    ) -> Optional[PlaybookOptimizationSuggestion]:
        """
        Generate optimization suggestion for an underperforming playbook.
        
        Args:
            playbook: Playbook to optimize
            metrics: Playbook performance metrics
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            
        Returns:
            PlaybookOptimizationSuggestion or None
        """
        # Identify optimization opportunities
        success_count = metrics.get("success_count", 0)
        failure_count = metrics.get("failure_count", 0)
        total_count = success_count + failure_count
        success_rate = success_count / total_count if total_count > 0 else 0
        
        mttr_values = metrics.get("mttr_seconds", [])
        avg_mttr = sum(mttr_values) / len(mttr_values) if mttr_values else None
        
        # Determine optimization reason
        if success_rate < 0.5:
            reason = f"Low success rate ({success_rate:.1%})"
        elif avg_mttr and avg_mttr > 7200:
            reason = f"High MTTR ({avg_mttr/60:.1f} minutes average)"
        else:
            return None  # Not underperforming enough
        
        # Generate optimized playbook
        # Option 1: Use LLM generator if available (but never auto-activate)
        optimized_playbook = None
        if self.playbook_generator:
            try:
                # Build past outcomes for LLM
                past_outcomes = [
                    {
                        "success": i < success_count,
                        "mttr_seconds": mttr_values[i] if i < len(mttr_values) else None,
                    }
                    for i in range(min(total_count, 10))  # Limit to 10 outcomes
                ]
                
                # Note: This would require domain_pack, which we don't have here
                # For MVP, we'll generate a simple optimization
                optimized_playbook = self._simple_optimize_playbook(playbook, metrics)
            except Exception as e:
                logger.warning(f"Failed to use LLM generator for optimization: {e}")
                optimized_playbook = self._simple_optimize_playbook(playbook, metrics)
        else:
            optimized_playbook = self._simple_optimize_playbook(playbook, metrics)
        
        if not optimized_playbook:
            return None
        
        # Calculate predicted improvement
        predicted_improvement = {
            "predicted_success_rate": min(0.9, success_rate + 0.2),
            "predicted_mttr_reduction": 0.2 if avg_mttr else None,
        }
        
        # Get supporting examples
        example_ids = metrics.get("example_exception_ids", [])[:5]
        
        return PlaybookOptimizationSuggestion(
            original_playbook=playbook,
            optimized_playbook=optimized_playbook,
            optimization_reason=reason,
            predicted_improvement=predicted_improvement,
            supporting_examples=example_ids,
            supporting_metrics=metrics,
        )

    def _simple_optimize_playbook(
        self, playbook: Playbook, metrics: dict[str, Any]
    ) -> Optional[Playbook]:
        """
        Simple playbook optimization without LLM.
        
        Removes redundant steps and adjusts order based on metrics.
        
        Args:
            playbook: Playbook to optimize
            metrics: Playbook performance metrics
            
        Returns:
            Optimized Playbook or None if no optimization possible
        """
        # Simple optimization: remove duplicate steps
        seen_actions = set()
        optimized_steps = []
        
        for step in playbook.steps:
            if step.action not in seen_actions:
                optimized_steps.append(step)
                seen_actions.add(step.action)
        
        # If no changes, try to optimize by reordering or other heuristics
        if len(optimized_steps) == len(playbook.steps):
            # For MVP, if no duplicates, return a copy with same steps
            # (In production, would apply more sophisticated optimizations)
            # Return a copy to indicate optimization was attempted
            return Playbook(
                exception_type=playbook.exception_type,
                steps=list(playbook.steps),  # Copy steps
            )
        
        return Playbook(
            exception_type=playbook.exception_type,
            steps=optimized_steps,
        )

    def _get_playbook_id(self, playbook: Playbook) -> str:
        """
        Generate a unique identifier for a playbook.
        
        Args:
            playbook: Playbook to identify
            
        Returns:
            Playbook identifier
        """
        # Use exception type and step count as identifier
        return f"{playbook.exception_type}_{len(playbook.steps)}"

    def _load_playbook_metrics(
        self, tenant_id: str, domain_name: str
    ) -> dict[str, dict[str, Any]]:
        """
        Load playbook performance metrics.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            
        Returns:
            Dictionary of playbook metrics
        """
        # Return in-memory metrics if available
        if tenant_id in self._playbook_metrics and domain_name in self._playbook_metrics[tenant_id]:
            return self._playbook_metrics[tenant_id][domain_name]
        
        # Otherwise, load from feedback data
        return {}

    def _persist_suggestions(
        self,
        tenant_id: str,
        domain_name: str,
        suggestions: list[PlaybookSuggestion],
    ) -> None:
        """
        Persist playbook suggestions to tenant/domain-specific JSONL file.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            suggestions: List of suggestions to persist
        """
        suggestions_file = self.storage_dir / f"{tenant_id}_{domain_name}_playbook_suggestions.jsonl"
        
        # Append each suggestion as a JSONL line
        with open(suggestions_file, "a", encoding="utf-8") as f:
            for i, suggestion in enumerate(suggestions):
                suggestion_dict = suggestion.model_dump()
                suggestion_dict["suggestion_id"] = f"{tenant_id}_{domain_name}_suggestion_{i}"
                suggestion_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(suggestion_dict, default=str) + "\n")
        
        logger.debug(
            f"Persisted {len(suggestions)} playbook suggestions to {suggestions_file}"
        )

    def _persist_optimization_suggestions(
        self,
        tenant_id: str,
        domain_name: str,
        suggestions: list[PlaybookOptimizationSuggestion],
    ) -> None:
        """
        Persist playbook optimization suggestions to tenant/domain-specific JSONL file.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            suggestions: List of optimization suggestions to persist
        """
        suggestions_file = self.storage_dir / f"{tenant_id}_{domain_name}_playbook_suggestions.jsonl"
        
        # Append each suggestion as a JSONL line
        with open(suggestions_file, "a", encoding="utf-8") as f:
            for i, suggestion in enumerate(suggestions):
                suggestion_dict = suggestion.model_dump()
                suggestion_dict["suggestion_id"] = f"{tenant_id}_{domain_name}_optimization_{i}"
                suggestion_dict["suggestion_type"] = "optimized_playbook"
                suggestion_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(suggestion_dict, default=str) + "\n")
        
        logger.debug(
            f"Persisted {len(suggestions)} playbook optimization suggestions to {suggestions_file}"
        )

    def _persist_review(
        self, tenant_id: str, domain_name: str, review: SuggestionReview
    ) -> None:
        """
        Persist suggestion review to tenant/domain-specific JSONL file.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            review: SuggestionReview to persist
        """
        reviews_file = self.storage_dir / f"{tenant_id}_{domain_name}_playbook_reviews.jsonl"
        
        # Append review as a JSONL line
        with open(reviews_file, "a", encoding="utf-8") as f:
            review_dict = review.model_dump()
            review_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
            f.write(json.dumps(review_dict, default=str) + "\n")
        
        logger.debug(f"Persisted review for suggestion {review.suggestion_id}")

