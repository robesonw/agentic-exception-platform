flowchart LR

subgraph CLIENTS["Tenant Clients & Downstream Systems"]
    C1["Ops Analysts"]
    C2["Supervisors"]
    C3["Downstream Systems"]
end

subgraph APIGW["API Gateway / Auth"]
    AUTH["JWT / API Key / RBAC / Tenant Routing"]
end

subgraph API["FastAPI Service Layer"]
    ING["/exceptions"]
    RUN["/run"]
    STATUS["/exceptions/{id}"]
    APPROVALUI["/ui/approvals"]
    METRICS["/metrics"]
    ADMIN["/admin/* APIs"]
    DASH["/dashboards"]
    PBAPI["/exceptions/{id}/playbook<br/>(Phase 7)"]
end

subgraph ORCH["Orchestrator"]
    HOOKS["Pre/Post Hooks"]
    PIPE["Intake → Triage → Policy → Resolution → Feedback"]
    SUP["SupervisorAgent"]
end

subgraph AGENTS["Agent Layer"]
    A1["IntakeAgent"]
    A2["TriageAgent"]
    A3["PolicyAgent"]
    A4["ResolutionAgent"]
    A5["FeedbackAgent"]
end

subgraph DOMAIN["Domain Knowledge"]
    DP["Domain Packs"]
    PBM["PlaybookManager"]
    TP["Tenant Policy Packs"]
    PMS["Playbook Matching Service<br/>(Phase 7)"]
    PES["Playbook Execution Service<br/>(Phase 7)"]
end

subgraph MEMORY["Memory & Search"]
    EMB["Embedding Providers"]
    VSTORE["Vector Store"]
    HYB["Hybrid Semantic Search"]
end

subgraph EXEC["Execution"]
    REG["Tool Registry"]
    INV["ToolInvoker"]
    EE["Execution Engine"]
end

subgraph WORKFLOWS["Human Approval & Learning"]
    HAP["Approval Queue"]
    LEARN["Policy Learning"]
end

subgraph OBS["Observability & Alerts"]
    MET["Metrics Collector"]
    ALERTS["Alert Rules"]
    NOTIF["Notification Service"]
    AUD["Audit Logs"]
end

CLIENTS --> APIGW --> API --> ORCH
ORCH --> AGENTS
AGENTS --> DOMAIN
AGENTS --> MEMORY
AGENTS --> EXEC
ORCH --> WORKFLOWS
ORCH --> OBS
