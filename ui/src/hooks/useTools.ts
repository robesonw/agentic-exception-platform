/**
 * TanStack Query hooks for tool-related endpoints
 * 
 * Provides hooks for:
 * - Listing tools with filters
 * - Getting tool detail
 * 
 * All hooks include tenantId in query keys and handle errors via snackbar.
 */

import { useQuery, useMutation, useQueryClient, UseQueryResult, UseMutationResult } from '@tanstack/react-query'
import { useTenant } from './useTenant'
import {
  listTools,
  getTool,
  listToolExecutions,
  executeTool,
  type ListToolsParams,
  type ToolDefinition,
  type ToolsListResponse,
  type ListToolExecutionsParams,
  type ToolExecutionsListResponse,
  type ExecuteToolRequest,
  type ToolExecution,
} from '../api/tools'
import { useQueryErrorHandler } from './useQueryErrorHandler'

/**
 * Query key factory for tool-related queries
 */
export const toolKeys = {
  /** All tool queries */
  all: ['tools'] as const,
  /** Tool list queries */
  lists: () => [...toolKeys.all, 'list'] as const,
  /** Tool list query with params */
  list: (tenantId: string | null, params?: ListToolsParams) =>
    [...toolKeys.lists(), tenantId, params] as const,
  /** Tool detail queries */
  details: () => [...toolKeys.all, 'detail'] as const,
  /** Tool detail query */
  detail: (tenantId: string | null, toolId: number) =>
    [...toolKeys.details(), tenantId, toolId] as const,
  /** Tool execution queries */
  executions: () => [...toolKeys.all, 'executions'] as const,
  /** Tool executions list query */
  executionsList: (tenantId: string | null, params?: ListToolExecutionsParams) =>
    [...toolKeys.executions(), 'list', tenantId, params] as const,
}

/**
 * Hook to list tools with filtering
 * 
 * @param params Query parameters for filtering
 * @returns Query result with tools list
 */
export function useToolsList(params?: ListToolsParams): UseQueryResult<ToolsListResponse, Error> {
  const { tenantId } = useTenant()
  const handleError = useQueryErrorHandler()

  return useQuery<ToolsListResponse, Error>({
    queryKey: toolKeys.list(tenantId, params),
    queryFn: async () => {
      try {
        return await listTools(params)
      } catch (error) {
        handleError(error as Error)
        throw error
      }
    },
    enabled: true, // Always enabled, even without tenantId (for global tools)
  })
}

/**
 * Hook to get a single tool definition
 * 
 * @param toolId Tool identifier
 * @param enabled Whether the query is enabled (default: true if toolId is provided)
 * @returns Query result with tool definition
 */
export function useTool(toolId: number | null, enabled: boolean = true): UseQueryResult<ToolDefinition, Error> {
  const { tenantId } = useTenant()
  const handleError = useQueryErrorHandler()

  return useQuery<ToolDefinition, Error>({
    queryKey: toolKeys.detail(tenantId, toolId!),
    queryFn: async () => {
      try {
        return await getTool(toolId!, tenantId || undefined)
      } catch (error) {
        handleError(error as Error)
        throw error
      }
    },
    enabled: enabled && toolId !== null,
  })
}

/**
 * Hook to list tool executions with filtering
 * 
 * @param params Query parameters for filtering
 * @returns Query result with tool executions list
 */
export function useToolExecutions(
  params?: ListToolExecutionsParams
): UseQueryResult<ToolExecutionsListResponse, Error> {
  const { tenantId } = useTenant()
  const handleError = useQueryErrorHandler()

  return useQuery<ToolExecutionsListResponse, Error>({
    queryKey: toolKeys.executionsList(tenantId, params),
    queryFn: async () => {
      try {
        return await listToolExecutions(params)
      } catch (error) {
        handleError(error as Error)
        throw error
      }
    },
    enabled: true,
  })
}

/**
 * Hook to execute a tool
 * 
 * @returns Mutation result for executing a tool
 */
export function useExecuteTool(): UseMutationResult<ToolExecution, Error, { toolId: number; request: ExecuteToolRequest }, unknown> {
  const queryClient = useQueryClient()
  const { tenantId } = useTenant()
  const handleError = useQueryErrorHandler()

  return useMutation<ToolExecution, Error, { toolId: number; request: ExecuteToolRequest }>({
    mutationFn: async ({ toolId, request }) => {
      try {
        return await executeTool(toolId, request)
      } catch (error) {
        handleError(error as Error)
        throw error
      }
    },
    onSuccess: (data, variables) => {
      // Invalidate executions list to refresh after execution
      queryClient.invalidateQueries({
        queryKey: toolKeys.executionsList(tenantId, { tool_id: variables.toolId }),
      })
      // Also invalidate tool detail to refresh enabled status if needed
      queryClient.invalidateQueries({
        queryKey: toolKeys.detail(tenantId, variables.toolId),
      })
    },
  })
}

