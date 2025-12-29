import { useState } from 'react';
import { useTenant } from './useTenant';
import { sendCopilotChat, createCopilotSession } from '../api/copilot';

/**
 * TypeScript types for Phase 13 Copilot chat functionality.
 * 
 * These types match the backend ChatResponse model from src/api/routes/router_copilot.py
 * Reference: docs/phase13-copilot-intelligence-mvp.md Section 6 (Response Contract)
 */

export type CopilotCitation = {
  id: string;
  source_type: 'policy_doc' | 'resolved_exception' | 'audit_event' | 'tool_registry' | 'playbook';
  title: string;
  snippet: string;
  relevance_score: number;
  metadata?: Record<string, any>;
  url?: string; // For UI navigation
};

export interface RecommendedPlaybook {
  playbook_id: string;
  name: string;
  confidence: number;
  rationale: string;
  steps: Array<{
    step: number;
    text: string;
    type?: string;
  }>;
}

export interface SimilarException {
  exception_id: string;
  similarity_score: number;
  title?: string;
  outcome?: string;
}

export interface SafetyConstraints {
  mode: 'READ_ONLY' | 'RESTRICTED' | 'FULL_ACCESS';
  blocked?: boolean;
  actions_allowed: string[];
  warnings?: string[];
}

export interface CopilotRequest {
  message: string;
  session_id?: string;
  context?: Record<string, any>;
  domain?: string;
}

export interface CopilotResponse {
  request_id: string;
  session_id: string;
  answer: string;
  bullets: string[];
  citations: CopilotCitation[];
  recommended_playbook?: RecommendedPlaybook;
  similar_exceptions?: SimilarException[];
  intent: string;
  confidence: number;
  processing_time_ms: number;
  safety: SafetyConstraints;
}

export interface CreateSessionRequest {
  title?: string;
}

export interface CreateSessionResponse {
  session_id: string;
  title: string;
  created_at: string;
}

export type ChatMessage = {
  role: 'user' | 'assistant';
  text: string;
  meta?: Partial<CopilotResponse>;
};

/**
 * Hook for managing Phase 13 Copilot chat state and interactions.
 * 
 * Provides:
 * - Session management (create session on first open)
 * - Message history management
 * - Loading state during API calls
 * - Error state handling
 * - sendMessage function wired to POST /api/copilot/chat
 * 
 * Reference: docs/phase13-copilot-intelligence-mvp.md Section 6.1 (Chat API)
 */
