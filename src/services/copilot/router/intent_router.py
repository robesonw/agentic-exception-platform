"""
Intent Detection Router for Copilot

Provides lightweight heuristic-based intent classification for user messages.
Designed to be deterministic and fast without requiring external LLM calls.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Pattern
import re
from datetime import datetime, timedelta


class IntentType(Enum):
    """Supported intent types for Copilot queries."""
    SUMMARY = "summary"
    EXPLAIN = "explain" 
    SIMILAR_CASES = "similar_cases"
    RECOMMEND_PLAYBOOK = "recommend_playbook"
    DRAFT_RESPONSE = "draft_response"
    WORKFLOW_VIEW = "workflow_view"
    OTHER = "other"


@dataclass
class IntentResult:
    """Result of intent detection with confidence and extracted parameters."""
    intent_type: IntentType
    confidence: float  # 0.0 to 1.0
    extracted_params: Dict[str, Any]
    raw_message: str
    processing_metadata: Dict[str, Any]


class IntentDetectionRouter:
    """
    Routes user messages to appropriate intent types using deterministic heuristics.
    
    Uses keyword matching, pattern recognition, and contextual clues to classify
    user intents without requiring external LLM calls for MVP implementation.
    """

    def __init__(self):
        """Initialize the intent detection router with pattern matchers."""
        self._intent_patterns = self._build_intent_patterns()
        self._exception_id_pattern = re.compile(r'\b(EX-[\w-]+|\d{4}-\d{4,})\b', re.IGNORECASE)
        self._date_patterns = {
            'today': re.compile(r'\btoday\b', re.IGNORECASE),
            'yesterday': re.compile(r'\byesterday\b', re.IGNORECASE),
            'this_week': re.compile(r'\bthis\s+week\b', re.IGNORECASE),
            'last_week': re.compile(r'\blast\s+week\b', re.IGNORECASE),
            'this_month': re.compile(r'\bthis\s+month\b', re.IGNORECASE),
            'last_24h': re.compile(r'\blast\s+24\s+hours?\b', re.IGNORECASE),
            'specific_date': re.compile(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b')
        }
        self._severity_patterns = re.compile(r'\b(critical|high|medium|low|severe|urgent)\b', re.IGNORECASE)
        
    def _build_intent_patterns(self) -> Dict[IntentType, List[Pattern]]:
        """Build regex patterns for each intent type."""
        return {
            IntentType.SUMMARY: [
                re.compile(r'\b(summarize?|summary|overview|status|report)\b', re.IGNORECASE),
                re.compile(r'\bshow\s+me\s+(today\'?s?|recent|latest|all)\s+(exceptions?|errors?|issues?)\b', re.IGNORECASE),
                re.compile(r'\bwhat\'?s\s+(happening|going\s+on|the\s+status)\b', re.IGNORECASE),
                re.compile(r'\b(dashboard|trends?|metrics?)\b', re.IGNORECASE),
            ],
            IntentType.EXPLAIN: [
                re.compile(r'\b(why|explain|tell\s+me\s+why|how\s+come)\b', re.IGNORECASE),
                re.compile(r'\bwhat\s+(caused|triggered|happened)\b', re.IGNORECASE),
                re.compile(r'\b(reason|explanation|details?|breakdown)\b', re.IGNORECASE),
                re.compile(r'\b(classified|categorized|tagged)\s+(as|with)\b', re.IGNORECASE),
            ],
            IntentType.SIMILAR_CASES: [
                re.compile(r'\b(similar|alike|comparable|related)\b', re.IGNORECASE),
                re.compile(r'\bfind\s+(similar|related|comparable)\b', re.IGNORECASE),
                re.compile(r'\b(cases?|exceptions?|issues?)\s+like\b', re.IGNORECASE),
                re.compile(r'\bother\s+(cases?|exceptions?|instances?)\b', re.IGNORECASE),
                re.compile(r'\bhas\s+this\s+happened\s+before\b', re.IGNORECASE),
            ],
            IntentType.RECOMMEND_PLAYBOOK: [
                re.compile(r'\b(recommend|suggest|propose)\s+(playbook|runbook|procedure|steps?)\b', re.IGNORECASE),
                re.compile(r'\bwhat\s+(should|do)\s+I\s+(do|follow|run)\b', re.IGNORECASE),
                re.compile(r'\b(playbook|runbook|procedure|checklist|guide)\b', re.IGNORECASE),
                re.compile(r'\b(how\s+to\s+)?(fix|resolve|handle|address|remediate)\b', re.IGNORECASE),
                re.compile(r'\bnext\s+steps?\b', re.IGNORECASE),
            ],
            IntentType.DRAFT_RESPONSE: [
                re.compile(r'\b(draft|write|compose|generate|create)\s+(response|email|message|reply|notification|template)\b', re.IGNORECASE),
                re.compile(r'\bhelp\s+me\s+(write|respond|reply|draft)\b', re.IGNORECASE),
                re.compile(r'\b(template|message|notification|reply)\s+(for|to|about)\b', re.IGNORECASE),
                re.compile(r'\bwhat\s+(should|can)\s+I\s+(say|write|tell)\b', re.IGNORECASE),
                re.compile(r'\bcustomer\s+(notification|response|message|email)\b', re.IGNORECASE),
                re.compile(r'\bcompose\s+(a\s+)?(reply|response|message)\b', re.IGNORECASE),
                re.compile(r'\bgenerate\s+(message|template|notification)\b', re.IGNORECASE),
            ],
            IntentType.WORKFLOW_VIEW: [
                re.compile(r'\b(workflow|process|flow|pipeline)\b', re.IGNORECASE),
                re.compile(r'\bshow\s+(me\s+)?(workflow|process|steps?)\b', re.IGNORECASE),
                re.compile(r'\bhow\s+does\s+this\s+(work|flow|process)\b', re.IGNORECASE),
                re.compile(r'\b(sequence|order|progression)\b', re.IGNORECASE),
            ]
        }

    def detect_intent(
        self,
        message: str,
        exception_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        domain: Optional[str] = None
    ) -> IntentResult:
        """
        Detect the intent of a user message using heuristic analysis.
        
        Args:
            message: User's natural language message
            exception_id: Optional context exception ID
            tenant_id: Optional tenant context
            domain: Optional domain context
            
        Returns:
            IntentResult with detected intent, confidence, and extracted parameters
        """
        message_normalized = message.strip().lower()
        
        # Extract parameters from message
        extracted_params = self._extract_parameters(message, exception_id, tenant_id, domain)
        
        # Score each intent type
        intent_scores = {}
        processing_details = {}
        
        for intent_type, patterns in self._intent_patterns.items():
            score, details = self._calculate_intent_score(message_normalized, patterns)
            intent_scores[intent_type] = score
            processing_details[intent_type.value] = details
            
        # Apply contextual boosts
        self._apply_contextual_boosts(intent_scores, extracted_params, message_normalized)
        
        # Extract date ranges for summary intents (auto-boost)
        date_detected = False
        for date_key, pattern in self._date_patterns.items():
            if pattern.search(message):
                if intent_scores.get(IntentType.SUMMARY, 0) > 0:
                    extracted_params['date_range'] = date_key
                    intent_scores[IntentType.SUMMARY] += 0.2
                    date_detected = True
                    break
        
        # Auto-extract severity for summary requests with critical keywords
        if any(word in message.lower() for word in ['critical', 'high', 'severe', 'urgent']) and intent_scores.get(IntentType.SUMMARY, 0) > 0:
            if 'severity_filters' not in extracted_params:
                severity_matches = self._severity_patterns.findall(message)
                if severity_matches:
                    extracted_params['severity_filters'] = [s.lower() for s in severity_matches]
        
        # Add fallback parameters for summary intents when no explicit ones found 
        if intent_scores.get(IntentType.SUMMARY, 0) > 0.5:  # High confidence summary
            if 'date_range' not in extracted_params and 'severity_filters' not in extracted_params:
                # Look for implicit time references
                if any(word in message.lower() for word in ['recent', 'latest', 'current', 'new', 'status']):
                    extracted_params['date_range'] = 'recent'  # Implicit recent timeframe
                elif any(word in message.lower() for word in ['all', 'total', 'complete']):
                    extracted_params['date_range'] = 'all'
        
        # Determine best match
        best_intent = max(intent_scores.items(), key=lambda x: x[1]) if intent_scores else (IntentType.OTHER, 0.0)
        intent_type, confidence = best_intent
        
        # Fallback to OTHER if confidence too low
        if confidence < 0.3:
            intent_type = IntentType.OTHER
            confidence = 0.3  # Lower confidence for OTHER
        
        # Include OTHER intent in scores for completeness
        all_scores = {k.value: v for k, v in intent_scores.items()}
        if 'other' not in all_scores:
            all_scores['other'] = 0.3 if intent_type == IntentType.OTHER else 0.0
            
        return IntentResult(
            intent_type=intent_type,
            confidence=min(confidence, 1.0),
            extracted_params=extracted_params,
            raw_message=message,
            processing_metadata={
                'scores': all_scores,
                'pattern_matches': processing_details,
                'contextual_boosts_applied': True
            }
        )

    def _extract_parameters(
        self,
        message: str,
        exception_id: Optional[str],
        tenant_id: Optional[str],
        domain: Optional[str]
    ) -> Dict[str, Any]:
        """Extract structured parameters from the message and context."""
        params = {
            'exception_id': exception_id,
            'tenant_id': tenant_id,
            'domain': domain,
        }
        
        # Extract exception IDs from message
        exception_matches = self._exception_id_pattern.findall(message)
        if exception_matches:
            params['mentioned_exceptions'] = exception_matches
            if not exception_id:
                params['exception_id'] = exception_matches[0]
        
        # Extract date/time references
        date_info = self._extract_date_range(message)
        if date_info:
            params.update(date_info)
            
        # Extract severity filters
        severity_matches = self._severity_patterns.findall(message)
        if severity_matches:
            params['severity_filters'] = [s.lower() for s in severity_matches]
            
        # Extract count/limit requests
        count_match = re.search(r'\b(\d+)\s+(latest|recent|last|top|first)\b', message, re.IGNORECASE)
        if count_match:
            params['limit'] = int(count_match.group(1))
        elif re.search(r'\btop\s+(\d+)\b', message, re.IGNORECASE):
            params['limit'] = int(re.search(r'\btop\s+(\d+)\b', message, re.IGNORECASE).group(1))
            
        return {k: v for k, v in params.items() if v is not None}

    def _extract_date_range(self, message: str) -> Optional[Dict[str, Any]]:
        """Extract date range information from message."""
        now = datetime.now()
        
        if self._date_patterns['today'].search(message):
            return {
                'date_range': 'today',
                'start_date': now.replace(hour=0, minute=0, second=0, microsecond=0),
                'end_date': now
            }
        elif self._date_patterns['yesterday'].search(message):
            yesterday = now - timedelta(days=1)
            return {
                'date_range': 'yesterday',
                'start_date': yesterday.replace(hour=0, minute=0, second=0, microsecond=0),
                'end_date': yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
            }
        elif self._date_patterns['this_week'].search(message):
            week_start = now - timedelta(days=now.weekday())
            return {
                'date_range': 'this_week',
                'start_date': week_start.replace(hour=0, minute=0, second=0, microsecond=0),
                'end_date': now
            }
        elif self._date_patterns['last_24h'].search(message):
            return {
                'date_range': 'last_24h',
                'start_date': now - timedelta(hours=24),
                'end_date': now
            }
        
        # Check for specific dates
        specific_date = self._date_patterns['specific_date'].search(message)
        if specific_date:
            try:
                date_str = specific_date.group(0)
                if '/' in date_str:
                    parsed_date = datetime.strptime(date_str, '%m/%d/%Y')
                else:
                    parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
                return {
                    'date_range': 'specific',
                    'start_date': parsed_date.replace(hour=0, minute=0, second=0, microsecond=0),
                    'end_date': parsed_date.replace(hour=23, minute=59, second=59, microsecond=999999),
                    'specific_date': date_str
                }
            except ValueError:
                pass
                
        return None

    def _calculate_intent_score(
        self,
        message: str,
        patterns: List[Pattern]
    ) -> tuple[float, Dict[str, Any]]:
        """Calculate confidence score for an intent based on pattern matches."""
        matches = []
        total_score = 0.0
        
        for pattern in patterns:
            match = pattern.search(message)
            if match:
                matches.append({
                    'pattern': pattern.pattern,
                    'match': match.group(0),
                    'start': match.start(),
                    'end': match.end()
                })
                # Score based on match strength and position
                match_length = len(match.group(0))
                message_length = len(message)
                match_score = (match_length / message_length) * 2.0  # Base score
                
                # Boost score if match is early in message
                position_boost = 1.2 if match.start() == 0 else 1.0
                
                # Add fixed bonus for each match
                pattern_bonus = 0.6
                
                total_score += (match_score + pattern_bonus) * position_boost
        
        details = {
            'pattern_matches': matches,
            'match_count': len(matches),
            'raw_score': total_score
        }
        
        # Normalize and boost confidence
        if matches:
            # Multiple matches increase confidence significantly
            multi_match_bonus = min(len(matches) * 0.3, 0.8)
            confidence = min(total_score + multi_match_bonus, 1.0)
            # Ensure minimum threshold for matches
            confidence = max(confidence, 0.5)
        else:
            confidence = 0.0
        
        return confidence, details

    def _apply_contextual_boosts(
        self,
        intent_scores: Dict[IntentType, float],
        extracted_params: Dict[str, Any],
        message_normalized: str
    ) -> None:
        """Apply contextual boosts to intent scores based on extracted parameters."""
        
        # Boost EXPLAIN if asking about specific exception
        if extracted_params.get('exception_id') or extracted_params.get('mentioned_exceptions'):
            if 'why' in message_normalized or 'explain' in message_normalized:
                intent_scores[IntentType.EXPLAIN] += 0.4
            if 'similar' in message_normalized:
                intent_scores[IntentType.SIMILAR_CASES] += 0.4
                
        # Boost SUMMARY if asking about time ranges
        if extracted_params.get('date_range'):
            if any(word in message_normalized for word in ['summary', 'summarize', 'overview', 'status']):
                intent_scores[IntentType.SUMMARY] += 0.4
                
        # Boost SIMILAR_CASES if specific exception mentioned
        if extracted_params.get('exception_id'):
            if any(word in message_normalized for word in ['similar', 'like', 'related', 'comparable']):
                intent_scores[IntentType.SIMILAR_CASES] += 0.5
                
        # Boost RECOMMEND_PLAYBOOK if asking for help/fix
        if any(word in message_normalized for word in ['fix', 'resolve', 'handle', 'help']):
            intent_scores[IntentType.RECOMMEND_PLAYBOOK] += 0.3
            
        # Boost DRAFT_RESPONSE if mention communication
        if any(word in message_normalized for word in ['email', 'message', 'customer', 'user', 'client']):
            intent_scores[IntentType.DRAFT_RESPONSE] += 0.3
        
        # Boost WORKFLOW_VIEW for process requests
        if any(word in message_normalized for word in ['process', 'workflow', 'steps', 'flow']):
            intent_scores[IntentType.WORKFLOW_VIEW] += 0.4
        
        # Prioritization for complex messages - first strong keyword wins
        words = message_normalized.split()
        first_keywords = {
            'explain': IntentType.EXPLAIN,
            'why': IntentType.EXPLAIN, 
            'find': IntentType.SIMILAR_CASES,
            'similar': IntentType.SIMILAR_CASES,
            'summarize': IntentType.SUMMARY,
            'recommend': IntentType.RECOMMEND_PLAYBOOK,
            'draft': IntentType.DRAFT_RESPONSE
        }
        
        # Strong boost for opening words  
        for i, word in enumerate(words[:5]):  # Check first 5 words
            if word in first_keywords:
                target_intent = first_keywords[word]
                if intent_scores.get(target_intent, 0) > 0:
                    boost = 0.6 if i == 0 else 0.4  # Bigger boost for very first word
                    intent_scores[target_intent] += boost
                    break  # First match wins


class LLMAssistedRouter(IntentDetectionRouter):
    """
    Future extension point for LLM-assisted intent classification.
    
    This class maintains the same interface but could optionally use
    LLM calls for more sophisticated intent detection when needed.
    """
    
    def __init__(self, use_llm: bool = False):
        """Initialize with optional LLM assistance."""
        super().__init__()
        self.use_llm = use_llm
        
    async def detect_intent_with_llm(
        self,
        message: str,
        exception_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        domain: Optional[str] = None
    ) -> IntentResult:
        """
        Placeholder for future LLM-assisted intent detection.
        
        For MVP, this falls back to heuristic detection.
        Future implementations could use LLM for edge cases or confidence boosting.
        """
        # For MVP, fall back to deterministic approach
        return self.detect_intent(message, exception_id, tenant_id, domain)