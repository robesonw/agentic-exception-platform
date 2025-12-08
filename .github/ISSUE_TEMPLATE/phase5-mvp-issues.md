# Phase 5 MVP - GitHub Issues Checklist

## Component: LLM Abstraction Layer

### Issue P5-1: Implement LLMClient Interface and LLMResponse Dataclass
**Labels:** `component:llm`, `phase:5`, `priority:high`
**Description:**
- Create `src/llm/` module directory structure
- Define `LLMClient` Protocol interface with `generate` method signature
- Implement `LLMResponse` dataclass with `text` and optional `raw` fields
- Ensure type safety with proper type hints
- Reference: docs/phase5-copilot-mvp.md Section 5.1 (LLM Abstraction)

**Dependencies:** None (foundational issue)

**Acceptance Criteria:**
- [ ] `src/llm/` module directory created
- [ ] `LLMClient` Protocol interface defined with `generate` method
- [ ] `LLMResponse` dataclass implemented with `text: str` and `raw: dict | None` fields
- [ ] Type hints properly defined
- [ ] Unit tests for LLMClient interface and LLMResponse dataclass

---

### Issue P5-2: Implement DummyLLM Client for Testing and Development
**Labels:** `component:llm`, `phase:5`, `priority:high`
**Description:**
- Implement `DummyLLMClient` class that implements `LLMClient` Protocol
- Return mock responses for testing without actual LLM API calls
- Support configurable mock responses for different scenarios
- Add logging for dummy LLM calls
- Reference: docs/phase5-copilot-mvp.md Section 5.1 (LLM Abstraction - default: DummyLLMClient)

**Dependencies:** P5-1

**Acceptance Criteria:**
- [ ] `DummyLLMClient` class implemented
- [ ] Implements `LLMClient` Protocol correctly
- [ ] Returns mock `LLMResponse` objects
- [ ] Configurable mock responses supported
- [ ] Logging for dummy calls implemented
- [ ] Unit tests for DummyLLMClient

---

### Issue P5-3: Implement LLM Provider Factory with Environment-Driven Selection
**Labels:** `component:llm`, `phase:5`, `priority:high`
**Description:**
- Implement provider factory that reads `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` from environment variables
- Support provider selection: OpenAI, Groq, Anthropic, Gemini, Grok, etc.
- Create provider-specific client implementations (start with OpenAI and DummyLLM)
- Implement factory function that returns appropriate `LLMClient` instance
- Default to `DummyLLMClient` if no provider configured
- Reference: docs/phase5-copilot-mvp.md Section 5.1 (Factory - env: LLM_PROVIDER, LLM_MODEL, LLM_API_KEY)

**Dependencies:** P5-1, P5-2

**Acceptance Criteria:**
- [ ] Provider factory implemented
- [ ] Environment variables read correctly (`LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`)
- [ ] OpenAI client implementation (if provider is OpenAI)
- [ ] Factory returns appropriate `LLMClient` instance
- [ ] Defaults to `DummyLLMClient` when no provider configured
- [ ] Error handling for invalid provider configurations
- [ ] Unit tests for provider factory

---

## Component: Copilot Core Models

### Issue P5-4: Implement CopilotRequest and CopilotResponse Models
**Labels:** `component:copilot`, `phase:5`, `priority:high`
**Description:**
- Create `src/copilot/models.py` with Pydantic models
- Implement `CopilotRequest` with fields: `message: str`, `tenant_id: str`, `domain: str`, `context: dict | None`
- Implement `CopilotResponse` with fields: `answer: str`, `answer_type: Literal["EXPLANATION", "SUMMARY", "POLICY_HINT", "UNKNOWN"]`, `citations: list[CopilotCitation]`, `raw_llm_trace_id: str | None`
- Implement `CopilotCitation` with fields: `type: Literal["exception", "policy", "domain"]`, `id: str`
- Add validation for all models
- Reference: docs/phase5-copilot-mvp.md Section 5.2 (Copilot Models)

**Dependencies:** None (can be done in parallel)

**Acceptance Criteria:**
- [ ] `src/copilot/models.py` created
- [ ] `CopilotRequest` model implemented with all required fields
- [ ] `CopilotResponse` model implemented with all required fields
- [ ] `CopilotCitation` model implemented with all required fields
- [ ] Pydantic validation works correctly
- [ ] Type hints properly defined
- [ ] Unit tests for all models

