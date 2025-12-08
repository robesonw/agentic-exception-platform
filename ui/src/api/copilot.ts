/**
 * API client for Co-Pilot chat endpoints
 * 
 * Mirrors backend routes from:
 * - src/api/routes/router_copilot.py
 * 
 * Reference: docs/phase5-copilot-mvp.md Section 3 (REST API)
 */

import { httpClient } from '../utils/httpClient'
import type { CopilotRequest, CopilotResponse } from '../hooks/useCopilotChat'

// Re-export types for convenience
export type { CopilotRequest, CopilotResponse } from '../hooks/useCopilotChat'

/**
 * Send a chat message to the Co-Pilot
 * POST /api/copilot/chat
 * 
 * @param request Co-Pilot request with message, tenant_id, domain, and optional context
 * @returns Co-Pilot response with answer, answer_type, citations, and optional trace ID
 */
export async function sendCopilotChat(
  request: CopilotRequest
): Promise<CopilotResponse> {
  return httpClient.post<CopilotResponse>('/api/copilot/chat', request)
}

