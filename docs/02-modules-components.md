# Design for Modules & Components

## Module Responsibilities
1. **Gateway / Tenant Router**: Authenticates requests, identifies tenantId, and routes to isolated pipelines. Handles rate limiting and API versioning.
2. **Exception Ingestion Service**: Parses raw inputs from connectors (e.g., Kafka, REST, file watchers), normalizes to canonical schema, and enqueues for orchestration.
3. **Agent Orchestrator**: Coordinates agent pipeline; invokes agents sequentially or conditionally based on decisions. Manages state and retries.
4. **Skill/Tool Registry**: Maintains a dynamic registry of tenant-approved tools (e.g., retry APIs, data fix scripts). Tools are invoked via standardized interfaces.
5. **Memory Layer**: Per-tenant vector stores for RAG, storing historical exceptions, resolutions, and learnings. Supports querying for root cause analysis.
6. **Audit & Observability System**: Logs all decisions/actions; exposes metrics (e.g., Prometheus) and dashboards (e.g., Grafana). Includes alerting for anomalies.
7. **Admin UI / API**: Web interface for tenant management, pack uploads, and monitoring. APIs for programmatic control.

## Data Flow Across Components
- **Ingress**: External exception → Gateway → Ingestion Service (normalize) → Orchestrator.
- **Processing**: Orchestrator → IntakeAgent → TriageAgent (query Memory) → PolicyAgent (check guardrails) → ResolutionAgent (invoke Tools) → FeedbackAgent (update Memory).
- **Egress**: Resolved exception → Audit System; metrics → Observability.
- **Admin Flow**: Admin UI → API → Update packs/registry → Reload tenant configs.

All flows are audited with timestamps and tenantIds.

## Agent Communication Contracts
Agents exchange messages via JSON contracts:
- **Input**: Canonical exception + context from prior agents.
- **Output**: Standardized response:
  ```json
  {
    "decision": "string (e.g., 'Classified as DataQualityFailure')",
    "confidence": "float (0.0-1.0)",
    "evidence": ["array of strings/reasons"],
    "nextStep": "string (e.g., 'ProceedToPolicy' or 'Escalate')"
  }

  Inter-agent: Outputs from one become inputs to the next, with orchestration handling branching.

Tool Registry Design

Structure: Key-value store (e.g., Redis) with tenantId as prefix.
Tool Definition: Name, description, parameters, endpoint (e.g., Lambda function), allow-list status.
Invocation: Orchestrator calls tools via HTTP/gRPC; sandboxes execution (e.g., AWS Lambda isolation).
Registration: Via Admin API; validated against Domain Pack tools.

Memory & RAG Layer Design

Backend: Vector database (e.g., FAISS or Pinecone) per tenant.
Content: Embeddings of exceptions, resolutions, playbooks.
Operations: Index updates via FeedbackAgent; queries for similarity search in Triage/Resolution.
Isolation: Namespaced indexes; TTL for data retention compliance.


