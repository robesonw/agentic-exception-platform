# Agentic Exception Processing Platform - Technical Documentation

## Executive Summary

The **Agentic Exception Processing Platform** is an enterprise-grade, domain-abstracted AI platform designed for multi-tenant exception processing across diverse business domains. Built on a foundation of configurable Domain Packs and Tenant Policy Packs, the platform provides intelligent exception handling through a multi-agent orchestration pipeline.

### Key Capabilities

- **Multi-Tenant Architecture:** Strict isolation of data, memory, tools, and configurations per tenant
- **Domain Abstraction:** Zero hardcoding - all behavior driven by Domain Packs and Tenant Policy Packs
- **Intelligent Agent Pipeline:** 5 core agents (Intake, Triage, Policy, Resolution, Feedback) + optional SupervisorAgent
- **LLM-Enhanced Reasoning:** All agents enhanced with explainable LLM reasoning, safe JSON outputs, and fallback strategies
- **Advanced RAG System:** Production vector database with hybrid semantic search
- **Robust Tool Execution:** Circuit breakers, retries, timeouts, and comprehensive error handling
- **Human-in-the-Loop:** Complete approval workflow for high-severity actions
- **Rich Observability:** Real-time metrics, dashboards, alerts, notifications, SLO/SLA monitoring
- **Admin Management:** Full CRUD operations for Domain Packs, Tenant Policies, and Tools
- **Testing Infrastructure:** Multi-domain simulation, automated test suite execution, red-team testing
- **Streaming Capabilities:** Kafka/MQ ingestion, incremental decision streaming, backpressure control
- **Autonomous Optimization:** Policy learning, playbook optimization, guardrail recommendations with human-in-loop approval
- **Explainability:** Human-readable decision timelines, evidence tracking, explanation APIs
- **Safety & Security:** Expanded safety rules, red-team test harness, policy violation detection, adversarial test suites
- **Scale Readiness:** Hardening for many domains/tenants, SLO/SLA metrics, tenancy-aware quotas, operational runbooks

### Business Value

- **80%+ Auto-Resolution Rate:** Automated handling of routine exceptions
- **Reduced MTTR:** Mean Time To Resolution significantly improved through intelligent routing
- **Domain Flexibility:** Support for finance, healthcare, manufacturing, and more without code changes
- **Compliance Ready:** Full audit trails, tenant isolation, human approval workflows, and regulatory compliance testing
- **Scalable Architecture:** Handles thousands of exceptions per second across multiple tenants
- **Explainable AI:** Natural language explanations for all agent decisions, enabling trust and compliance
- **Continuous Learning:** Autonomous optimization of policies, playbooks, and guardrails based on outcomes
- **Real-Time Visibility:** Streaming updates and comprehensive dashboards for operational awareness

---

## Enterprise Architecture

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         External Sources                                 │
│  (Logs, DBs, APIs, Queues, Files, Event Streams)                        │
└──────────────────────────────┬──────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Gateway / Tenant Router                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  • Authentication (JWT/API Keys)                                 │  │
│  │  • Tenant Identification & Routing                              │  │
│  │  • Rate Limiting (per tenant)                                    │  │
│  │  • API Versioning                                                │  │
│  │  • Security Audit Logging                                        │  │
│  │  • Phase 3: Quota Enforcement                                    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                │                               │
                ▼                               ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│  REST Ingestion (Batch)      │  │  Streaming Ingestion (Phase 3)│
│  • POST /exceptions/{id}     │  │  • Kafka/MQ Consumer         │
│  • Batch Processing          │  │  • Real-time Processing   │
└───────────────┬──────────────┘  └──────────────┬───────────────┘
                │                                 │
                └───────────────┬─────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              Exception Ingestion Service                                 │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  • REST API Endpoint (POST /exceptions/{tenantId})              │  │
│  │  • Streaming Ingestion (Kafka/MQ) - Phase 3                      │  │
│  │  • Raw Payload Parsing                                           │  │
│  │  • Canonical Schema Normalization                                │  │
│  │  • Field Extraction (tenantId, sourceSystem, timestamp, etc.)   │  │
│  │  • Schema Validation                                             │  │
│  │  • Phase 3: Backpressure Control                                 │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Agent Orchestrator                                    │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Orchestrates Sequential Agent Pipeline:                          │  │
│  │                                                                   │  │
│  │  1. IntakeAgent ──► Normalize & Extract                          │  │
│  │  2. TriageAgent ──► Classify & Score (Phase 3: LLM Reasoning)    │  │
│  │  3. PolicyAgent ───► Enforce Guardrails (Phase 3: LLM Reasoning) │  │
│  │  4. ResolutionAgent ──► Execute Playbooks (Phase 3: LLM Reasoning)│  │
│  │  5. FeedbackAgent ──► Learn & Update Memory                      │  │
│  │                                                                   │  │
│  │  Optional: SupervisorAgent ──► Oversight (Phase 3: LLM Reasoning)│  │
│  │                                                                   │  │
│  │  Features:                                                        │  │
│  │  • Parallel execution support                                    │  │
│  │  • Conditional branching                                         │  │
│  │  • Retry logic & error recovery                                  │  │
│  │  • State management                                              │  │
│  │  • Phase 3: LLM Fallback Strategies                             │  │
│  │  • Phase 3: Incremental Decision Streaming                       │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                │                               │
                ▼                               ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│    Supporting Subsystems     │  │    Supporting Subsystems     │
│                              │  │                              │
│  • Tool Registry             │  │  • Memory Layer (RAG)        │
│  • Execution Engine          │  │  • Vector Store              │
│  • Approval Workflow         │  │  • Embedding Provider        │
│  • Notification Service      │  │  • Semantic Search           │
│  • Phase 3: LLM Client       │  │  • Phase 3: Evidence Tracking│
│  • Phase 3: Safety Rules     │  │  • Phase 3: Decision Timelines│
│  • Phase 3: Quota Enforcer   │  │                              │
└──────────────────────────────┘  └──────────────────────────────┘
                │                               │
                └───────────────┬───────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              Phase 3: Learning & Optimization                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  • Policy Learning with Outcome Analysis                         │  │
│  │  • Severity Rule Recommender                                     │  │
│  │  • Playbook Recommender & Optimizer                              │  │
│  │  • Guardrail Recommender                                         │  │
│  │  • Unified Optimization Engine                                   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────────┘
                │                               │
                └───────────────┬───────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              Audit & Observability System                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  • Audit Trail Logging (all decisions/actions)                   │  │
│  │  • Metrics Collection (Prometheus format)                        │  │
│  │  • Real-time Dashboards                                          │  │
│  │  • Alert Rules & Escalation                                      │  │
│  │  • Notification Service (Email/Slack/Webhooks)                   │  │
│  │  • Phase 3: SLO/SLA Monitoring                                   │  │
│  │  • Phase 3: Explanation Analytics                                 │  │
│  │  • Phase 3: Quality Scoring                                     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Admin UI / API                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  • Domain Pack Management (CRUD, versioning, rollback)           │  │
│  │  • Tenant Policy Pack Management                                 │  │
│  │  • Tool Management                                               │  │
│  │  • Approval UI                                                   │  │
│  │  • Dashboard APIs                                                │  │
│  │  • Phase 3: Operator UI APIs (browsing, NLQ, simulation)          │  │
│  │  • Phase 3: Supervisor Dashboard APIs                            │  │
│  │  • Phase 3: Configuration Viewing & Diffing APIs                   │  │
│  │  • Phase 3: Explanation APIs                                     │  │
│  │  • Phase 3: Guardrail Recommendation APIs                       │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow Architecture

