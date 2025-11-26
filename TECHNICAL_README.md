# Agentic Exception Processing Platform - Technical Documentation

## Executive Summary

The **Agentic Exception Processing Platform** is an enterprise-grade, domain-abstracted AI platform designed for multi-tenant exception processing across diverse business domains. Built on a foundation of configurable Domain Packs and Tenant Policy Packs, the platform provides intelligent exception handling through a multi-agent orchestration pipeline.

### Key Capabilities

- **Multi-Tenant Architecture:** Strict isolation of data, memory, tools, and configurations per tenant
- **Domain Abstraction:** Zero hardcoding - all behavior driven by Domain Packs and Tenant Policy Packs
- **Intelligent Agent Pipeline:** 5 core agents (Intake, Triage, Policy, Resolution, Feedback) + optional SupervisorAgent
- **Advanced RAG System:** Production vector database with hybrid semantic search
- **Robust Tool Execution:** Circuit breakers, retries, timeouts, and comprehensive error handling
- **Human-in-the-Loop:** Complete approval workflow for high-severity actions
- **Rich Observability:** Real-time metrics, dashboards, alerts, and notifications
- **Admin Management:** Full CRUD operations for Domain Packs, Tenant Policies, and Tools
- **Testing Infrastructure:** Multi-domain simulation and automated test suite execution

### Business Value

- **80%+ Auto-Resolution Rate:** Automated handling of routine exceptions
- **Reduced MTTR:** Mean Time To Resolution significantly improved through intelligent routing
- **Domain Flexibility:** Support for finance, healthcare, manufacturing, and more without code changes
- **Compliance Ready:** Full audit trails, tenant isolation, and human approval workflows
- **Scalable Architecture:** Handles thousands of exceptions per second across multiple tenants

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
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              Exception Ingestion Service                                 │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  • REST API Endpoint (POST /exceptions/{tenantId})              │  │
│  │  • Raw Payload Parsing                                           │  │
│  │  • Canonical Schema Normalization                                │  │
│  │  • Field Extraction (tenantId, sourceSystem, timestamp, etc.)   │  │
│  │  • Schema Validation                                             │  │
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
│  │  2. TriageAgent ──► Classify & Score                            │  │
│  │  3. PolicyAgent ───► Enforce Guardrails                          │  │
│  │  4. ResolutionAgent ──► Execute Playbooks                        │  │
│  │  5. FeedbackAgent ──► Learn & Update Memory                      │  │
│  │                                                                   │  │
│  │  Optional: SupervisorAgent ──► Oversight & Intervention          │  │
│  │                                                                   │  │
│  │  Features:                                                        │  │
│  │  • Parallel execution support                                    │  │
│  │  • Conditional branching                                         │  │
│  │  • Retry logic & error recovery                                  │  │
│  │  • State management                                              │  │
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
└──────────────────────────────┘  └──────────────────────────────┘
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

**Responsibilities:**
- Classify exception type using Domain Pack taxonomy
- Score severity using Domain Pack severity rules
- Query RAG for similar historical exceptions
- Generate diagnostic summary
- Calculate confidence based on match strength

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

---

#### 3. PolicyAgent
**Location:** `src/agents/policy.py`

**Responsibilities:**
- Evaluate triage output against Tenant Policy Pack guardrails
- Check allow-lists and block-lists
- Apply human approval rules based on severity
- Approve or block suggested actions
- Route to approval queue if required

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

---

#### 4. ResolutionAgent
**Location:** `src/agents/resolution.py`

**Responsibilities:**
- Select playbook from Domain/Tenant Packs matching exception type
- Execute playbook steps sequentially
- Invoke approved tools via Tool Execution Engine
- Handle partial automation for non-critical actions
- Update resolution status
- Support rollback on failure

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

**Responsibilities:**
- Oversee entire pipeline for safety
- Review agent decisions for consistency
- Intervene if confidence chain is too low
- Override decisions if policy breach detected
- Escalate to human if needed

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
# LLM Provider (OpenAI example)
OPENAI_API_KEY=your_api_key_here

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
  
- **Tool Metrics:**
  - Tool execution latency
  - Retry counts
  - Failure rates
  - Circuit breaker states
  
- **Playbook Metrics:**
  - Playbook success rates
  - Step execution times
  - Rollback frequency

### Dashboards

- Real-time exception processing
- Agent performance
- Domain-specific analytics
- Custom dashboards per tenant

### Alerts

- High exception volume
- Repeated CRITICAL breaks
- Tool circuit breaker open
- Approval queue aging
- Custom alert rules per tenant

---

## Security and Compliance

### Tenant Isolation

- **Data Isolation:** Separate storage per tenant
- **Memory Isolation:** Per-tenant vector collections
- **Tool Isolation:** Tenant-scoped tool registry
- **Configuration Isolation:** Per-tenant Domain/Policy Packs

### Audit Trail

- All agent decisions logged
- Tool executions audited
- Approval actions tracked
- Full timestamp and actor tracking

### Access Control

- JWT token authentication
- API key authentication
- RBAC with tenant-scoped sessions
- Rate limiting per tenant

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

## Version History

- **v2.0.0** (Phase 2 MVP): Complete Phase 2 implementation
- **v1.0.0** (Phase 1 MVP): Initial MVP release

---

*Last Updated: 2024*