---

## Component: Copilot Intent Classification

### Issue P5-5: Implement Simple Keyword-Based Intent Classification
**Labels:** `component:copilot`, `phase:5`, `priority:high`
**Description:**
- Implement intent classification function in `src/copilot/orchestrator.py`
- Classify user intents based on keywords:
  - "today", "summary", "exceptions" → SUMMARY
  - "policy", "rule", "domain pack" → POLICY_HINT
  - "explain", "why" + exception id → EXPLANATION
  - fallback → UNKNOWN
- Extract exception IDs from messages (e.g., "EX-12345")
- Return intent type and extracted parameters
- Reference: docs/phase5-copilot-mvp.md Section 5.3 (Classify user intent)

**Dependencies:** P5-4

**Acceptance Criteria:**
- [ ] Intent classification function implemented
- [ ] Keyword-based classification works for SUMMARY intent
- [ ] Keyword-based classification works for POLICY_HINT intent
- [ ] Keyword-based classification works for EXPLANATION intent (with exception ID extraction)
- [ ] UNKNOWN intent returned for unrecognized patterns
- [ ] Exception ID extraction from messages functional
- [ ] Unit tests for intent classification

---

## Component: Copilot Retrieval Utilities

### Issue P5-6: Implement Exception Retrieval Utilities
**Labels:** `component:copilot`, `phase:5`, `priority:high`
**Description:**
- Implement retrieval functions in `src/copilot/retrieval.py`:
  - Load exceptions by ID (single exception lookup)
  - Load latest N exceptions by tenant/domain
  - Load exceptions by severity for tenant/domain
- Integrate with existing exception repository
- Ensure tenant isolation in all retrieval operations
- Return formatted exception data for LLM context
- Reference: docs/phase5-copilot-mvp.md Section 3 (Retrieval utilities - Load exceptions)

**Dependencies:** Phase 1: Issue 18 (Status API Endpoint)

**Acceptance Criteria:**
- [ ] Exception retrieval utilities implemented
- [ ] Load exception by ID functional
- [ ] Load latest N exceptions functional
- [ ] Load exceptions by severity functional
- [ ] Tenant isolation enforced in all operations
- [ ] Exception data formatted for LLM context
- [ ] Unit tests for exception retrieval

---

### Issue P5-7: Implement Domain Pack and Policy Pack Retrieval Utilities
**Labels:** `component:copilot`, `phase:5`, `priority:high`
**Description:**
- Implement retrieval functions in `src/copilot/retrieval.py`:
  - Load domain pack summaries for tenant/domain
  - Load policy pack summaries for tenant
  - Load exception timeline/fields for specific exceptions
- Integrate with existing Domain Pack and Tenant Policy Pack storage
- Ensure tenant isolation in all retrieval operations
- Return formatted summaries for LLM context
- Reference: docs/phase5-copilot-mvp.md Section 3 (Retrieval utilities - Load domain packs & policy packs summaries)

**Dependencies:** Phase 2: Issue 22 (Domain Pack Loader and Validator)

**Acceptance Criteria:**
- [ ] Domain pack retrieval utilities implemented
- [ ] Policy pack retrieval utilities implemented
- [ ] Exception timeline/fields retrieval functional
- [ ] Tenant isolation enforced in all operations
- [ ] Summaries formatted for LLM context
- [ ] Unit tests for pack retrieval

---

## Component: Copilot Orchestrator

### Issue P5-8: Implement Copilot Orchestrator with Data Gathering and Prompt Building
**Labels:** `component:copilot`, `phase:5`, `priority:high`
**Description:**
- Implement `CopilotOrchestrator` class in `src/copilot/orchestrator.py`
- Responsibilities:
  - Classify user intent (use P5-5)
  - Gather relevant data based on intent (use P5-6, P5-7)
  - Build prompt template with grounded context
  - Call LLMClient to generate response
  - Wrap LLM output into CopilotResponse
- Implement prompt template with safety guardrails:
  - "You are the read-only AI Co-Pilot..."
  - "You NEVER perform actions..."
  - Include tenant, domain, message, and context in prompt
- Reference: docs/phase5-copilot-mvp.md Section 5.3 (Copilot Orchestrator), Section 7 (Prompt Template)

**Dependencies:** P5-3, P5-4, P5-5, P5-6, P5-7