```
┌──────────────┐
│   External   │
│   Exception  │
└──────┬───────┘
       │
       ▼
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐
│   Gateway        │────►│  Ingestion   │────►│ Orchestrator │
│   (Auth/Route)   │     │  (Normalize) │     │   (Pipeline)  │
└─────────────────┘     └──────────────┘     └──────┬───────┘
                                                     │
         ┌──────────────────────────────────────────┼────────────┐
         │                                          │            │
         ▼                                          ▼            ▼
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐
│  IntakeAgent    │────►│ TriageAgent  │────►│ PolicyAgent   │
│  (Normalize)    │     │ (Classify)   │     │ (Guardrails)  │
└─────────────────┘     └──────┬───────┘     └──────┬───────┘
                               │                     │
                               ▼                     ▼
                    ┌─────────────────┐     ┌──────────────┐
                    │  RAG Query      │     │ Approval      │
                    │  (Similar Cases)│     │ Queue        │
                    └─────────────────┘     └──────────────┘
                               │                     │
                               └──────────┬──────────┘
                                          │
                                          ▼
                              ┌─────────────────┐
                              │ ResolutionAgent │
                              │ (Execute Tools) │
                              └────────┬────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                   │
                    ▼                  ▼                   ▼
         ┌─────────────────┐  ┌──────────────┐  ┌──────────────┐
         │ Tool Execution  │  │  Feedback    │  │   Audit      │
         │    Engine       │  │   Agent      │  │   Logger     │
         └─────────────────┘  └──────┬───────┘  └──────────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │  Update RAG     │
                            │  (Memory)       │
                            └─────────────────┘
```

### Multi-Tenant Isolation Model

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Tenant A                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ Domain Pack  │  │ Tenant Policy│  │ Vector Store │             │
│  │  (Finance)   │  │     Pack     │  │  Collection  │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ Tool Registry│  │ Approval     │  │ Metrics      │             │
│  │  (Isolated)  │  │   Queue      │  │  (Isolated)  │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        Tenant B                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ Domain Pack  │  │ Tenant Policy│  │ Vector Store │             │
│  │ (Healthcare) │  │     Pack     │  │  Collection  │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ Tool Registry│  │ Approval     │  │ Metrics      │             │
│  │  (Isolated)  │  │   Queue      │  │  (Isolated)  │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────┐
                    │  Shared Core     │
                    │  Infrastructure  │
                    │  (Orchestrator,  │
                    │   API Gateway)   │
                    └──────────────────┘
```

---

## Agents Subsystem

### Agent Architecture

The platform employs a **multi-agent orchestration model** where specialized agents process exceptions through a sequential pipeline. Each agent follows a standardized contract and makes decisions based on Domain Packs and Tenant Policy Packs.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Agent Pipeline                                │
└─────────────────────────────────────────────────────────────────────┘

Exception ──► [IntakeAgent] ──► [TriageAgent] ──► [PolicyAgent] ──►
                                                      │
                                                      ├─► [Approval Queue]
                                                      │   (if required)
                                                      │
                                                      ▼
                                    [ResolutionAgent] ──► [FeedbackAgent]
                                                              │
                                                              ▼
                                                          [RAG Update]
```

### Agent Details

#### 1. IntakeAgent
**Location:** `src/agents/intake.py`

**Responsibilities:**
- Normalize raw exception payloads to canonical schema
- Extract required fields: `tenantId`, `sourceSystem`, `timestamp`, `rawPayload`
- Infer `exceptionType` from Domain Pack taxonomy if possible
- Validate schema compliance

