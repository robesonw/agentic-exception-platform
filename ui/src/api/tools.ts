/**
 * API client for tool-related endpoints
 * 
 * Mirrors backend routes from:
 * - src/api/routes/tools.py (P8-1, P8-6, P8-8: Tool Registry & Execution)
 * 
 * All functions automatically include tenantId via httpClient interceptors.
 */

import { httpClient } from '../utils/httpClient'

/**
 * Tool definition response from API
 */
export interface ToolDefinition {
  toolId: number
  tenantId: string | null
  name: string
  type: string
  config: Record<string, any>
  enabled: boolean | null
  createdAt: string
}

/**
 * Parameters for listing tools
 * Mirrors query parameters from GET /api/tools
 */
export interface ListToolsParams {
  /** Scope filter: tenant, global, or all */
  scope?: 'tenant' | 'global' | 'all'
  /** Status filter: enabled or disabled */
  status?: 'enabled' | 'disabled'
  /** Tool name filter (partial match) */
  name?: string
  /** Tool type filter (exact match) */
  type?: string
  /** Tenant identifier (optional, for tenant-scoped tools) */
  tenant_id?: string
}

/**
 * Paginated response for tools list
 */
export interface ToolsListResponse {
  items: ToolDefinition[]
  total: number
}

/**
 * List tools with filtering
 * GET /api/tools
 * 
 * @param params Query parameters for filtering
 * @returns Paginated list of tool definitions
 */
export async function listTools(params?: ListToolsParams): Promise<ToolsListResponse> {
  const response = await httpClient.get<ToolsListResponse>('/api/tools', { params })
  return response
}

/**
 * Get a single tool definition by ID
 * GET /api/tools/{tool_id}
 * 
 * @param toolId Tool identifier
 * @param tenantId Optional tenant identifier (required for tenant-scoped tools)
 * @returns Tool definition
 */
export async function getTool(toolId: number, tenantId?: string): Promise<ToolDefinition> {
  const params = tenantId ? { tenant_id: tenantId } : undefined
  const response = await httpClient.get<ToolDefinition>(`/api/tools/${toolId}`, { params })
  return response
}

/**
 * Tool execution response from API
 */
export interface ToolExecution {
  executionId: string
  tenantId: string
  toolId: number
  exceptionId: string | null
  status: 'requested' | 'running' | 'succeeded' | 'failed'
  requestedByActorType: 'user' | 'agent' | 'system'
  requestedByActorId: string
  inputPayload: Record<string, any>
  outputPayload: Record<string, any> | null
  errorMessage: string | null
  createdAt: string
  updatedAt: string
}

/**
 * Parameters for listing tool executions
 */
export interface ListToolExecutionsParams {
  /** Filter by tool ID */
  tool_id?: number
  /** Filter by exception ID */
  exception_id?: string
  /** Filter by status */
  status?: 'requested' | 'running' | 'succeeded' | 'failed'
  /** Filter by actor type */
  actor_type?: 'user' | 'agent' | 'system'
  /** Filter by actor ID */
  actor_id?: string
  /** Page number (1-indexed) */
  page?: number
  /** Items per page */
  page_size?: number
}

/**
 * Paginated response for tool executions
 */
export interface ToolExecutionsListResponse {
  items: ToolExecution[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

/**
 * Request model for executing a tool
 */
export interface ExecuteToolRequest {
  payload: Record<string, any>
  exceptionId?: string
  actorType?: 'user' | 'agent' | 'system'
  actorId: string
}

/**
 * List tool executions with filtering
 * GET /api/tools/executions
 * 
 * @param params Query parameters for filtering
 * @returns Paginated list of tool executions
 */
export async function listToolExecutions(params?: ListToolExecutionsParams): Promise<ToolExecutionsListResponse> {
  const response = await httpClient.get<ToolExecutionsListResponse>('/api/tools/executions', { params })
  return response
}

/**
 * Execute a tool
 * POST /api/tools/{tool_id}/execute
 * 
 * @param toolId Tool identifier
 * @param request Request body with payload and actor info
 * @returns Tool execution result
 */
export async function executeTool(toolId: number, request: ExecuteToolRequest): Promise<ToolExecution> {
  const response = await httpClient.post<ToolExecution>(`/api/tools/${toolId}/execute`, request)
  return response
}

