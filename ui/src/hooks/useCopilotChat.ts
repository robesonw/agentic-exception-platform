import { useState } from 'react';
import { useTenant } from './useTenant';
import { sendCopilotChat } from '../api/copilot';

/**
 * TypeScript types for Co-Pilot chat functionality.
 * 
 * These types match the backend CopilotResponse model from src/copilot/models.py
 * Reference: docs/phase5-copilot-mvp.md Section 6.3 (TS Types)
 */

export type CopilotCitation = {
  type: string;
  id: string;
};

export type CopilotAnswerType = 'EXPLANATION' | 'SUMMARY' | 'POLICY_HINT' | 'UNKNOWN';

export interface CopilotRequest {
  message: string;
  tenant_id: string;
  domain: string;
  context?: Record<string, any> | null;
}

export interface CopilotResponse {
  answer: string;
  answer_type: CopilotAnswerType;
  citations: CopilotCitation[];
  raw_llm_trace_id?: string | null;
}

export type ChatMessage = {
  role: 'user' | 'assistant';
  text: string;
  meta?: Partial<CopilotResponse>;
};

/**
 * Hook for managing Co-Pilot chat state and interactions.
 * 
 * Provides:
 * - Message history management
 * - Loading state during API calls
 * - Error state handling
 * - sendMessage function wired to POST /api/copilot/chat
 * 
 * Reference: docs/phase5-copilot-mvp.md Section 6.1 (useCopilotChat hook)
 */
export function useCopilotChat() {
  const { tenantId, domain } = useTenant();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      text: 'Hello, Operator. I am monitoring active exceptions. How can I assist you today?',
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Send a message to the Co-Pilot backend.
   * 
   * POST /api/copilot/chat
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
      // Get tenant and domain from context, fallback to demo values
      const requestTenantId = tenantId || 'demo-tenant';
      const requestDomain = domain || 'demo-domain';

      // Build request
      const request: CopilotRequest = {
        message: text.trim(),
        tenant_id: requestTenantId,
        domain: requestDomain,
        context: context || null,
      };

      // Call backend API
      const response: CopilotResponse = await sendCopilotChat(request);

      // Append assistant message with response
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        text: response.answer,
        meta: {
          answer_type: response.answer_type,
          citations: response.citations,
          raw_llm_trace_id: response.raw_llm_trace_id,
        },
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setLoading(false);
    } catch (err) {
      // Handle error
      const errorMessage = 'Co-Pilot is temporarily unavailable.';
      setError(errorMessage);
      
      // Append error message as assistant message
      const errorAssistantMessage: ChatMessage = {
        role: 'assistant',
        text: errorMessage,
        meta: {
          answer_type: 'UNKNOWN',
          citations: [],
        },
      };
      
      setMessages((prev) => [...prev, errorAssistantMessage]);
      setLoading(false);
    }
  };

  return {
    messages,
    setMessages,
    loading,
    error,
    sendMessage,
  };
}