**Input:**
```json
{
  "rawPayload": {...},
  "sourceSystem": "ERP",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Output:**
```json
{
  "decision": "Normalized",
  "confidence": 0.95,
  "evidence": ["Extracted tenantId: TENANT_001", "Inferred exceptionType: SETTLEMENT_FAIL"],
  "nextStep": "ProceedToTriage",
  "exceptionRecord": {
    "exceptionId": "exc_123",
    "tenantId": "TENANT_001",
    "exceptionType": "SETTLEMENT_FAIL",
    ...
  }
}
```

**Key Features:**
- LLM-powered normalization
- Domain Pack taxonomy matching
- Schema validation
- Error handling for malformed inputs

---

#### 2. TriageAgent
**Location:** `src/agents/triage.py`

**Phase 3 Enhancement:** LLM-augmented with explainable reasoning (P3-1)

**Responsibilities:**
- Classify exception type using Domain Pack taxonomy
- Score severity using Domain Pack severity rules
- Query RAG for similar historical exceptions
- Generate diagnostic summary
- Calculate confidence based on match strength
- **Phase 3:** Provide natural language explanations for classification and severity decisions
- **Phase 3:** Structured reasoning output with evidence chains
- **Phase 3:** Explainable confidence scoring with reasoning breakdown

**Input:**
- Normalized exception record
- Domain Pack (for taxonomy and severity rules)
- RAG index (for similarity search)

**Output:**
```json
{
  "decision": "Triaged SETTLEMENT_FAIL HIGH",
  "confidence": 0.88,
  "evidence": [
    "Matched severity rule: HIGH for SETTLEMENT_FAIL",
    "Found 3 similar cases in RAG",
    "Root cause: Network timeout in settlement service"
  ],
  "nextStep": "ProceedToPolicy",
  "severity": "HIGH",
  "diagnosticSummary": "Settlement failure due to network timeout..."
}
```

**Key Features:**
- RAG-powered similarity search
- Severity rule matching
- Root cause analysis
- Diagnostic summary generation
- **Phase 3:** LLM-enhanced reasoning with natural language explanations
- **Phase 3:** Evidence chain documentation (which rules matched, which RAG results influenced)
- **Phase 3:** Fallback to rule-based logic when LLM unavailable

---

#### 3. PolicyAgent
**Location:** `src/agents/policy.py`

**Phase 3 Enhancement:** LLM-augmented with rule explanation (P3-2)

**Responsibilities:**
- Evaluate triage output against Tenant Policy Pack guardrails
- Check allow-lists and block-lists
- Apply human approval rules based on severity
- Approve or block suggested actions
- Route to approval queue if required
- **Phase 3:** Provide natural language explanations for guardrail decisions
- **Phase 3:** Explain which specific rules and policies influenced decisions
- **Phase 3:** Generate human-readable policy violation reports
- **Phase 3:** Policy violation detection and automatic blocking

**Input:**
- TriageAgent output
- Tenant Policy Pack (guardrails, allow-lists, approval rules)

**Output:**
```json
{
  "decision": "APPROVED" | "BLOCKED" | "PENDING_APPROVAL",
  "confidence": 0.92,
  "evidence": [
    "Tool 'retry_settlement' is in allow-list",
    "Severity HIGH requires human approval per policy",
    "Confidence 0.88 exceeds threshold 0.85"
  ],
  "nextStep": "ProceedToResolution" | "SubmitForApproval" | "Escalate",
  "approvedActions": ["retry_settlement"],
  "requiresApproval": true
}
```

**Key Features:**
- Guardrail enforcement
- Allow-list/block-list validation
- Human approval routing
- Policy rule evaluation
- Integration with approval workflow
- **Phase 3:** LLM-enhanced reasoning explaining guardrail applications
- **Phase 3:** Tenant-specific policy explanations
- **Phase 3:** Integration with violation detection system

---

#### 4. ResolutionAgent
**Location:** `src/agents/resolution.py`

**Phase 3 Enhancement:** LLM-augmented with action explanation (P3-3)

**Responsibilities:**
- Select playbook from Domain/Tenant Packs matching exception type
- Execute playbook steps sequentially
- Invoke approved tools via Tool Execution Engine
- Handle partial automation for non-critical actions
- Update resolution status
- Support rollback on failure
- **Phase 3:** Provide natural language explanations for playbook selection
- **Phase 3:** Explain tool execution order and dependencies
- **Phase 3:** Generate action summaries with reasoning for operators

**Input:**
- PolicyAgent output
- Domain Pack (playbooks)
- Tenant Policy Pack (approved tools)
- Tool Registry

**Output:**
```json
{
  "decision": "RESOLVED" | "PARTIAL" | "FAILED",
  "confidence": 0.90,
  "evidence": [
    "Selected playbook: retry_settlement_v2",
    "Tool 'retry_settlement' executed successfully",
    "Settlement retry completed in 2.3s"
  ],
  "nextStep": "ProceedToFeedback",
  "resolutionStatus": "RESOLVED",
  "executedSteps": [
    {"step": 1, "action": "retry_settlement", "status": "SUCCESS"},
    {"step": 2, "action": "verify_settlement", "status": "SUCCESS"}
  ]
}
```

**Key Features:**
- Playbook selection and execution
- Tool invocation with retry/timeout
- Partial automation support
- Step-by-step execution tracking
- Rollback on failure
- Integration with Tool Execution Engine
- **Phase 3:** LLM-enhanced reasoning for playbook and tool selection
- **Phase 3:** Playbook rejection reasons explained when applicable
- **Phase 3:** Evidence tracking for tool outputs

---

#### 5. FeedbackAgent
**Location:** `src/agents/feedback.py`

**Responsibilities:**
- Capture resolution outcome
- Compare actual vs expected results
- Update RAG index with new exception/resolution pair
- Detect patterns for playbook improvements
- Generate learning insights

**Input:**
- ResolutionAgent output
- Exception record with resolution status
- RAG index

**Output:**
```json
{
  "decision": "LEARNED",
  "confidence": 0.85,
  "evidence": [
    "Resolution successful: settlement retry worked",
    "Added to RAG index with embedding",
    "Pattern detected: network timeouts resolve with retry"
  ],
  "nextStep": "Complete",
  "ragUpdated": true,
  "patternsDetected": ["network_timeout_retry_pattern"]
}
```

**Key Features:**
- RAG index updates
- Pattern detection
- Learning from outcomes
- Integration with Policy Learning

---

#### 6. SupervisorAgent (Optional)
**Location:** `src/agents/supervisor.py`

**Phase 3 Enhancement:** LLM-augmented with oversight reasoning (P3-4)

**Responsibilities:**
- Oversee entire pipeline for safety
- Review agent decisions for consistency
- Intervene if confidence chain is too low
- Override decisions if policy breach detected
- Escalate to human if needed
- **Phase 3:** Provide natural language explanations for oversight decisions
- **Phase 3:** Explain anomaly detection and escalation rationale
- **Phase 3:** Generate supervisor decision summaries with evidence

**Input:**
- All agent outputs
- Tenant Policy Pack
- Domain Pack

**Output:**
```json
{
  "decision": "APPROVED_FLOW" | "INTERVENED" | "ESCALATE",
  "confidence": 0.95,
  "evidence": [
    "All agents within confidence thresholds",
    "No policy breaches detected",
    "Pipeline flow approved"
  ],
  "nextStep": "Continue" | "Escalate",
  "interventions": []
}
```

**Key Features:**
- Pipeline oversight
- Decision review
- Override capability
- Escalation support
- **Phase 3:** LLM-enhanced reasoning for oversight decisions
- **Phase 3:** Intervention rationale documentation
- **Phase 3:** Anomaly detection explanations

---

### Agent Communication Contracts

All agents communicate via standardized contracts defined in `src/models/agent_contracts.py`:

```python
class AgentDecision(BaseModel):
    decision: str  # Agent's decision/classification
    confidence: float  # Confidence score (0.0-1.0)
    evidence: list[str]  # Supporting evidence
    nextStep: str  # Next step in pipeline
    details: dict[str, Any]  # Additional context
```

---

## LLM Integration Subsystem (Phase 3)

### Architecture Overview

Phase 3 introduces comprehensive LLM integration across all agents, providing explainable reasoning while maintaining safety and reliability.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LLM Integration Layer                            │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  LLM Client  │────►│  Schema      │────►│  Validation  │
│  (Provider)  │     │  Registry    │     │  & Sanitize   │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                   │
                ┌──────────────────────────────────┼────────────┐
                │                                  │            │
                ▼                                  ▼            ▼
        ┌──────────┐                      ┌──────────┐  ┌──────────┐
        │ Fallback │                      │ Circuit  │  │  Safety  │
        │ Strategy │                      │ Breaker  │  │  Rules   │
        └──────────┘                      └──────────┘  └──────────┘
                │                                  │            │
                └──────────────────────────────────┼────────────┘
                                                   │
                                                   ▼
                                         ┌──────────────┐
                                         │   Agent      │
                                         │   Reasoning  │
                                         └──────────────┘
```

### Components

#### 1. LLM Client
**Location:** `src/llm/provider.py`

**Responsibilities:**
- Provider-agnostic LLM interface (OpenAI, Grok, etc.)
- Schema-aware JSON generation
- Tenant-aware configuration
- Token and cost tracking
- Integration with safety rules and quotas

**Key Classes:**
- `LLMClient` (interface)
- `LLMClientImpl` (implementation)
- `LLMProvider` (provider abstraction)

**Features:**
- **Schema Validation:** All outputs validated against Pydantic models
- **Tenant Awareness:** Per-tenant model/tuning support (future)
- **Usage Tracking:** Token counts and cost estimation
- **Safety Integration:** Pre-call safety checks and post-call usage recording
- **Quota Enforcement:** Integration with quota enforcer

---

#### 2. LLM Output Schemas
**Location:** `src/llm/schemas.py`

**Responsibilities:**
- Define structured output schemas for all agents
- Provide schema registry for validation
- Support reasoning steps, evidence references, and natural language summaries

**Key Schemas:**
- `TriageLLMOutput`: Classification and severity reasoning
- `PolicyLLMOutput`: Guardrail and policy decision reasoning
- `ResolutionLLMOutput`: Playbook and tool execution reasoning
- `SupervisorLLMOutput`: Oversight and intervention reasoning
- `NLQAnswer`: Natural language query responses

**Features:**
- Structured reasoning fields (`reasoning_steps[]`, `evidence_references[]`)
- Confidence scores with explanations
- Natural language summaries
- Evidence attribution

---

#### 3. LLM Validation and Sanitization
**Location:** `src/llm/validation.py`

**Responsibilities:**
- Parse and validate LLM JSON outputs
- Sanitize outputs (strip unknown fields, clamp values)
- Fallback JSON parsing for malformed responses
- Error reporting with detailed diagnostics

**Key Functions:**
- `validate_llm_output()`: Schema validation
- `sanitize_llm_output()`: Output cleaning
- `LLMValidationError`: Detailed error reporting

