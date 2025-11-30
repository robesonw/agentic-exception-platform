"""
Explanation Quality Scoring (P3-31).

Provides quality heuristics for explanations to enable analytics and quality tracking.
"""

import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def score_explanation(explanation: dict[str, Any] | str) -> float:
    """
    Score explanation quality using simple heuristics.
    
    Quality factors:
    - Length/completeness (longer explanations generally better, but not too verbose)
    - Presence of evidence references
    - Avoidance of "I don't know" or filler text
    - Structured reasoning presence
    
    Args:
        explanation: Explanation dict (for JSON/structured) or string (for text)
        
    Returns:
        Quality score between 0.0 and 1.0
    """
    score = 0.0
    
    if isinstance(explanation, str):
        # Text format scoring
        text = explanation.lower()
        
        # Length factor (optimal range: 200-2000 chars)
        length = len(explanation)
        if 200 <= length <= 2000:
            score += 0.3
        elif 100 <= length < 200:
            score += 0.2
        elif 2000 < length <= 5000:
            score += 0.25
        else:
            score += 0.1
        
        # Evidence references
        evidence_indicators = ["evidence", "similar", "rag", "tool", "policy", "rule", "guardrail"]
        evidence_count = sum(1 for indicator in evidence_indicators if indicator in text)
        if evidence_count >= 3:
            score += 0.3
        elif evidence_count >= 2:
            score += 0.2
        elif evidence_count >= 1:
            score += 0.1
        
        # Avoid filler text
        filler_phrases = [
            "i don't know",
            "i'm not sure",
            "unable to determine",
            "cannot explain",
            "no information available",
        ]
        has_filler = any(phrase in text for phrase in filler_phrases)
        if not has_filler:
            score += 0.2
        else:
            score -= 0.2  # Penalty for filler
        
        # Reasoning indicators
        reasoning_indicators = ["because", "reason", "based on", "due to", "therefore", "conclusion"]
        reasoning_count = sum(1 for indicator in reasoning_indicators if indicator in text)
        if reasoning_count >= 2:
            score += 0.2
        elif reasoning_count >= 1:
            score += 0.1
        
    elif isinstance(explanation, dict):
        # JSON/structured format scoring
        # Timeline presence
        if "timeline" in explanation:
            timeline = explanation["timeline"]
            if isinstance(timeline, dict) and timeline.get("events"):
                events_count = len(timeline.get("events", []))
                if events_count >= 3:
                    score += 0.3
                elif events_count >= 2:
                    score += 0.2
                elif events_count >= 1:
                    score += 0.1
        
        # Evidence items presence
        if "evidence_items" in explanation:
            evidence_items = explanation["evidence_items"]
            if isinstance(evidence_items, list):
                if len(evidence_items) >= 3:
                    score += 0.3
                elif len(evidence_items) >= 2:
                    score += 0.2
                elif len(evidence_items) >= 1:
                    score += 0.1
        
        # Agent decisions presence
        if "agent_decisions" in explanation:
            decisions = explanation["agent_decisions"]
            if isinstance(decisions, dict) and decisions:
                decision_count = len(decisions)
                if decision_count >= 3:
                    score += 0.2
                elif decision_count >= 2:
                    score += 0.15
                elif decision_count >= 1:
                    score += 0.1
        
        # Evidence links presence
        if "evidence_links" in explanation:
            links = explanation["evidence_links"]
            if isinstance(links, list) and links:
                score += 0.2
        
        # Structured format bonus
        if "evidence" in explanation and isinstance(explanation["evidence"], dict):
            if "by_type" in explanation["evidence"]:
                score += 0.1
            if "links_by_agent" in explanation["evidence"]:
                score += 0.1
    
    # Clamp score to [0.0, 1.0]
    score = max(0.0, min(1.0, score))
    
    return score


def generate_explanation_hash(explanation: dict[str, Any] | str) -> str:
    """
    Generate a hash for an explanation for tracking purposes.
    
    Args:
        explanation: Explanation dict or string
        
    Returns:
        SHA256 hash as hex string
    """
    if isinstance(explanation, dict):
        # Sort keys for consistent hashing
        import json
        explanation_str = json.dumps(explanation, sort_keys=True)
    else:
        explanation_str = str(explanation)
    
    return hashlib.sha256(explanation_str.encode("utf-8")).hexdigest()