**Acceptance Criteria:**
- [ ] `CopilotOrchestrator` class implemented
- [ ] Intent classification integrated
- [ ] Data gathering based on intent functional
- [ ] Prompt template built with safety guardrails
- [ ] LLMClient called correctly
- [ ] LLM output wrapped into CopilotResponse
- [ ] Citations populated correctly
- [ ] Unit tests for orchestrator

---

## Component: Copilot REST API

### Issue P5-9: Implement POST /api/copilot/chat Endpoint
**Labels:** `component:api`, `phase:5`, `priority:high`
**Description:**
- Create REST API endpoint `POST /api/copilot/chat` in `src/api/routes/router_copilot.py`
- Accept `CopilotRequest` in request body:
  - `message: str`
  - `tenant_id: str`
  - `domain: str`
  - `context: dict | None`
- Validate request body against CopilotRequest model
- Call CopilotOrchestrator to process request
- Return `CopilotResponse` in JSON format
- Add proper error handling and validation
- Ensure tenant isolation
- Reference: docs/phase5-copilot-mvp.md Section 3 (REST API: POST /api/copilot/chat), Section 5.4 (REST Endpoint)

**Dependencies:** P5-8

**Acceptance Criteria:**
- [ ] `POST /api/copilot/chat` endpoint implemented
- [ ] Request body validated against CopilotRequest model
- [ ] CopilotOrchestrator called correctly
- [ ] CopilotResponse returned in JSON format
- [ ] Error handling for invalid requests
- [ ] Tenant isolation enforced
- [ ] Integration tests for API endpoint

---

## Component: Copilot Guardrails

### Issue P5-10: Implement Read-Only Guardrails for Copilot Responses
**Labels:** `component:copilot`, `phase:5`, `priority:high`
**Description:**
- Implement guardrail checks in CopilotOrchestrator or separate guardrail module
- Ensure Co-Pilot MUST NOT suggest or perform state-changing actions
- Ensure Co-Pilot MUST NOT output executable commands
- Ensure Co-Pilot MUST NOT impersonate any system agent
- Filter/validate LLM responses for action keywords (approve, escalate, resolve, delete, force, etc.)
- Return safe responses that decline action requests
- Reference: docs/phase5-copilot-mvp.md Section 3 (Guardrails)

**Dependencies:** P5-8

**Acceptance Criteria:**
- [ ] Guardrail checks implemented
- [ ] State-changing action suggestions blocked
- [ ] Executable command outputs blocked
- [ ] System agent impersonation blocked
- [ ] Action keywords detected and filtered
- [ ] Safe decline responses generated
- [ ] Guardrail violations logged
- [ ] Unit tests for guardrails

---

## Component: Copilot Logging and Observability

### Issue P5-11: Implement Copilot Interaction Logging
**Labels:** `component:copilot`, `phase:5`, `priority:high`
**Description:**
- Implement comprehensive logging for all Copilot interactions
- Log the following for each request:
  - Request message, tenant, domain
  - Exception ID(s) used (if any)
  - Answer type (EXPLANATION, SUMMARY, POLICY_HINT, UNKNOWN)
  - Latency (time to generate response)
  - Error events (if any)
- Store logs in structured format (JSON)
- Integrate with existing audit/observability system
- Ensure tenant-scoped logging
- Reference: docs/phase5-copilot-mvp.md Section 3 (Logging)

**Dependencies:** P5-9

**Acceptance Criteria:**
- [ ] Copilot interaction logging implemented
- [ ] All required fields logged for each request
- [ ] Latency tracking functional
- [ ] Error events logged
- [ ] Structured logging format (JSON)
- [ ] Integration with audit/observability system
- [ ] Tenant-scoped logging enforced
- [ ] Unit tests for logging

---

## Component: Frontend - Copilot UI Foundation

### Issue UI-P5-1: Create AICopilotDock Component with Floating Button and Chat Window
**Labels:** `component:ui:copilot`, `phase:5`, `priority:high`
**Description:**
- Create `ui/src/components/copilot/AICopilotDock.tsx` component
- Implement floating Gemini-style AI button (bottom-right corner)
- Implement expandable docked chat window that opens from button
- Chat window features:
  - Scrollable chat history
  - Input field with send button
  - Quick suggestion chips (optional)