**Features:**
- Robust JSON parsing (handles extra text around JSON)
- Field stripping and value clamping
- Safe defaults for missing required fields
- Comprehensive error logging

---

#### 4. LLM Fallback Strategies
**Location:** `src/llm/fallbacks.py`

**Responsibilities:**
- Implement fallback to rule-based logic when LLM fails
- Circuit breaker pattern for persistent failures
- Retry logic with exponential backoff
- Timeout handling per agent

**Key Classes:**
- `LLMFallbackPolicy`: Configuration for fallback behavior
- `CircuitBreaker`: Circuit breaker state management
- `call_with_fallback()`: Main fallback orchestration function

**Features:**
- **Timeout Handling:** Configurable timeouts per agent
- **Retry Logic:** Exponential backoff with jitter
- **Circuit Breaker:** CLOSED → OPEN → HALF_OPEN transitions
- **Rule-Based Fallback:** Automatic fallback to deterministic logic
- **Audit Logging:** All fallback events logged

---

## RAG / Memory Subsystem

### Architecture Overview

The RAG (Retrieval-Augmented Generation) subsystem provides intelligent memory for the platform, enabling agents to learn from historical exceptions and resolutions.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RAG / Memory Subsystem                            │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Exception   │────►│ Embedding    │────►│ Vector Store │
│   Record     │     │  Provider    │     │  (Qdrant)    │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
                                                  ▼
                                         ┌──────────────┐
                                         │  Semantic     │
                                         │   Search      │
                                         └──────┬───────┘
                                                │
                                                ▼
                                         ┌──────────────┐
                                         │  Similar     │
                                         │  Exceptions  │
                                         │  + Resolutions│
                                         └──────────────┘
```

### Components

#### 1. Embedding Provider
**Location:** `src/memory/embeddings.py`

**Responsibilities:**
- Generate embeddings for exception records
- Support multiple embedding providers (OpenAI, HuggingFace, etc.)
- Embedding caching to reduce API costs
- Quality metrics and validation
- Custom models per tenant

**Key Classes:**
- `EmbeddingProvider` (abstract interface)
- `OpenAIEmbeddingProvider`
- `HFEmbeddingProvider` (stub)
- `EmbeddingCache` (LRU + disk)

**Features:**
- Batch embedding generation
- Dimension configuration
- Tenant-specific provider config
- Cache hit rate tracking

---

#### 2. Vector Store
**Location:** `src/memory/vector_store.py`

**Responsibilities:**
- Persistent vector storage (Qdrant integration)
- Per-tenant namespace/collection isolation
- Vector point upsert and deletion
- Similarity search with filtering
- Connection pooling and retry logic
- Backup/recovery stubs

**Key Classes:**
- `VectorStore` (abstract interface)
- `QdrantVectorStore` (production implementation)
- `VectorPoint` (data model)
- `SearchResult` (search result model)

**Features:**
- Per-tenant collection isolation
- Similarity search with score threshold
- Metadata filtering
- Connection pooling
- Retry logic for failures

---

#### 3. RAG Query Interface
**Location:** `src/memory/rag.py`

**Responsibilities:**
- Hybrid semantic search (vector + keyword)
- Query similar exceptions from history
- Return relevant resolutions
- Filtering by exceptionType, severity, domainName
- Relevance ranking and re-ranking
- Search result explanations

**Key Methods:**
- `hybrid_search()`: Combined vector + keyword search
- `search_similar()`: Find similar exceptions
- `get_resolution_context()`: Get resolution history

**Features:**
- Hybrid search (vector + keyword matching)
- Multi-vector search support
- Filtering and faceting
- Relevance scoring
- Result explanations

---

#### 4. Memory Index Registry
**Location:** `src/memory/index.py`

**Responsibilities:**
- Per-tenant memory index management
- Exception/resolution pair storage
- Index creation and management
- Search coordination

**Key Features:**
- Tenant-scoped indexes
- Exception/resolution pairing
- Search coordination
- Index lifecycle management

---

### Data Flow

```
1. Exception Resolved
   │
   ▼
2. Generate Embedding (via EmbeddingProvider)
   │
   ▼
3. Store in Vector Store (per-tenant collection)
   │
   ▼
4. Query Time: TriageAgent searches for similar
   │
   ▼
5. Hybrid Search (vector + keyword)
   │
   ▼
6. Return Top-K Similar Exceptions + Resolutions
   │
   ▼
7. Use as Context for Decision Making
```

---

## Autonomous Optimization & Learning Subsystem (Phase 3)

### Architecture Overview

Phase 3 introduces autonomous optimization engines that analyze outcomes and generate recommendations for continuous improvement.

```
┌─────────────────────────────────────────────────────────────────────┐
│              Optimization & Learning Pipeline                        │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Policy      │     │  Severity    │     │  Playbook    │
│  Learning    │     │  Recommender │     │  Recommender │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                     │
       └────────────────────┼─────────────────────┘
                            │
                            ▼
                  ┌─────────────────┐
                  │  Optimization  │
                  │     Engine     │
                  └────────┬───────┘
                           │
                ┌──────────┼──────────┐
                │          │          │
                ▼          ▼          ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Guardrail│ │ Combined │ │  Human   │
        │ Recommender│ │Suggestions│ │ Review  │
        └──────────┘ └──────────┘ └──────────┘
```

### Components

#### 1. Policy Learning
**Location:** `src/learning/policy_learning.py`

**Phase 3 Enhancement:** Enhanced with outcome analysis (P3-7)

**Responsibilities:**
- Track per-policy-rule outcomes (success/failure, MTTR, false positives/negatives)
- Analyze policy rule effectiveness
- Generate policy improvement suggestions
- Integrate with severity and guardrail recommenders

**Key Features:**
- Per-rule outcome tracking
- False positive/negative detection from human overrides
- Policy improvement suggestions with impact estimates
- Human-in-the-loop approval workflow
- Combined suggestions from all recommenders

---

#### 2. Severity Rule Recommender
**Location:** `src/learning/severity_recommender.py`

**Phase 3:** Automatic severity rule recommendation (P3-8)

**Responsibilities:**
- Analyze historical exceptions and triage decisions
- Identify patterns correlating with escalated cases
- Generate severity rule suggestions with confidence scores
- Support human review and approval workflow

**Key Features:**
- Pattern analysis for severity rules
- Confidence scoring based on historical data
- Example exception tracking
- Persistence to JSONL files

---

#### 3. Playbook Recommender
**Location:** `src/learning/playbook_recommender.py`

**Phase 3:** Automatic playbook recommendation and optimization (P3-9)

**Responsibilities:**
- Analyze successful resolutions to suggest new playbooks
- Detect patterns of repeated manual steps
- Optimize existing underperforming playbooks
- Generate effectiveness predictions

**Key Features:**
- New playbook suggestions from successful patterns
- Playbook optimization (remove redundant steps, adjust order)
- Effectiveness prediction based on historical stats
- Human review and approval workflow

---

#### 4. Guardrail Recommender
**Location:** `src/learning/guardrail_recommender.py`

**Phase 3:** Guardrail adjustment recommendation (P3-10)

**Responsibilities:**
- Analyze policy violations and false positives/negatives
- Suggest guardrail tuning and adjustments
- Generate impact analysis for recommendations
- Support human review and approval workflow

**Key Features:**
- False positive/negative ratio analysis
- Guardrail relaxation/tightening suggestions
- Impact analysis (estimated changes in FP/FN ratios)
- Configurable thresholds for analysis

---

#### 5. Optimization Engine
**Location:** `src/optimization/engine.py`

**Phase 3:** Metrics-driven optimization (P3-11)

**Responsibilities:**
- Collect optimization signals from all learning modules
- Generate unified optimization recommendations
- Normalize recommendations from different sources
- Persist recommendations for human review

**Key Features:**
- Signal collection from policy, severity, playbook, guardrail recommenders
- Unified `OptimizationRecommendation` format
- Category-based organization (policy, severity, playbook, guardrail)
- Impact estimates and confidence scores

---

## Streaming & Real-Time Subsystem (Phase 3)

### Architecture Overview

Phase 3 introduces streaming capabilities for high-throughput ingestion and real-time decision updates.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Streaming Subsystem                              │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Kafka/MQ   │────►│  Streaming   │────►│  Backpressure│
│   Backend    │     │  Ingestion   │     │  Controller   │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                            ▼
                  ┌─────────────────┐
                  │  Orchestrator   │
                  │   (Pipeline)    │
                  └────────┬───────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Decision       │
                  │  Stream        │
                  │  (Event Bus)    │
                  └────────┬───────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  SSE/WebSocket  │
                  │  (Real-Time)    │
                  └─────────────────┘
```

