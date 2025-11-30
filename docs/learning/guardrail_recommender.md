# Guardrail Adjustment Recommendation System

## Overview

The Guardrail Adjustment Recommendation System (Phase 3, Issue P3-10) analyzes policy violations, false positives, and false negatives for guardrails to suggest guardrail tuning and adjustments.

**Safety**: All recommendations are suggestions only and never auto-applied. Human review and approval is required for all guardrail adjustments.

## Purpose

Guardrails are defined in Domain Packs and Tenant Policy Packs to enforce security, compliance, and operational boundaries. Over time, guardrails may become:
- **Too strict**: Causing high false positive rates (blocking legitimate operations)
- **Too lenient**: Causing high false negative rates (allowing operations that should be blocked)

The Guardrail Recommender analyzes historical performance metrics and suggests adjustments to optimize guardrail effectiveness.

## Inputs

### Metrics Data
- **False positives**: Cases where guardrails blocked operations that should have been allowed
- **False negatives**: Cases where guardrails allowed operations that should have been blocked
- **Total checks**: Total number of guardrail evaluations
- **Violation counts**: Number of policy violations detected
- **Human override counts**: Number of times humans overrode guardrail decisions

### Policy Logs
- Historical policy decisions from `PolicyAgent`
- Policy violation records
- Human override records

### Guardrail Configs
- **Domain Pack guardrails**: Base guardrail configuration from `DomainPack.guardrails`
- **Tenant Policy Pack guardrails**: Tenant-specific overrides from `TenantPolicyPack.custom_guardrails`

## Output Schema

Each recommendation follows this structure:

```json
{
  "guardrailId": "human_approval_threshold",
  "tenantId": "tenant_001",
  "currentConfig": {
    "human_approval_threshold": 0.8
  },
  "proposedChange": {
    "human_approval_threshold": 0.9
  },
  "reason": "Human approval threshold is too strict (false positive ratio: 75.0%). Increase threshold from 0.80 to 0.90 to reduce false positives.",
  "impactAnalysis": {
    "estimatedFalsePositiveChange": -0.225,
    "estimatedFalseNegativeChange": 0.075,
    "confidence": 0.85,
    "currentFalsePositiveRatio": 0.75,
    "currentFalseNegativeRatio": 0.05,
    "currentAccuracy": 0.70,
    "totalChecks": 100
  },
  "reviewRequired": true,
  "createdAt": "2024-01-15T10:30:00Z",
  "confidence": 0.85,
  "metadata": {
    "false_positive_ratio": 0.75,
    "total_checks": 100,
    "false_positive_count": 75,
    "domain": "TestDomain"
  }
}
```

### Fields

- **guardrailId**: Identifier for the guardrail (e.g., "human_approval_threshold", "allow_lists", "block_lists")
- **tenantId**: Tenant identifier
- **currentConfig**: Current guardrail configuration
- **proposedChange**: Proposed guardrail adjustment
- **reason**: Natural language explanation of the recommendation
- **impactAnalysis**: Estimated impact of applying the recommendation
  - **estimatedFalsePositiveChange**: Expected change in false positive ratio (negative = reduction)
  - **estimatedFalseNegativeChange**: Expected change in false negative ratio (negative = reduction)
  - **confidence**: Confidence in the impact estimates
  - **currentFalsePositiveRatio**: Current false positive ratio
  - **currentFalseNegativeRatio**: Current false negative ratio
  - **currentAccuracy**: Current guardrail accuracy
  - **totalChecks**: Total number of guardrail evaluations
- **reviewRequired**: Always `true` (all recommendations require human review)
- **createdAt**: Timestamp when recommendation was created
- **confidence**: Confidence in the recommendation (0.0-1.0)
- **metadata**: Additional metadata about the recommendation

## Examples

### Example 1: Overly Strict Rate-Limit Guardrail

**Scenario**: A guardrail is blocking 80% of operations, but only 10% of those blocks are actually necessary.