- Use MUI components for styling
- Make component globally available (integrate into AppLayout)
- Reference: docs/phase5-copilot-mvp.md Section 6.1 (Component Architecture), Section 6.2 (AICopilotDock Features)

**Dependencies:** Phase 4: UI-A2 (AppLayout), UI-A2 (MUI Theme)

**Acceptance Criteria:**
- [ ] AICopilotDock component created
- [ ] Floating AI button renders in bottom-right corner
- [ ] Chat window expands/collapses from button
- [ ] Scrollable chat history functional
- [ ] Input field with send button works
- [ ] Quick suggestion chips displayed (optional)
- [ ] Component integrated into AppLayout
- [ ] Responsive design works on mobile/tablet

---

### Issue UI-P5-2: Implement Copilot Chat API Integration and State Management
**Labels:** `component:ui:copilot`, `phase:5`, `priority:high`
**Description:**
- Create API client function in `ui/src/api/copilot.ts`:
  - `sendCopilotMessage(message: string, tenantId: string, domain: string, context?: object)`
- Create TanStack Query hook `useCopilotChat` in `ui/src/hooks/useCopilotChat.ts`
- Implement chat state management:
  - Message history (user messages + AI responses)
  - Loading state during API calls
  - Error state handling
- Wire AICopilotDock to use `useCopilotChat` hook
- Reference: docs/phase5-copilot-mvp.md Section 6.1 (useCopilotChat hook), Section 6.3 (TS Types)

**Dependencies:** Phase 4: UI-A5 (HTTP Client), UI-A13 (TanStack Query), UI-P5-1

**Acceptance Criteria:**
- [ ] Copilot API client function created
- [ ] `useCopilotChat` hook implemented
- [ ] Chat state management functional (history, loading, error)
- [ ] AICopilotDock integrated with hook
- [ ] Messages sent to `POST /api/copilot/chat` API
- [ ] Responses displayed in chat history
- [ ] Loading state shows during API calls
- [ ] Error handling displays error messages

---

### Issue UI-P5-3: Implement CopilotResponse TypeScript Types
**Labels:** `component:ui:copilot`, `phase:5`, `priority:high`
**Description:**
- Define TypeScript types in `ui/src/types/copilot.ts`:
  - `CopilotRequest` type matching backend model
  - `CopilotResponse` type with fields: `answer`, `answer_type`, `citations`, `raw_llm_trace_id`
  - `CopilotCitation` type with fields: `type`, `id`
- Ensure types match backend API response schemas exactly
- Reference: docs/phase5-copilot-mvp.md Section 6.3 (TS Types)

**Dependencies:** Phase 4: UI-A11 (TypeScript Types)

**Acceptance Criteria:**
- [ ] Copilot TypeScript types defined
- [ ] Types match backend API response schemas
- [ ] CopilotRequest type matches backend model
- [ ] CopilotResponse type matches backend model
- [ ] CopilotCitation type matches backend model
- [ ] TypeScript compiles without errors

---

### Issue UI-P5-4: Implement Citation Display in Chat Messages
**Labels:** `component:ui:copilot`, `phase:5`, `priority:high`
**Description:**
- Enhance AICopilotDock to display citations when present in CopilotResponse
- Show citations as clickable links or badges below AI messages
- Citation types: "exception", "policy", "domain"
- For exception citations: Link to exception detail page (`/exceptions/{id}`)
- For policy/domain citations: Display citation info (read-only in Phase 5)
- Use MUI components for citation display
- Reference: docs/phase5-copilot-mvp.md Section 6.2 (Displays citations if provided)

**Dependencies:** UI-P5-1, UI-P5-2, UI-P5-3

**Acceptance Criteria:**
- [ ] Citations displayed when present in responses
- [ ] Citations shown as clickable links or badges
- [ ] Exception citations link to detail page
- [ ] Policy/domain citations display info
- [ ] Citation styling matches design system
- [ ] Citations responsive on mobile/tablet

---

### Issue UI-P5-5: Implement MessageBubble Component (Optional)
**Labels:** `component:ui:copilot`, `phase:5`, `priority:medium`
**Description:**
- Create `ui/src/components/copilot/MessageBubble.tsx` component (optional)
- Display individual chat messages (user and AI) with proper styling
- User messages: Right-aligned, distinct styling
- AI messages: Left-aligned, distinct styling
- Support markdown formatting in AI responses (optional)
- Use MUI components for styling
- Reference: docs/phase5-copilot-mvp.md Section 6.1 (MessageBubble optional)