### Components

#### 1. Streaming Ingestion
**Location:** `src/ingestion/streaming.py`

**Phase 3:** Streaming ingestion mode (P3-17)

**Responsibilities:**
- Support Kafka or message queue ingestion
- High-throughput exception ingestion
- Message queue abstraction layer
- Integration with backpressure controller

**Key Classes:**
- `StreamingIngestionBackend` (protocol)
- `KafkaIngestionBackend` (stub implementation)
- `StubIngestionBackend` (in-memory for testing)
- `StreamingIngestionService`

**Features:**
- Both batch and streaming modes supported
- Per-tenant configuration
- Queue depth tracking
- Integration with backpressure control

---

#### 2. Incremental Decision Streaming
**Location:** `src/streaming/decision_stream.py`

**Phase 3:** Stage-by-stage updates (P3-18)

**Responsibilities:**
- Stream stage-by-stage updates as agents process exceptions
- Real-time status updates via SSE/WebSocket
- Event bus for pub/sub architecture
- Subscription management per tenant/exception

**Key Classes:**
- `EventBus`: In-memory pub/sub system
- `DecisionStreamService`: Subscription management
- `StageCompletedEvent`: Structured update events

**Features:**
- Real-time updates for all pipeline stages
- Server-Sent Events (SSE) support
- Subscription per exception or per tenant
- Heartbeat events to keep connections alive

---

#### 3. Backpressure and Rate Control
**Location:** `src/streaming/backpressure.py`

**Phase 3:** Backpressure mechanisms (P3-19)

**Responsibilities:**
- Protect downstream systems from overload
- Rate limiting and throttling for streaming
- Adaptive rate control based on system health
- Queue depth monitoring and alerting

**Key Classes:**
- `BackpressurePolicy`: Configuration thresholds
- `BackpressureController`: State management and enforcement
- `BackpressureState`: NORMAL, WARNING, CRITICAL, OVERLOADED

**Features:**
- Queue depth tracking
- In-flight exception limits
- Per-tenant rate limiting
- Adaptive delays based on system load
- Low-priority message dropping when overloaded

---

## Safety & Security Subsystem (Phase 3)

### Architecture Overview

Phase 3 introduces comprehensive safety rules, violation detection, and red-teaming capabilities.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Safety & Security Layer                          │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Safety      │     │  Violation   │     │  Red-Team    │
│  Rules       │     │  Detector    │     │  Harness     │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                     │
       └────────────────────┼─────────────────────┘
                            │
                            ▼
                  ┌─────────────────┐
                  │  Incident       │
                  │  Manager        │
                  └────────┬───────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Audit & Alert  │
                  └─────────────────┘
```

### Components

#### 1. Safety Rules
**Location:** `src/safety/rules.py`

**Phase 3:** Expanded safety rules (P3-20)

**Responsibilities:**
- Enforce safety rules for LLM calls (rate limits, token limits, cost controls)
- Enforce safety rules for tool usage (execution time, retries, disallowed tools)
- Support tenant-specific overrides
- Monitor and alert on violations

**Key Classes:**
- `SafetyRuleConfig`: Configuration with per-tenant overrides
- `SafetyEnforcer`: Rule enforcement and usage tracking
- `SafetyViolation`: Exception for violations

**Features:**
- LLM safety: max tokens per call, max calls per minute, max cost per hour
- Tool safety: max execution time, max retries, disallowed tools list
- Per-tenant overrides
- Usage tracking and metrics

---

#### 2. Violation Detector
**Location:** `src/safety/violation_detector.py`

**Phase 3:** Policy violation and unauthorized tool usage detection (P3-22)

**Responsibilities:**
- Detect policy violations in agent decisions
- Detect unauthorized tool usage attempts
- Real-time monitoring and alerting
- Automatic blocking of unauthorized actions

**Key Classes:**
- `ViolationDetector`: Main detection logic
- `PolicyViolation`: Policy violation data model
- `ToolViolation`: Tool violation data model
- `ViolationSeverity`: Severity levels (LOW, MEDIUM, HIGH, CRITICAL)

**Features:**
- Policy decision validation against tenant policies
- Tool call validation against allow-lists
- Automatic blocking of critical violations
- Incident management integration

---

#### 3. Red-Team Test Harness
**Location:** `src/redteam/harness.py`, `src/redteam/scenarios.py`, `src/redteam/reporting.py`

**Phase 3:** Red-team testing (P3-21)

**Responsibilities:**
- Validate LLM prompts and outputs against safety requirements
- Test for prompt injection, jailbreaking, and output manipulation
- Generate red-team test reports with vulnerability assessments
- Support automated testing in CI/CD pipeline

**Key Classes:**
- `RedTeamHarness`: Test execution engine
- `RedTeamScenario`: Test scenario definition
- `RedTeamResult`: Test result with violations
- `AttackType`: Types of attacks to test

**Features:**
- Adversarial prompt injection scenarios
- Schema bypass detection
- Output manipulation detection
- Domain-specific adversarial suites (finance/FINRA, healthcare/HIPAA)
- JSON and Markdown report generation

---

#### 4. Adversarial Test Suites
**Location:** `src/redteam/adversarial_suites.py`, `src/redteam/data_generators.py`

**Phase 3:** Synthetic adversarial test suites (P3-23)

**Responsibilities:**
- Generate synthetic adversarial test suites for high-risk domains
- Create test scenarios for malicious or edge-case exceptions
- Test for domain-specific compliance violations (FINRA, HIPAA)
- Generate synthetic test data that challenges agent decision-making

**Key Functions:**
- `build_finance_adversarial_suite()`: FINRA-style test scenarios
- `build_healthcare_adversarial_suite()`: HIPAA-style test scenarios
- `generate_finance_exception_edge_cases()`: Synthetic finance data
- `generate_healthcare_exception_edge_cases()`: Synthetic healthcare data

**Features:**
- Domain-specific test scenarios
- Regulatory compliance testing
- Synthetic data generation
- Integration with red-team harness

---

## Explainability & Traceability Subsystem (Phase 3)

### Architecture Overview

Phase 3 introduces comprehensive explainability features for full transparency and traceability.

```
┌─────────────────────────────────────────────────────────────────────┐
│              Explainability & Traceability                          │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Decision    │     │  Evidence    │     │  Explanation │
│  Timelines   │     │  Tracking    │     │  Service     │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                     │
       └────────────────────┼─────────────────────┘
                            │
                            ▼
                  ┌─────────────────┐
                  │  Explanation    │
                  │  API           │
                  └────────┬───────┘
                           │
                ┌──────────┼──────────┐
                │          │          │
                ▼          ▼          ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  Quality  │ │ Analytics│ │  Audit   │
        │  Scoring │ │  Service │ │ Integration│
        └──────────┘ └──────────┘ └──────────┘