**Recommendation**:
- **Guardrail**: `human_approval_threshold`
- **Current**: `0.7` (requires approval for confidence < 0.7)
- **Proposed**: `0.85` (requires approval for confidence < 0.85)
- **Reason**: "Human approval threshold is too strict (false positive ratio: 80.0%). Increase threshold from 0.70 to 0.85 to reduce false positives."
- **Impact**: Estimated 24% reduction in false positives, 8% increase in false negatives

### Example 2: Overly Permissive Tool-Scope Guardrail

**Scenario**: A guardrail is allowing 30% of operations that should be blocked (high false negative rate).

**Recommendation**:
- **Guardrail**: `allow_lists`
- **Current**: `["tool1", "tool2", "tool3"]`
- **Proposed**: Reduce allow list or add items to block list
- **Reason**: "Allow list is too permissive (false negative ratio: 30.0%). Consider reducing allow list based on false negative patterns."
- **Impact**: Estimated 9% reduction in false negatives, 3% increase in false positives

## Integration Points

### PolicyAgent

The `PolicyAgent` evaluates exceptions against guardrails and makes allow/block decisions. These decisions are tracked for analysis.

### Domain Pack & Tenant Policy Pack

Guardrails are defined in:
- **Domain Pack**: Base guardrail configuration (`DomainPack.guardrails`)
- **Tenant Policy Pack**: Tenant-specific overrides (`TenantPolicyPack.custom_guardrails`)

The recommender analyzes both to understand the effective guardrail configuration.

### Optimization Engine

The `OptimizationEngine` (P3-11) integrates guardrail recommendations alongside policy, severity, and playbook recommendations into a unified optimization report.

### Policy Learning Pipeline

The `PolicyLearning` module (P3-7) can be extended to call `GuardrailRecommender` alongside severity and playbook recommenders, providing combined suggestions in `get_combined_suggestions()`.

## Configuration Thresholds

The recommender uses configurable thresholds (defined in `GuardrailAnalysisConfig`):

- **HIGH_FALSE_POSITIVE_RATIO**: `0.7` (70%) - Threshold for detecting overly strict guardrails
- **HIGH_FALSE_NEGATIVE_RATIO**: `0.3` (30%) - Threshold for detecting overly lenient guardrails
- **MIN_SAMPLE_SIZE**: `10` - Minimum number of evaluations for reliable analysis
- **MIN_CONFIDENCE_THRESHOLD**: `0.6` - Minimum confidence for recommendations

## Heuristics

The recommender uses simple, explainable heuristics for MVP:

1. **High False Positive Ratio (≥70%)**:
   - Indicates guardrail is too strict
   - Suggests relaxing criteria (e.g., increase threshold, expand allow list, reduce block list)

2. **High False Negative Ratio (≥30%)**:
   - Indicates guardrail is too lenient
   - Suggests tightening criteria (e.g., decrease threshold, reduce allow list, expand block list)

3. **Balanced Performance**:
   - If false positive and false negative ratios are both below thresholds
   - No recommendation or low-confidence suggestion

## Storage

Recommendations are persisted to:
```
./runtime/learning/{tenantId}_{domainName}_guardrail_recommendations.jsonl
```

Each line is a JSON object representing a single recommendation.

## Audit Trail

All guardrail recommendation events are logged to the audit trail:

- **GUARDRAIL_RECOMMENDATION_GENERATED**: When a recommendation is created
- **GUARDRAIL_RECOMMENDATION_ACCEPTED**: When a recommendation is accepted (future UX flow)
- **GUARDRAIL_RECOMMENDATION_REJECTED**: When a recommendation is rejected (future UX flow)

## API Endpoints

### GET /learning/guardrail-recommendations

Retrieve guardrail recommendations for a tenant and domain.

**Query Parameters**:
- `tenant_id` (required): Tenant identifier
- `domain` (required): Domain name identifier
- `guardrail_id` (optional): Filter by specific guardrail ID

**Response**:
```json
{
  "tenant_id": "tenant_001",
  "domain": "TestDomain",
  "guardrail_id": null,
  "recommendations": [...],
  "count": 2
}
```

## Future Enhancements

- Machine learning-based impact prediction
- A/B testing framework for guardrail adjustments
- Automated guardrail optimization (with human approval)
- Integration with red-team testing (P3-21)
- Multi-tenant guardrail benchmarking