export function useCopilotChat() {
  const { tenantId } = useTenant();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      text: 'Hello, Operator. I am your enterprise AI assistant monitoring exceptions across your platform. How can I assist you today?',
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Send a message to the Phase 13 Copilot backend with session management.
   * 
   * Flow:
   * 1. Create session if needed (first message)
   * 2. Send message to POST /api/copilot/chat
   * 3. Handle structured response with citations, playbooks, safety
   * 
   * @param text - User message text
   * @param context - Optional context (e.g., current exception ID, page context)
   */
  const sendMessage = async (text: string, context?: Record<string, any>) => {
    if (!text.trim()) return;

    // Add user message immediately
    const userMessage: ChatMessage = {
      role: 'user',
      text: text.trim(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);
    setError(null);

    try {
      // Handle test/demo case first to verify UI rendering
      if (text.toLowerCase().includes('test structured response demo')) {
        // Simulate a full structured response to test UI
        const testResponse: ChatMessage = {
          role: 'assistant',
          text: 'This is a demo of the Phase 13 Copilot structured response format.',
          meta: {
            request_id: 'test-123',
            session_id: 'test-session',
            answer: 'This is a demo of the Phase 13 Copilot structured response format.',
            bullets: [
              'Enhanced citations with source type badges',
              'Recommended playbooks with confidence scores',
              'Similar exceptions finder integration',
              'READ_ONLY safety constraints enforcement',
            ],
            citations: [
              {
                id: 'POL-FIN-001',
                source_type: 'policy_doc',
                title: 'Financial Settlement Policy',
                snippet: 'Settlement failures require immediate escalation...',
                relevance_score: 0.95,
                metadata: {}
              },
              {
                id: 'EX-2024-001',
                source_type: 'resolved_exception',
                title: 'Resolved Settlement Timeout',
                snippet: 'Similar timeout issue resolved using playbook PB-FIN-001...',
                relevance_score: 0.87,
                metadata: {}
              },
              {
                id: 'TOOL-SETTLEMENT-001',
                source_type: 'tool_registry',
                title: 'Settlement Retry Tool',
                snippet: 'Automated retry mechanism for failed settlements',
                relevance_score: 0.82,
                metadata: {}
              }
            ],
            recommended_playbook: {
              playbook_id: 'PB-FIN-001',
              name: 'Handle Settlement Failure',
              confidence: 0.94,
              rationale: 'Based on similar settlement timeout patterns and policy requirements',
              steps: [
                { step: 1, text: 'Verify transaction details and status' },
                { step: 2, text: 'Check counterparty connectivity' },
                { step: 3, text: 'Escalate to operations if timeout persists' },
                { step: 4, text: 'Execute manual settlement if approved' }
              ]
            },
            similar_exceptions: [
              { exception_id: 'EX-2024-001', similarity_score: 0.94, title: 'Settlement Timeout' },
              { exception_id: 'EX-2024-015', similarity_score: 0.89, title: 'Network Timeout' },
              { exception_id: 'EX-2024-032', similarity_score: 0.76, title: 'Connection Error' }
            ],
            intent: 'PLAYBOOK_RECOMMENDATION',
            confidence: 0.94,
            processing_time_ms: 1250,
            safety: {
              mode: 'READ_ONLY',
              actions_allowed: [],
              warnings: ['This is a demonstration response with test data']
            }
          }
        };

        setMessages((prev) => [...prev, testResponse]);
        setLoading(false);
        return;
      }

      // Create session if needed (first interaction)
      let currentSessionId = sessionId;
      if (!currentSessionId) {
        const sessionResponse = await createCopilotSession({});
        currentSessionId = sessionResponse.session_id;
        setSessionId(currentSessionId);
      }

      // Build request
      const request: CopilotRequest = {
        message: text.trim(),
        session_id: currentSessionId,
        context: context || null,
        domain: null, // Will be derived from tenant context in backend
      };

      // Call backend API
      const response: CopilotResponse = await sendCopilotChat(request);

      // Build assistant message with full structured metadata
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        text: response.answer,
        meta: {
          request_id: response.request_id,
          session_id: response.session_id,
          answer: response.answer,
          bullets: response.bullets,
          citations: response.citations,
          recommended_playbook: response.recommended_playbook,
          similar_exceptions: response.similar_exceptions,
          intent: response.intent,
          confidence: response.confidence,
          processing_time_ms: response.processing_time_ms,
          safety: response.safety,
        },
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setLoading(false);
    } catch (err: any) {
      // Handle error gracefully
      const errorMessage = err?.response?.status === 403 
        ? 'Access denied. Please check your permissions.'
        : err?.response?.status === 401 
        ? 'Please log in to continue using Copilot.'
        : 'Copilot is temporarily unavailable. Please try again later.';
      
      setError(errorMessage);
      
      // Append error message as assistant message
      const errorAssistantMessage: ChatMessage = {
        role: 'assistant',
        text: errorMessage,
        meta: {
          request_id: '',
          session_id: sessionId || '',
          answer: errorMessage,
          bullets: [],
          citations: [],
          intent: 'ERROR',
          confidence: 0,
          processing_time_ms: 0,
          safety: { mode: 'READ_ONLY' as const, actions_allowed: [] },
        },
      };
      
      setMessages((prev) => [...prev, errorAssistantMessage]);
      setLoading(false);
    }
  };

  return {
    messages,
    setMessages,
    sessionId,
    loading,
    error,
    sendMessage,
  };
}