```

### Components

#### 1. Decision Timelines
**Location:** `src/explainability/timelines.py`

**Phase 3:** Human-readable decision timelines (P3-28)

**Responsibilities:**
- Build human-readable decision timelines showing agent execution sequence
- Document evidence used at each stage
- Explain action/playbook selection and rejection reasoning
- Generate timeline visualizations

**Key Classes:**
- `TimelineEvent`: Single event in the timeline
- `DecisionTimeline`: Complete timeline for an exception
- `build_timeline_for_exception()`: Timeline builder function

**Features:**
- Chronological agent execution sequence
- Evidence attribution at each stage
- Action/playbook reasoning
- Markdown export for sharing

---

#### 2. Evidence Tracking
**Location:** `src/explainability/evidence.py`, `src/explainability/evidence_integration.py`

**Phase 3:** Evidence tracking and attribution (P3-29)

**Responsibilities:**
- Track all evidence sources (RAG, tools, policies)
- Document evidence influence on decisions
- Support evidence chain visualization
- Enable evidence validation and verification

**Key Classes:**
- `EvidenceItem`: Single piece of evidence
- `EvidenceLink`: Link between evidence and decisions
- `EvidenceType`: Types (rag, tool, policy, manual)
- `EvidenceInfluence`: Influence types (support, contradict, contextual)

**Features:**
- RAG result tracking with similarity scores
- Tool output tracking
- Policy rule and guardrail tracking
- Evidence chain visualization
- Integration with all agents

---

#### 3. Explanation Service
**Location:** `src/services/explanation_service.py`

**Phase 3:** Explanation API endpoints (P3-30)

**Responsibilities:**
- Generate explanations in multiple formats (JSON, text, structured)
- Support explanation queries by exception ID, agent, or decision type
- Integrate decision timelines and evidence tracking
- Provide explanation versioning and history

**Key Features:**
- Multiple format support (JSON, natural language, structured)
- Explanation filtering and search
- Integration with timelines and evidence
- Quality scoring integration

---

#### 4. Explanation Analytics
**Location:** `src/services/explanation_analytics.py`

**Phase 3:** Explanation integration with audit and metrics (P3-31)

**Responsibilities:**
- Link explanations to audit trail entries
- Link explanations to metrics and outcomes
- Enable explanation-based analytics and quality scoring
- Correlate explanations with resolution success/failure and MTTR

**Key Features:**
- Average quality score calculation
- Correlation with resolution success
- Correlation with MTTR
- Quality score and latency distributions

---

## Execution Engine Subsystem

### Architecture Overview

The Execution Engine provides robust, production-ready tool execution with comprehensive error handling, retry logic, and circuit breakers.

```
┌─────────────────────────────────────────────────────────────────────┐
│                  Tool Execution Engine                               │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Tool        │────►│  Execution   │────►│  Circuit     │
│  Registry    │     │    Engine     │     │  Breaker     │
└──────────────┘     └──────┬───────┘     └──────────────┘
                             │
                ┌────────────┼────────────┐
                │            │            │
                ▼            ▼            ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │  Retry   │  │ Timeout  │  │ Result   │
        │  Logic   │  │ Handler  │  │ Validator│
        └──────────┘  └──────────┘  └──────────┘
                │            │            │
                └────────────┼────────────┘
                             │
                             ▼
                    ┌──────────────┐
                    │  Tool        │
                    │  Invocation  │
                    │  (HTTP/gRPC) │
                    └──────────────┘
```

### Components

#### 1. Tool Execution Engine
**Location:** `src/tools/execution_engine.py`

**Responsibilities:**
- Execute tools with retry logic (exponential backoff)
- Timeout management per tool definition
- Circuit breaker pattern (open/half-open/closed)
- Result schema validation
- Async and sync execution modes
- Comprehensive audit logging

**Key Classes:**
- `ToolExecutionEngine`
- `CircuitBreaker`
- `CircuitState` (enum)
- `ToolExecutionError`, `CircuitBreakerOpenError`, `ToolTimeoutError`

**Features:**
- **Retry Logic:**
  - Exponential backoff
  - Configurable max retries
  - Jitter for retry delays
  
- **Circuit Breaker:**
  - Failure threshold tracking
  - Automatic circuit opening
  - Half-open state for recovery testing
  - Success threshold for closing
  
- **Timeout Management:**
  - Per-tool timeout configuration
  - Async timeout handling
  - Timeout error reporting
  
- **Result Validation:**
  - Schema validation against tool definition
  - Type checking
  - Required field validation

---

#### 2. Tool Registry
**Location:** `src/tools/registry.py`

**Responsibilities:**
- Tenant-scoped tool registration
- Domain tool loading from Domain Packs
- Tool inheritance and overrides
- Tool versioning and compatibility
- Allow-list enforcement
- Tool lookup and listing

**Key Features:**
- **Domain Tools:**
  - Load from Domain Pack tool definitions
  - Namespace: `{tenantId}:{domainName}:{toolName}`
  - Version compatibility checks
  
- **Tool Overrides:**
  - Tenant Policy Pack can override tool properties
  - Timeout, retry, and other parameter overrides
  
- **Isolation:**
  - Per-tenant tool registry
  - No cross-tenant tool access

---

#### 3. Tool Invoker
**Location:** `src/tools/invoker.py`

**Responsibilities:**
- HTTP/gRPC tool invocation
- Request/response handling
- Error handling and transformation
- Integration with Execution Engine
- Audit logging

**Key Features:**
- HTTP client (httpx)
- Request signing (if configured)
- Response parsing
- Error transformation
- Audit trail generation

---

### Execution Flow

```
1. ResolutionAgent selects tool
   │
   ▼
2. Check Tool Registry (tenant-scoped)
   │
   ▼
3. Check Circuit Breaker State
   │
   ├─► OPEN: Fail immediately
   │
   ├─► HALF_OPEN: Test execution
   │
   └─► CLOSED: Proceed
       │
       ▼
4. Execute with Retry Logic
   │
   ├─► Success: Record success, return result
   │
   └─► Failure: Retry with backoff
       │
       ├─► Max retries exceeded: Open circuit
       │
       └─► Retry successful: Record success
```

---

## Startup and Deployment

### Prerequisites

- **Python:** 3.11 or higher
- **Dependencies:** See `requirements.txt`
- **Optional:**
  - Qdrant vector database (for production RAG)
  - SMTP server (for email notifications)
  - Webhook endpoints (for Slack/Teams)

### Installation Steps

#### 1. Clone Repository
```bash
git clone <repository-url>
cd agentic-exception-platform
```

#### 2. Create Virtual Environment
```bash
# Linux/Mac
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt

# With development dependencies
pip install -e ".[dev]"
```

#### 4. Configure Environment (Optional)
Create `.env` file:
```bash
# LLM Provider (OpenAI example) - Phase 3
OPENAI_API_KEY=your_api_key_here
LLM_PROVIDER=openai
LLM_MODEL=gpt-4

