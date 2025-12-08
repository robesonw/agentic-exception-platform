# Phase 5 – AI Co-Pilot MVP  
Agentic Exception Processing Platform  
(SentinAI – Multi-Tenant, Domain-Abstraction Architecture)

---

## 1. Overview

Phase 5 introduces the **AI Co-Pilot** — a safe, read-only conversational assistant embedded into the platform UI.  
It allows users to ask natural-language questions about:

- Exceptions (detail, summary, analysis)
- Trends and operational patterns
- Domains and Domain Packs
- Policies and rules
- High-level recommendations

The Co-Pilot uses the **existing backend data sources** (exceptions, trends, domain packs, policy packs, audit logs) and a pluggable LLM layer to generate meaningful responses.

**Important:**  
👉 **Phase 5 is 100% read-only. NO actions can be taken by AI.**  
No approve/resolve/escalate/workflow execution is allowed yet.

This Phase prepares for Phase 6 (Actions & Playbooks) and Phase 7 (Admin / Guardrails).

---

## 2. Goals

### **Primary Goals**
1. Implement a safe, read-only AI Co-Pilot that:
   - Understands user questions about exceptions, trends, and policies.
   - Summarizes operational risk and exceptions.
   - Explains exception history and classification outcomes.
   - Suggests *non-destructive*, high-level recommendations.

2. Integrate Co-Pilot UI into the platform shell:
   - Available on all major pages (Exceptions, Detail, Supervisor, Config).

3. Provide grounding via:
   - Exception repository
   - Trend endpoints
   - Domain Packs / Policy Packs
   - Tenant metadata

4. Introduce an LLM abstraction that supports:
   - Swappable providers (OpenAI, Groq, Anthropic, Gemini, Grok, etc.)
   - Env-driven model selection
   - Domain- and tenant-aware routing (see `docs/phase5-llm-routing.md`)
   - Multi-provider fallback chains

### **Secondary Goals**
- Produce structured, auditable AI responses.
- Add logging & observability around Co-Pilot interactions.
- Prepare the pipeline for future action-driven agents.

---

## 3. In Scope (Phase 5)

### **Backend Features**
✔ New `src/llm` module:  
- `LLMClient` interface  
- `LLMResponse` dataclass  
- DummyLLM implementation  
- Provider factory with domain/tenant-aware routing (see `docs/phase5-llm-routing.md`)
- Multi-provider fallback chains
- Secret masking and prompt constraints

✔ New `src/copilot` module:
- `CopilotRequest`
- `CopilotResponse`
- `CopilotCitation`
- Intent classification (simple keyword-based)
- Co-Pilot Orchestrator

✔ Retrieval utilities:
- Load exceptions (latest N, by severity, by ID)
- Load domain packs & policy packs summaries
- Load exception timeline/fields

