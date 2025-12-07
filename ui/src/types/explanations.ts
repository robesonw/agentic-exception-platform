/**
 * Explanation and timeline types
 * 
 * Mirrors backend models from:
 * - src/api/routes/router_explanations.py (ExplanationResponse, ExplanationSearchResponse)
 * - src/services/explanation_service.py (ExplanationFormat, ExplanationSummary, DecisionTimeline)
 * - src/explainability/timelines.py (DecisionTimeline, TimelineStage)
 * - docs/03-data-models-apis.md
 */

/**
 * Explanation format
 * Mirrors ExplanationFormat enum from src/services/explanation_service.py
 */
export type ExplanationFormat = 'json' | 'text' | 'structured'

/**
 * Explanation response
 * Mirrors ExplanationResponse from router_explanations.py
 */
export interface ExplanationResponse {
  /** Exception identifier */
  exceptionId: string
  /** Explanation in requested format (dict for json/structured, string for text) */
  explanation: Record<string, unknown> | string
  /** Format used (json, text, structured) */
  format: ExplanationFormat
  /** Version information */
  version: {
    /** Version identifier (pipeline run ID) */
    version: string
    /** ISO datetime when this version was created */
    timestamp: string
  }
}

/**
 * Explanation summary (for search results)
 * Mirrors ExplanationSummary from src/services/explanation_service.py
 */
export interface ExplanationSummary {
  /** Exception identifier */
  exceptionId: string
  /** Tenant identifier */
  tenantId: string
  /** Agent name (optional) */
  agentName?: string | null
  /** Decision type (optional) */
  decisionType?: string | null
  /** Brief explanation summary */
  summary: string
  /** ISO datetime when the decision was made */
  timestamp: string
  /** Confidence score (0.0 to 1.0, optional) */
  confidence?: number | null
}

/**
 * Explanation search response
 * Mirrors ExplanationSearchResponse from router_explanations.py
 */
export interface ExplanationSearchResponse {
  /** List of explanation summaries */
  items: ExplanationSummary[]
  /** Total number of results */
  total: number
  /** Current page number (1-indexed) */
  page: number
  /** Page size */
  pageSize: number
  /** Total number of pages */
  totalPages: number
}

/**
 * Agent stage names
 * Mirrors agent stage names from pipeline (Intake, Triage, Policy, Resolution, Feedback)
 */
export type TimelineStage = 'intake' | 'triage' | 'policy' | 'resolution' | 'feedback'

/**
 * Timeline entry structure
 * Mirrors timeline entry structure from DecisionTimeline in src/explainability/timelines.py
 */
export interface TimelineEntry {
  /** Agent stage */
  stage: TimelineStage
  /** Decision made by agent */
  decision: string
  /** Confidence score (0.0 to 1.0, optional) */
  confidence?: number | null
  /** ISO datetime when decision was made */
  timestamp: string
  /** Evidence IDs used (optional) */
  evidenceIds?: string[]
  /** Additional stage-specific data */
  [key: string]: unknown
}

/**
 * Decision timeline
 * Mirrors DecisionTimeline structure from src/explainability/timelines.py
 * Returned by GET /explanations/{exception_id}/timeline endpoint
 */
export interface DecisionTimeline {
  /** Exception identifier */
  exceptionId: string
  /** Tenant identifier */
  tenantId: string
  /** Timeline entries in chronological order */
  entries: TimelineEntry[]
  /** Additional timeline metadata */
  [key: string]: unknown
}

/**
 * Evidence item type
 * Mirrors evidence item types from evidence tracking
 */
export type EvidenceItemType = 'rag' | 'tool' | 'policy' | 'historical' | 'other'

/**
 * Evidence item
 * Mirrors EvidenceItem structure from src/explainability/evidence.py
 */
export interface EvidenceItem {
  /** Evidence identifier */
  id: string
  /** Evidence type */
  type: EvidenceItemType
  /** Evidence content/data */
  content: Record<string, unknown>
  /** ISO datetime when evidence was collected */
  timestamp: string
  /** Additional evidence metadata */
  [key: string]: unknown
}

/**
 * Evidence link
 * Mirrors EvidenceLink structure from src/explainability/evidence.py
 */
export interface EvidenceLink {
  /** Source evidence ID */
  sourceId: string
  /** Target evidence ID or decision ID */
  targetId: string
  /** Link type */
  linkType: string
  /** Additional link metadata */
  [key: string]: unknown
}

/**
 * Evidence graph
 * Mirrors evidence graph structure returned by GET /explanations/{exception_id}/evidence endpoint
 */
export interface EvidenceGraph {
  /** All evidence items */
  items: EvidenceItem[]
  /** Evidence links */
  links: EvidenceLink[]
  /** Graph structure (nodes and edges, optional) */
  graph?: {
    nodes: Array<{
      id: string
      type: string
      data: Record<string, unknown>
    }>
    edges: Array<{
      source: string
      target: string
      type: string
    }>
  }
  /** Additional graph metadata */
  [key: string]: unknown
}