# Vector Database (Qdrant)
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_api_key_here

# SMTP (for notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@example.com
SMTP_PASSWORD=your_password

# API Keys (for tenant authentication)
TENANT_API_KEYS=tenant1:key1,tenant2:key2

# Phase 3: Streaming Ingestion (optional)
STREAMING_ENABLED=false
STREAMING_BACKEND=kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC=exceptions
KAFKA_GROUP_ID=exception-processor

# Phase 3: SLO/SLA Configuration
SLO_CONFIG_DIR=./config/slo
```

#### 5. Prepare Domain Packs and Tenant Policies
```bash
# Domain Packs
mkdir -p domainpacks
# Copy domain pack JSON files to domainpacks/

# Tenant Policy Packs
mkdir -p tenantpacks
# Copy tenant policy JSON files to tenantpacks/
```

#### 6. Start Application

**Quick Start (Recommended):**
```bash
# Linux/Mac
chmod +x scripts/start_server.sh
./scripts/start_server.sh

# Windows
scripts\start_server.bat
```

The startup script will:
- Check/create virtual environment
- Install dependencies if needed
- Create necessary runtime directories
- Start the FastAPI server

**Manual Start - Development Server:**
```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

**Production Server:**
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**With Docker (if Dockerfile exists):**
```bash
docker build -t agentic-exception-platform .
docker run -p 8000:8000 agentic-exception-platform
```

### Verification

#### 1. Health Check
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

#### 2. API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

#### 3. Test Exception Ingestion
```bash
curl -X POST http://localhost:8000/exceptions/TENANT_001 \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test_api_key_tenant_001" \
  -d '{
    "sourceSystem": "ERP",
    "timestamp": "2024-01-15T10:30:00Z",
    "rawPayload": {
      "error": "Settlement failed",
      "orderId": "ORD123"
    }
  }'
```

### Running Tests

**All Tests:**
```bash
pytest
```

**With Coverage:**
```bash
# Linux/Mac
./scripts/run_tests.sh

# Windows
scripts\run_tests.bat
```

**Specific Test Suite:**
```bash
pytest tests/test_e2e_pipeline.py -v
pytest tests/test_phase2_tenant_isolation.py -v
```

### Running Multi-Domain Simulation

```bash
python -m src.simulation.runner \
  --domains finance,healthcare \
  --batch 100 \
  --domain-packs-dir domainpacks \
  --tenant-packs-dir tenantpacks \
  --output-dir runtime/simulation
```

---

## API Endpoints

### Core Exception Processing

- `POST /exceptions/{tenantId}` - Ingest exception
- `GET /exceptions/{tenantId}/{exceptionId}` - Get exception status
- `POST /run` - Run pipeline for exception batch

### Admin APIs

- `POST /admin/domainpacks/{tenantId}` - Upload Domain Pack
- `GET /admin/domainpacks/{tenantId}` - List Domain Packs
- `POST /admin/domainpacks/{tenantId}/rollback` - Rollback version
- `POST /admin/domainpacks/{tenantId}/{domainName}/run-tests` - Run test suites
- `POST /admin/tenantpolicies/{tenantId}` - Upload Tenant Policy Pack
- `GET /admin/tenantpolicies/{tenantId}` - Get Tenant Policy Pack
- `POST /admin/tools/{tenantId}/{domainName}` - Register tool

### Approval Workflow

- `GET /ui/approvals/{tenantId}` - List pending approvals
- `POST /approvals/{tenantId}/{approvalId}/approve` - Approve request
- `POST /approvals/{tenantId}/{approvalId}/reject` - Reject request

### Observability

- `GET /metrics/{tenantId}` - Get metrics
- `GET /dashboards/{tenantId}/summary` - Dashboard summary
- `GET /dashboards/{tenantId}/exceptions` - Exception dashboard
- `GET /dashboards/{tenantId}/playbooks` - Playbook dashboard

### Phase 3: Operator UI Backend APIs

- `GET /ui/exceptions` - Browse exceptions with filtering, searching, and pagination
- `GET /ui/exceptions/{exception_id}` - Get full exception detail with agent decisions
- `GET /ui/exceptions/{exception_id}/evidence` - Get evidence chains and RAG results
- `GET /ui/exceptions/{exception_id}/audit` - Get audit events for exception
- `GET /ui/stream/exceptions` - Server-Sent Events stream for real-time updates

### Phase 3: Natural Language Interaction

- `POST /ui/nlq` - Natural language query API for agent questions

### Phase 3: Simulation & What-If

- `POST /ui/exceptions/{exception_id}/rerun` - Re-run exception processing with modified parameters
- `GET /ui/simulations/{simulation_id}` - Get simulation result and comparison

### Phase 3: Supervisor Dashboard

- `GET /ui/supervisor/overview` - Supervisor dashboard overview with aggregated metrics
- `GET /ui/supervisor/escalations` - List of escalated exceptions
- `GET /ui/supervisor/policy-violations` - Recent policy violation events

### Phase 3: Configuration Management

- `GET /admin/config/domain-packs` - List Domain Packs
- `GET /admin/config/domain-packs/{id}` - Get Domain Pack by ID
- `GET /admin/config/tenant-policies/{id}` - Get Tenant Policy Pack by ID
- `GET /admin/config/playbooks/{id}` - Get Playbook by ID
- `GET /admin/config/diff` - Compare two configuration versions
- `GET /admin/config/history/{config_type}/{config_id}` - Get configuration version history
- `POST /admin/config/rollback` - Rollback configuration version (stub)

### Phase 3: Explanation APIs

- `GET /explanations/{exception_id}` - Get explanation in multiple formats (JSON, text, structured)
- `GET /explanations/search` - Search explanations by tenant, agent, decision type, etc.
- `GET /explanations/{exception_id}/timeline` - Get decision timeline for exception
- `GET /explanations/{exception_id}/evidence` - Get evidence graph for exception

### Phase 3: Learning & Optimization APIs

- `GET /learning/guardrail-recommendations` - Get guardrail adjustment recommendations

---

## Configuration

### Domain Pack Structure
See `docs/05-domain-pack-schema.md` for full schema.

Key components:
- `domainName`: Domain identifier
- `exceptionTypes`: Exception taxonomy
- `severityRules`: Severity mapping rules
- `tools`: Tool definitions
- `playbooks`: Resolution playbooks
- `guardrails`: Safety guardrails
- `testSuites`: Test cases

### Tenant Policy Pack Structure
See `docs/03-data-models-apis.md` for full schema.

Key components:
- `tenantId`: Tenant identifier
- `domainName`: Associated domain
- `approvedTools`: Tool allow-list
- `humanApprovalRules`: Approval rules
- `customGuardrails`: Custom guardrails
- `notificationPolicies`: Notification routing

---

## Monitoring and Observability

### Metrics Collected

- **Exception Metrics:**
  - Total exceptions processed
  - Auto-resolution rate
  - Mean Time To Resolution (MTTR)
  - Exception counts by type/severity
  
- **Agent Metrics:**
  - Agent latency per stage
  - Confidence score distribution
  - Decision distribution
  - Success/failure rates
  - **Phase 3:** LLM fallback rates
  - **Phase 3:** Explanation generation metrics
  
- **Tool Metrics:**
  - Tool execution latency
  - Retry counts
  - Failure rates
  - Circuit breaker states
  - **Phase 3:** Quota usage tracking
  