✔ REST API:
POST /api/copilot/chat
With:
```json
{
  "message": "Explain EX-12345",
  "tenant_id": "FinCo",
  "domain": "Capital Markets",
  "context": { }
}
✔ Guardrails:

Co-Pilot MUST NOT suggest or perform state-changing actions.

Co-Pilot MUST NOT output executable commands.

Co-Pilot MUST NOT impersonate any system agent.

✔ Logging:

Request message, tenant, domain

Exception ID(s) used

Answer type

Latency

Error events

4. Out of Scope (until Phase 6+)

❌ No “Approve Resolution”
❌ No “Run Playbook”
❌ No “Escalate”
❌ No action tools (email, workflow run, ticket creation)
❌ No edits to Domain Packs or Policy Packs
❌ No autonomous agent loops

Phase 5 is read-only.

5. Backend – Detailed Design
5.1 LLM Abstraction (src/llm)

LLMClient

class LLMClient(Protocol):
    async def generate(self, prompt: str, context: dict | None = None) -> LLMResponse:
        ...


LLMResponse

@dataclass
class LLMResponse:
    text: str
    raw: dict | None = None


Factory

The factory uses the LLM routing layer (see `docs/phase5-llm-routing.md` and `docs/phase5-llm-routing-usage.md`) to select providers based on domain and tenant configuration.

Configuration:
- Environment variables: LLM_PROVIDER, LLM_MODEL, LLM_API_KEY
- Optional routing config file: LLM_ROUTING_CONFIG_PATH
- Default: DummyLLMClient (safe fallback)

The Co-Pilot never calls providers directly—it always uses the routing layer.

5.2 Copilot Models (src/copilot/models.py)
class CopilotRequest(BaseModel):
    message: str
    tenant_id: str
    domain: str
    context: dict | None = None

class CopilotCitation(BaseModel):
    type: Literal["exception", "policy", "domain"]
    id: str

class CopilotResponse(BaseModel):
    answer: str
    answer_type: Literal["EXPLANATION", "SUMMARY", "POLICY_HINT", "UNKNOWN"]
    citations: list[CopilotCitation]
    raw_llm_trace_id: str | None

5.3 Copilot Orchestrator (src/copilot/orchestrator.py)

Responsibilities:

Classify user intent:

e.g., “today”, “summary”, “exceptions” → SUMMARY

“policy”, “rule”, “domain pack” → POLICY_HINT

“explain”, “why” + exception id → EXPLANATION

fallback → UNKNOWN

Gather relevant data:

If EX-123 → exception repository lookup

For summary → fetch last 24h exceptions by tenant/domain

For policy → find matching domain pack sections

Build prompt template:

You are the AI Co-Pilot for the SentinAI Exception Platform.
You ONLY describe, summarize, or explain.
You NEVER perform actions or propose system changes.
Use grounded factual data only.


Call LLMClient via routing layer: `load_llm_provider(domain=request.domain, tenant_id=request.tenant_id)`

Wrap LLM output into CopilotResponse

5.4 REST Endpoint
POST /api/copilot/chat


Example response:

{
  "answer": "Exception EX-12345 is a settlement mismatch related to a currency holiday.",
  "answer_type": "EXPLANATION",
  "citations": [
    { "type": "exception", "id": "EX-12345" }
  ],
  "raw_llm_trace_id": null
}

6. Frontend – Detailed Design
6.1 Component Architecture

Create:

ui/src/components/copilot/AICopilotDock.tsx
ui/src/components/copilot/MessageBubble.tsx (optional)
ui/src/hooks/useCopilotChat.ts (optional)

6.2 AICopilotDock Features

Floating Gemini-style AI button

Expandable docked chat window (bottom-right)

Scrollable chat history

Input field with send button

Quick suggestion chips

Uses backend /api/copilot/chat

Shows loading / error states

Displays citations if provided

6.3 TS Types
type CopilotResponse = {
  answer: string;
  answer_type: "EXPLANATION" | "SUMMARY" | "POLICY_HINT" | "UNKNOWN";
  citations: { type: string; id: string }[];
  raw_llm_trace_id?: string | null;
};

7. Prompt Template Used for LLM
You are the read-only AI Co-Pilot of the SentinAI Exception Platform.
You NEVER perform actions.
You NEVER approve, escalate, resolve, update, or modify state.
You ONLY summarize, describe, classify, explain, or highlight patterns.
If asked to perform an action, politely decline and explain the restriction.
Always use factual grounded data from retrieved context.
Tenant: {tenant_id}
Domain: {domain}

User Query:
{message}

Context:
{context_json}

8. Phase 5 Test Plan
Backend

Test /api/copilot/chat with:

simple message

exception id references

policy questions

invalid domain/tenant

Ensure guardrails trigger:

“approve this”

“escalate”

“delete”

“force settle”

etc.

Frontend

Chat window opens/closes cleanly

Messages append correctly

Loading state

Error state

Large responses wrap correctly

Citations appear if present

9. Phase 5 Exit Criteria

✔ Co-Pilot dock integrated globally
✔ Read-only conversational AI working end-to-end
✔ Backend LLM abstraction implemented
✔ Guardrails active (no system actions allowed)
✔ Logs for each conversation event
✔ UI is polished and stable

After this phase, the platform supports:
ChatGPT-style understanding + reasoning over exceptions.