**Dependencies:** UI-P5-1

**Acceptance Criteria:**
- [ ] MessageBubble component created (optional)
- [ ] User messages styled correctly (right-aligned)
- [ ] AI messages styled correctly (left-aligned)
- [ ] Markdown formatting supported (optional)
- [ ] Component reusable for all messages
- [ ] Responsive design works

---

## Component: Testing

### Issue P5-12: Implement Backend Tests for Copilot API
**Labels:** `component:testing`, `phase:5`, `priority:high`
**Description:**
- Write integration tests for `POST /api/copilot/chat` endpoint:
  - Test with simple messages
  - Test with exception ID references (e.g., "Explain EX-12345")
  - Test with policy questions
  - Test with invalid domain/tenant
- Test guardrails:
  - Test that "approve this" requests are blocked
  - Test that "escalate" requests are blocked
  - Test that "delete" requests are blocked
  - Test that "force settle" requests are blocked
- Ensure all guardrails trigger correctly
- Reference: docs/phase5-copilot-mvp.md Section 8 (Phase 5 Test Plan - Backend)

**Dependencies:** P5-9, P5-10

**Acceptance Criteria:**
- [ ] Integration tests for copilot API endpoint
- [ ] Tests cover simple messages, exception IDs, policy questions
- [ ] Tests cover invalid domain/tenant scenarios
- [ ] Guardrail tests verify action blocking
- [ ] All tests pass
- [ ] Test coverage >80% for copilot module

---

### Issue UI-P5-6: Implement Frontend Tests for Copilot UI
**Labels:** `component:ui:testing`, `phase:5`, `priority:high`
**Description:**
- Write component tests for AICopilotDock:
  - Test chat window opens/closes cleanly
  - Test messages append correctly
  - Test loading state displays
  - Test error state displays
  - Test large responses wrap correctly
  - Test citations appear if present
- Write integration tests for copilot chat flow
- Reference: docs/phase5-copilot-mvp.md Section 8 (Phase 5 Test Plan - Frontend)

**Dependencies:** UI-P5-1, UI-P5-2, UI-P5-4

**Acceptance Criteria:**
- [ ] Component tests for AICopilotDock
- [ ] Tests cover all UI interactions
- [ ] Integration tests for chat flow
- [ ] All tests pass
- [ ] Test coverage >80% for copilot components

---

## Summary

**Total Issues:** 18
**High Priority:** 16
**Medium Priority:** 2
**Low Priority:** 0

**Components Covered:**
- LLM Abstraction Layer (3 issues)
- Copilot Core Models (1 issue)
- Copilot Intent Classification (1 issue)
- Copilot Retrieval Utilities (2 issues)
- Copilot Orchestrator (1 issue)
- Copilot REST API (1 issue)
- Copilot Guardrails (1 issue)
- Copilot Logging and Observability (1 issue)
- Frontend - Copilot UI Foundation (5 issues)
- Testing (2 issues)

**Phase 5 Milestones (from docs/phase5-copilot-mvp.md):**
- Co-Pilot dock integrated globally
- Read-only conversational AI working end-to-end
- Backend LLM abstraction implemented
- Guardrails active (no system actions allowed)
- Logs for each conversation event
- UI is polished and stable

**Key Phase 5 Focus Areas:**
1. **LLM Integration**: Abstract LLM provider layer with swappable providers (OpenAI, Groq, Anthropic, Gemini, Grok, etc.)
2. **Read-Only Co-Pilot**: Safe conversational assistant that only describes, summarizes, explains - NO actions
3. **Intent Classification**: Simple keyword-based classification for SUMMARY, POLICY_HINT, EXPLANATION, UNKNOWN
4. **Data Grounding**: Retrieve exceptions, domain packs, policy packs for context-aware responses
5. **Guardrails**: Strict enforcement that Co-Pilot cannot suggest or perform actions
6. **UI Integration**: Floating AI button with expandable chat window integrated into platform shell
7. **Observability**: Comprehensive logging of all Co-Pilot interactions

**Spec References:**
- docs/phase5-copilot-mvp.md - Phase 5 AI Co-Pilot MVP specification
- docs/10-ui-guidelines.md - UI working principles and tech stack
- docs/03-data-models-apis.md - Backend API schemas and data models

