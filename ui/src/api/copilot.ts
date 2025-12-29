/**
 * API client for Phase 13 Copilot chat endpoints
 * 
 * Mirrors backend routes from:
 * - src/api/routes/router_copilot.py
 * 
 * Reference: docs/phase13-copilot-intelligence-mvp.md Section 5 (Backend APIs)
 */

import { httpClient } from '../utils/httpClient'
import type { 
  CopilotRequest, 
  CopilotResponse, 
  CreateSessionRequest,
  CreateSessionResponse 
} from '../hooks/useCopilotChat'

// Re-export types for convenience
export type { 
  CopilotRequest, 
  CopilotResponse,
  CreateSessionRequest,
  CreateSessionResponse,
  CopilotCitation,
  RecommendedPlaybook,
  SimilarException,
  SafetyConstraints
} from '../hooks/useCopilotChat'

/**
 * Send a chat message to the Phase 13 Copilot
 * POST /api/copilot/chat
 * 
 * @param request Copilot request with message, session_id, and optional context
 * @returns Copilot response with structured answer, bullets, citations, and metadata
 */
export async function sendCopilotChat(
  request: CopilotRequest
): Promise<CopilotResponse> {
  return httpClient.post<CopilotResponse>('/api/copilot/chat', request)
}

/**
 * Create a new copilot conversation session
 * POST /api/copilot/sessions
 * 
 * @param request Session creation request with optional title
 * @returns Session details with session_id and created_at
 */
export async function createCopilotSession(
  request: CreateSessionRequest = {}
): Promise<CreateSessionResponse> {
  return httpClient.post<CreateSessionResponse>('/api/copilot/sessions', request)
}

