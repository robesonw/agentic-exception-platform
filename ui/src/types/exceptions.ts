/**
 * Exception-related types
 * 
 * Mirrors backend models from:
 * - src/models/exception_record.py (ExceptionRecord, Severity, ResolutionStatus)
 * - src/api/routes/router_operator.py (ExceptionListItem, ExceptionDetailResponse, EvidenceResponse)
 * - docs/03-data-models-apis.md (Canonical Exception Schema)
 */

/**
 * Exception severity levels
 * Mirrors Severity enum from src/models/exception_record.py
 */
export type ExceptionSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

/**
 * Exception resolution status
 * Mirrors ResolutionStatus enum from src/models/exception_record.py
 */
export type ExceptionStatus = 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'ESCALATED' | 'PENDING_APPROVAL'

/**
 * Exception list item (summary for browsing)
 * Mirrors ExceptionListItem from router_operator.py
 */
export interface ExceptionSummary extends Record<string, unknown> {
  /** Unique exception identifier */
  exception_id: string
  /** Tenant identifier */
  tenant_id: string
  /** Domain name (optional) */
  domain?: string | null
  /** Exception type from Domain Pack taxonomy (optional) */
  exception_type?: string | null
  /** Severity level (optional) */
  severity?: ExceptionSeverity | null
  /** Resolution status */
  resolution_status: ExceptionStatus
  /** Source system name (optional) */
  source_system?: string | null
  /** ISO datetime when exception occurred */
  timestamp: string
}

/**
 * Audit trail entry
 * Mirrors AuditEntry from src/models/exception_record.py
 */
export interface AuditEntry {
  /** Description of the action performed */
  action: string
  /** ISO datetime when action occurred */
  timestamp: string
  /** Agent or system component performing action */
  actor: string
}

/**
 * Full exception detail record
 * Mirrors ExceptionRecord from src/models/exception_record.py
 * and exception field in ExceptionDetailResponse from router_operator.py
 */
export interface ExceptionDetail {
  /** Unique exception identifier */
  exceptionId: string
  /** Tenant identifier */
  tenantId: string
  /** Source system name (e.g., 'ERP') */
  sourceSystem: string
  /** Exception type from Domain Pack taxonomy (optional) */
  exceptionType?: string | null
  /** Exception severity level (optional) */
  severity?: ExceptionSeverity | null
  /** ISO datetime when exception occurred */
  timestamp: string
  /** Arbitrary source data */
  rawPayload: Record<string, unknown>
  /** Key-value pairs from normalization */
  normalizedContext: Record<string, unknown>
  /** Array of violated rules */
  detectedRules: string[]
  /** Array of potential resolutions */
  suggestedActions: string[]
  /** Resolution status */
  resolutionStatus: ExceptionStatus
  /** Array of audit trail entries */
  auditTrail: AuditEntry[]
}

/**
 * Agent decisions from pipeline stages
 * Mirrors agent_decisions field in ExceptionDetailResponse from router_operator.py
 */
export interface AgentDecisions {
  /** Intake agent decision (optional) */
  intake?: Record<string, unknown>
  /** Triage agent decision (optional) */
  triage?: Record<string, unknown>
  /** Policy agent decision (optional) */
  policy?: Record<string, unknown>
  /** Resolution agent decision (optional) */
  resolution?: Record<string, unknown>
  /** Feedback agent decision (optional) */
  feedback?: Record<string, unknown>
  /** Additional stage decisions */
  [stageName: string]: Record<string, unknown> | undefined
}

/**
 * Pipeline result structure
 * Mirrors pipeline_result field in ExceptionDetailResponse from router_operator.py
 */
export interface PipelineResult {
  /** Stage results keyed by stage name */
  stages: Record<string, unknown>
  /** Additional pipeline metadata */
  [key: string]: unknown
}

/**
 * Exception detail response
 * Mirrors ExceptionDetailResponse from router_operator.py
 */
export interface ExceptionDetailResponse {
  /** Full exception record */
  exception: ExceptionDetail
  /** Agent decisions from all stages */
  agent_decisions: AgentDecisions
  /** Full pipeline processing result */
  pipeline_result: PipelineResult
}

/**
 * RAG result item
 * Mirrors rag_results array in EvidenceResponse from router_operator.py
 */
export interface RAGResult {
  /** Similar exception ID (optional) */
  exception_id?: string
  /** Similarity score (optional) */
  score?: number
  /** RAG result data */
  [key: string]: unknown
}

/**
 * Tool output item
 * Mirrors tool_outputs array in EvidenceResponse from router_operator.py
 */
export interface ToolOutput {
  /** Tool name */
  tool_name?: string
  /** Tool execution result */
  result?: unknown
  /** Tool output data */
  [key: string]: unknown
}

/**
 * Agent evidence item
 * Mirrors agent_evidence array in EvidenceResponse from router_operator.py
 */
export interface AgentEvidence {
  /** Agent name */
  agent_name?: string
  /** Evidence data */
  evidence?: unknown
  /** Additional evidence fields */
  [key: string]: unknown
}

/**
 * Evidence response
 * Mirrors EvidenceResponse from router_operator.py
 */
export interface EvidenceResponse {
  /** RAG results (similar historical exceptions) */
  rag_results: RAGResult[]
  /** Tool outputs (executed tool results) */
  tool_outputs: ToolOutput[]
  /** Agent evidence (evidence from each agent stage) */
  agent_evidence: AgentEvidence[]
}

/**
 * Audit event structure
 * Mirrors audit events from get_exception_audit endpoint in router_operator.py
 */
export interface AuditEvent {
  /** Event timestamp */
  timestamp: string
  /** Pipeline run ID */
  run_id?: string
  /** Event type (agent_event, tool_call, decision) */
  event_type?: string
  /** Event-specific data */
  data?: Record<string, unknown>
}

/**
 * Audit response
 * Mirrors response from get_exception_audit endpoint in router_operator.py
 */
export interface AuditResponse {
  /** Exception identifier */
  exception_id: string
  /** Tenant identifier */
  tenant_id: string
  /** Array of audit events */
  events: AuditEvent[]
  /** Total number of events */
  count: number
}

/**
 * Workflow node
 * Mirrors WorkflowNode from router_operator.py
 */
export interface WorkflowNode {
  /** Node identifier */
  id: string
  /** Node type (agent, decision, human, system, playbook) */
  type: string
  /** Node kind (stage, playbook, step) */
  kind: string
  /** Display label */
  label: string
  /** Node status (pending, in-progress, completed, failed, skipped) */
  status: string
  /** Start timestamp */
  started_at?: string | null
  /** Completion timestamp */
  completed_at?: string | null
  /** Additional metadata */
  meta?: Record<string, unknown> | null
}

/**
 * Workflow edge
 * Mirrors WorkflowEdge from router_operator.py
 */
export interface WorkflowEdge {
  /** Edge identifier */
  id: string
  /** Source node ID */
  source: string
  /** Target node ID */
  target: string
  /** Optional edge label */
  label?: string | null
}

/**
 * Workflow graph response
 * Mirrors WorkflowGraphResponse from router_operator.py
 */
export interface WorkflowGraphResponse {
  /** Array of workflow nodes */
  nodes: WorkflowNode[]
  /** Array of workflow edges */
  edges: WorkflowEdge[]
  /** Current active stage */
  current_stage?: string | null
  /** Associated playbook ID */
  playbook_id?: string | number | null
  /** Name of the playbook */
  playbook_name?: string | null
  /** Playbook steps definition */
  playbook_steps?: unknown[] | null
  /** Current step the exception is on in the playbook */
  exception_current_step?: number | null
}

