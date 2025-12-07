/**
 * Configuration types (Domain Packs, Tenant Policy Packs, Playbooks)
 * 
 * Mirrors backend models from:
 * - src/api/routes/router_config_view.py (ConfigListItem, ConfigDetailResponse, ConfigDiffResponse)
 * - src/models/domain_pack.py (DomainPack)
 * - src/models/tenant_policy.py (TenantPolicyPack)
 * - docs/03-data-models-apis.md (Domain Pack Schema, Tenant Policy Pack Schema)
 */

/**
 * Configuration type
 * Mirrors ConfigType enum usage in router_config_view.py
 */
export type ConfigType = 'domain_pack' | 'tenant_policy' | 'playbook'

/**
 * Configuration list item
 * Mirrors ConfigListItem from router_config_view.py
 */
export interface ConfigListItem extends Record<string, unknown> {
  /** Configuration identifier */
  id: string
  /** Configuration name */
  name: string
  /** Version string */
  version: string
  /** Tenant identifier */
  tenant_id: string
  /** Domain name (optional) */
  domain?: string | null
  /** Exception type (optional, for playbooks) */
  exception_type?: string | null
  /** Timestamp (optional) */
  timestamp?: string | null
}

/**
 * Configuration list response
 * Mirrors ConfigListResponse from router_config_view.py
 */
export interface ConfigListResponse {
  /** List of configurations */
  items: ConfigListItem[]
  /** Total number of configurations */
  total: number
}

/**
 * Configuration detail response
 * Mirrors ConfigDetailResponse from router_config_view.py
 */
export interface ConfigDetailResponse {
  /** Configuration identifier */
  id: string
  /** Configuration type */
  type: string
  /** Configuration data (full schema) */
  data: Record<string, unknown>
  /** Version string (if available) */
  version?: string
  /** Available versions for comparison (if history endpoint provides) */
  availableVersions?: Array<{ id: string; label: string; timestamp?: string | null }>
}

/**
 * Configuration diff response
 * Mirrors ConfigDiffResponse from router_config_view.py
 */
export interface ConfigDiffResponse {
  /** Left configuration */
  left: Record<string, unknown>
  /** Right configuration */
  right: Record<string, unknown>
  /** Structured differences */
  differences: Record<string, unknown>
  /** Summary of changes */
  summary: Record<string, unknown>
}

/**
 * Extended diff result with version metadata
 * Used for UI display
 */
export interface ConfigDiffResult {
  /** Left version ID */
  leftVersionId: string
  /** Right version ID */
  rightVersionId: string
  /** Left version label (e.g., "v1.0.0") */
  leftLabel?: string
  /** Right version label (e.g., "v1.1.0") */
  rightLabel?: string
  /** Number of additions */
  additions: number
  /** Number of deletions */
  deletions: number
  /** Number of changes */
  changes: number
  /** Raw text/json diff if provided */
  diffText?: string
  /** Structured diff from backend */
  structuredDiff?: ConfigDiffResponse
}

/**
 * Configuration history item
 * Mirrors ConfigHistoryItem from router_config_view.py
 */
export interface ConfigHistoryItem {
  /** Version string */
  version: string
  /** Timestamp (optional) */
  timestamp?: string | null
  /** Configuration identifier */
  id: string
}

/**
 * Configuration history response
 * Mirrors ConfigHistoryResponse from router_config_view.py
 */
export interface ConfigHistoryResponse {
  /** List of version history entries */
  items: ConfigHistoryItem[]
  /** Total number of versions */
  total: number
}

/**
 * Domain Pack summary (for list views)
 * Based on ConfigListItem with domain-specific fields
 */
export interface DomainPackSummary extends ConfigListItem {
  /** Always 'domain_pack' */
  type: 'domain_pack'
}

/**
 * Domain Pack detail
 * Mirrors DomainPack schema from src/models/domain_pack.py and docs/03-data-models-apis.md
 */
export interface DomainPackDetail {
  /** Domain name */
  domainName: string
  /** Entity definitions keyed by entity name */
  entities: Record<string, {
    attributes: Record<string, unknown>
    relations: unknown[]
  }>
  /** Exception type definitions keyed by type name */
  exceptionTypes: Record<string, {
    description: string
    detectionRules: unknown[]
  }>
  /** Severity mapping rules */
  severityRules: Array<{
    condition: string
    severity: string
  }>
  /** Tool definitions keyed by tool name */
  tools: Record<string, {
    description: string
    parameters: Record<string, unknown>
    endpoint: string
  }>
  /** Playbook definitions */
  playbooks: Array<{
    exceptionType: string
    steps: unknown[]
  }>
  /** Guardrails configuration */
  guardrails: {
    allowLists: unknown[]
    blockLists: unknown[]
    humanApprovalThreshold: number
  }
  /** Test suites */
  testSuites: Array<{
    input: Record<string, unknown>
    expectedOutput: Record<string, unknown>
  }>
}