- **Playbook Metrics:**
  - Playbook success rates
  - Step execution times
  - Rollback frequency
  
- **Phase 3: LLM Metrics:**
  - LLM call counts and latencies
  - Token usage and cost tracking
  - Schema validation success/failure rates
  - Circuit breaker states per provider
  
- **Phase 3: Explanation Metrics:**
  - Explanations generated total
  - Explanations per exception
  - Explanation latency
  - Explanation quality scores
  
- **Phase 3: SLO/SLA Metrics:**
  - P95 latency per tenant
  - Error rates
  - MTTR targets vs actual
  - Auto-resolution rate targets vs actual
  - Throughput (exceptions per second)

### Dashboards

- Real-time exception processing
- Agent performance
- Domain-specific analytics
- Custom dashboards per tenant
- **Phase 3:** Supervisor dashboard with cross-tenant views
- **Phase 3:** Explanation analytics dashboard
- **Phase 3:** SLO/SLA compliance dashboard

### Alerts

- High exception volume
- Repeated CRITICAL breaks
- Tool circuit breaker open
- Approval queue aging
- Custom alert rules per tenant
- **Phase 3:** SLO/SLA violations
- **Phase 3:** Quota threshold exceeded
- **Phase 3:** Policy violations detected
- **Phase 3:** Safety rule violations
- **Phase 3:** Backpressure thresholds exceeded

### Phase 3: SLO/SLA Monitoring

**Location:** `src/observability/slo_config.py`, `src/observability/slo_engine.py`, `src/observability/slo_monitoring.py`

**Features:**
- Per-tenant SLO/SLA configuration
- P95 latency tracking
- Error rate monitoring
- MTTR target tracking
- Auto-resolution rate monitoring
- SLO violation alerting
- Compliance reporting

---

## Security and Compliance

### Tenant Isolation

- **Data Isolation:** Separate storage per tenant
- **Memory Isolation:** Per-tenant vector collections
- **Tool Isolation:** Tenant-scoped tool registry
- **Configuration Isolation:** Per-tenant Domain/Policy Packs
- **Phase 3:** Resource pools per tenant (DB connections, vector DB clients, tool clients)
- **Phase 3:** Quota isolation per tenant

### Audit Trail

- All agent decisions logged
- Tool executions audited
- Approval actions tracked
- Full timestamp and actor tracking
- **Phase 3:** Explanation generation events logged
- **Phase 3:** Guardrail recommendation events logged
- **Phase 3:** Policy violation events logged
- **Phase 3:** Safety rule violation events logged
- **Phase 3:** LLM fallback events logged

### Access Control

- JWT token authentication
- API key authentication
- RBAC with tenant-scoped sessions
- Rate limiting per tenant

### Phase 3: Safety & Compliance Features

- **Expanded Safety Rules:**
  - LLM call limits (tokens, requests, cost)
  - Tool usage limits (execution time, retries, disallowed tools)
  - Per-tenant safety rule overrides
  
- **Policy Violation Detection:**
  - Real-time monitoring of policy violations
  - Automatic blocking of unauthorized actions
  - Incident management integration
  
- **Red-Team Testing:**
  - Automated adversarial testing
  - Prompt injection detection
  - Domain-specific compliance testing (FINRA, HIPAA)
  
- **Quota Enforcement:**
  - LLM quotas (tokens, requests, cost per day)
  - Vector DB quotas (queries, writes, storage)
  - Tool execution quotas (calls, execution time)
  - Per-tenant quota isolation

---

## Performance Characteristics

### Throughput

- **Single Tenant:** 1000+ exceptions/second
- **Multi-Tenant:** Scales horizontally
- **Parallel Processing:** Supported for batch operations

### Latency

- **End-to-End Pipeline:** < 5 seconds (typical)
- **Agent Response:** < 1 second per agent (typical)
- **RAG Query:** < 500ms (typical)
- **Tool Execution:** Varies by tool (typically < 2 seconds)

### Scalability

- **Horizontal Scaling:** Stateless agents support multiple instances
- **Vector Database:** Scales with Qdrant cluster
- **Tool Execution:** Async execution supports high concurrency
- **Phase 3:** Streaming ingestion supports high-throughput scenarios
- **Phase 3:** Domain pack caching and lazy loading for performance
- **Phase 3:** Resource pooling per tenant for efficient resource usage
- **Phase 3:** Backpressure control protects downstream systems from overload

---

## Troubleshooting

### Common Issues

1. **Vector Database Connection Failed**
   - Check QDRANT_URL and QDRANT_API_KEY
   - Verify Qdrant service is running
   - Check network connectivity

2. **LLM Provider Errors**
   - Verify API keys are set
   - Check rate limits
   - Review provider status

3. **Tenant Isolation Violations**
   - Review tenant ID extraction in auth middleware
   - Verify Domain Pack loading per tenant
   - Check vector store collection namespacing

4. **Tool Execution Failures**
   - Check circuit breaker state
   - Review tool endpoint availability
   - Verify tool allow-list configuration

### Logging

Logs are written to:
- Console (structured JSON)
- Files: `runtime/logs/{tenantId}.log`
- Audit trail: `runtime/audit/{tenantId}.jsonl`

Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

---

## Contributing

See `CONTRIBUTING.md` for development guidelines.

### Development Workflow

1. Create feature branch
2. Implement feature with tests
3. Ensure >85% coverage
4. Run linting and type checking
5. Submit pull request

### Code Quality

- **Formatting:** Black
- **Linting:** Ruff
- **Type Checking:** mypy
- **Testing:** pytest with >85% coverage

---

## License

[Specify license]

---

## Support

For issues and questions:
- GitHub Issues: [repository-url]/issues
- Documentation: `docs/` directory
- API Documentation: http://localhost:8000/docs

---

## Phase 3 Enhancements Summary

### LLM Integration
- All agents enhanced with explainable LLM reasoning
- Safe JSON-bounded outputs with schema validation
- Fallback strategies and circuit breakers
- Tenant-aware LLM configuration

### Autonomous Optimization
- Policy learning with outcome analysis
- Automatic severity rule recommendations
- Playbook recommendation and optimization
- Guardrail adjustment recommendations
- Unified optimization engine

### UX & Workflow Layer
- Comprehensive operator UI backend APIs
- Natural language interaction (NLQ)
- Re-run and what-if simulation
- Supervisor dashboard APIs
- Configuration viewing and diffing

### Streaming Capabilities
- Kafka/MQ streaming ingestion
- Incremental decision streaming (SSE)
- Backpressure and rate control
- Real-time status updates

### Safety & Security
- Expanded safety rules for LLM and tools
- Red-team test harness
- Policy violation detection
- Synthetic adversarial test suites
- Incident management

### Scale Readiness
- Infrastructure hardening for many domains/tenants
- SLO/SLA metrics definitions and monitoring
- Tenancy-aware quotas and limits
- Operational runbooks and incident playbooks

### Explainability
- Human-readable decision timelines
- Evidence tracking and attribution
- Explanation API endpoints
- Explanation integration with audit and metrics
- Quality scoring for explanations

---

## Version History

- **v3.0.0** (Phase 3 MVP): Complete Phase 3 implementation with LLM integration, autonomous optimization, streaming, safety, and explainability
- **v2.0.0** (Phase 2 MVP): Complete Phase 2 implementation
- **v1.0.0** (Phase 1 MVP): Initial MVP release

---

*Last Updated: 2024*