/**
 * Tenant Policy Pack summary (for list views)
 * Based on ConfigListItem with policy-specific fields
 */
export interface TenantPolicyPackSummary extends ConfigListItem {
  /** Always 'tenant_policy' */
  type: 'tenant_policy'
}

/**
 * Tenant Policy Pack detail
 * Mirrors TenantPolicyPack schema from src/models/tenant_policy.py and docs/03-data-models-apis.md
 */
export interface TenantPolicyPackDetail {
  /** Tenant identifier */
  tenantId: string
  /** Domain name (references Domain Pack) */
  domainName: string
  /** Custom severity overrides */
  customSeverityOverrides: Array<{
    exceptionType: string
    severity: string
  }>
  /** Custom guardrails (similar to Domain Pack guardrails) */
  customGuardrails: {
    allowLists: unknown[]
    blockLists: unknown[]
    humanApprovalThreshold: number
  }
  /** Approved tool names */
  approvedTools: string[]
  /** Human approval rules */
  humanApprovalRules: Array<{
    severity: string
    requireApproval: boolean
  }>
  /** Data retention policies */
  retentionPolicies: {
    dataTTL: number // days
  }
  /** Custom playbooks */
  customPlaybooks: Array<{
    exceptionType: string
    steps: unknown[]
  }>
}

/**
 * Playbook summary (for list views)
 * Based on ConfigListItem with playbook-specific fields
 */
export interface PlaybookSummary extends ConfigListItem {
  /** Always 'playbook' */
  type: 'playbook'
}

/**
 * Playbook detail
 * Based on playbook structure from Domain Pack and Tenant Policy Pack
 */
export interface PlaybookDetail {
  /** Exception type this playbook handles */
  exceptionType: string
  /** Playbook steps/actions */
  steps: Array<{
    action: string
    parameters?: Record<string, unknown>
    [key: string]: unknown
  }>
  /** Additional playbook metadata */
  [key: string]: unknown
}

/**
 * Rollback request
 * Mirrors RollbackRequest from router_config_view.py
 */
export interface RollbackRequest {
  /** Configuration type */
  config_type: ConfigType
  /** Configuration identifier */
  config_id: string
  /** Target version to rollback to */
  target_version: string
}

/**
 * Rollback response
 * Mirrors RollbackResponse from router_config_view.py
 */
export interface RollbackResponse {
  /** Whether rollback validation succeeded */
  success: boolean
  /** Rollback message */
  message: string
  /** Note about rollback behavior */
  note?: string
}

/**
 * Configuration recommendation (generic)
 * Used for policy, severity, playbook, and guardrail recommendations
 */
export interface ConfigRecommendation {
  /** Recommendation identifier */
  id: string
  /** Recommendation type */
  type: 'policy' | 'severity' | 'playbook' | 'guardrail' | string
  /** Description of the recommendation */
  description: string
  /** Confidence score (0-1) */
  confidence?: number
  /** Suggested change description */
  suggestedChange?: string
  /** Impact analysis */
  impactAnalysis?: string | Record<string, unknown>
  /** Additional metadata */
  metadata?: Record<string, unknown>
}

/**
 * Guardrail recommendation response
 * Mirrors GuardrailRecommendation from src/learning/guardrail_recommender.py
 */
export interface GuardrailRecommendation {
  /** Guardrail identifier */
  guardrailId: string
  /** Tenant identifier */
  tenantId: string
  /** Current guardrail configuration */
  currentConfig: Record<string, unknown>
  /** Proposed guardrail change */
  proposedChange: Record<string, unknown>
  /** Reason for the recommendation */
  reason: string
  /** Impact analysis */
  impactAnalysis: Record<string, unknown>
  /** Whether human review is required */
  reviewRequired: boolean
  /** Timestamp when recommendation was created */
  createdAt: string
  /** Confidence score (0-1) */
  confidence: number
  /** Additional metadata */
  metadata?: Record<string, unknown>
}

/**
 * Guardrail recommendations response
 * Mirrors response from GET /learning/guardrail-recommendations
 */
export interface GuardrailRecommendationsResponse {
  /** Tenant identifier */
  tenant_id: string
  /** Domain name */
  domain: string
  /** Optional guardrail ID filter */
  guardrail_id?: string | null
  /** List of guardrail recommendations */
  recommendations: GuardrailRecommendation[]
  /** Count of recommendations */
  count: number
}

