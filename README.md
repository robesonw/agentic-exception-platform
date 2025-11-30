# Agentic Exception Processing Platform (MVP)

Domain-Abstracted Agentic AI Platform for Multi-Tenant Exception Processing.

This repo implements the MVP described in `docs/06-mvp-plan.md`.

## Documentation

Start here:
- `docs/master_project_instruction_full.md` - Master project specification
- `docs/01-architecture.md` - System architecture
- `docs/03-data-models-apis.md` - Data models and API specifications
- `docs/06-mvp-plan.md` - MVP implementation plan

## Project Structure

```
src/
├── api/              # FastAPI application and routes
├── models/           # Pydantic models for schemas
├── domainpack/       # Domain Pack loader and validator
├── tenantpack/       # Tenant Policy Pack loader and validator
├── tools/            # Tool registry and invocation
├── agents/           # Agent implementations (Phase 3: LLM-enhanced)
├── orchestrator/     # Agent pipeline orchestrator
├── audit/            # Audit trail and metrics
├── llm/              # Phase 3: LLM client, schemas, validation, fallbacks
├── learning/         # Phase 3: Policy learning, recommenders, optimization
├── streaming/        # Phase 3: Streaming ingestion and decision streaming
├── safety/           # Phase 3: Safety rules, violation detection, quotas
├── explainability/   # Phase 3: Decision timelines, evidence tracking
├── optimization/     # Phase 3: Metrics-driven optimization engine
├── redteam/          # Phase 3: Red-team test harness and adversarial suites
├── operations/       # Phase 3: Operational runbooks
└── observability/    # Phase 3: SLO/SLA monitoring

tests/                # Test suite
```

## Setup

### Prerequisites

- Python 3.11 or higher
- pip or poetry
- **Phase 3 (Optional):**
  - LLM provider API keys (OpenAI, Grok, etc.) for LLM-enhanced reasoning
  - Kafka/MQ broker for streaming ingestion (optional)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd agentic-exception-platform
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

Or install with development dependencies:
```bash
pip install -r requirements.txt
pip install -e ".[dev]"
```

## Running the Application

### Development Server

Start the FastAPI development server:

```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Alternative API Docs: http://localhost:8000/redoc

### Health Check

```bash
curl http://localhost:8000/health
```

## Development

### Code Quality

Format code with Black:
```bash
black src tests
```

Lint with Ruff:
```bash
ruff check src tests
```

Type checking with mypy:
```bash
mypy src
```

### Running Tests

Run all tests:
```bash
pytest
```

Run with coverage (recommended):
```bash
# Linux/Mac
./scripts/run_tests.sh

# Windows
scripts\run_tests.bat

# Or manually
pytest --cov=src --cov-report=term-missing --cov-report=html --cov-report=xml
```

View coverage report:
- Terminal: Coverage summary shown after test run
- HTML: Open `htmlcov/index.html` in browser
- XML: `coverage.xml` for CI/CD integration

Coverage threshold: Tests will fail if coverage is below 85% (Phase 2 requirement).

## Phase 1, Phase 2 & Phase 3 MVP Status

**Phase 1 MVP:** ✅ COMPLETE (21 issues)
**Phase 2 MVP:** ✅ COMPLETE (25 issues)
**Phase 3 MVP:** ✅ COMPLETE (31 issues)

**Total Issues Implemented:** 77/77 (100% complete)

### Documentation

- **Technical Documentation:** See `TECHNICAL_README.md` for comprehensive architecture, subsystems, and deployment guide
- **MVP Issues Summary:** See `docs/MVP_ISSUES_SUMMARY.md` for complete issue tracking
- **Phase 1 Issues:** `.github/ISSUE_TEMPLATE/phase1-mvp-issues.md`
- **Phase 2 Issues:** `.github/ISSUE_TEMPLATE/phase2-mvp-issues.md`
- **Phase 3 Issues:** `.github/ISSUE_TEMPLATE/phase3-mvp-issues.md`

### Key Features Implemented

**Phase 1 & 2:**
- ✅ Multi-tenant agentic orchestration pipeline
- ✅ Domain abstraction via Domain Packs and Tenant Policy Packs
- ✅ Advanced RAG system with production vector database
- ✅ Robust tool execution engine with circuit breakers
- ✅ Human-in-the-loop approval workflow
- ✅ Rich observability (metrics, dashboards, alerts)
- ✅ Admin APIs for pack and tool management
- ✅ Multi-domain simulation and testing
- ✅ Comprehensive test coverage (>85%)

**Phase 3:**
- ✅ LLM-enhanced agent reasoning with explainable AI
- ✅ Safe JSON-bounded LLM outputs with schema validation
- ✅ LLM fallback strategies and circuit breakers
- ✅ Autonomous optimization (policy learning, playbook optimization, guardrail recommendations)
- ✅ Operator UI backend APIs (browsing, NLQ, simulation, supervisor dashboards)
- ✅ Streaming ingestion (Kafka/MQ) and incremental decision streaming
- ✅ Backpressure and rate control for streaming
- ✅ Expanded safety rules for LLM calls and tool usage
- ✅ Red-team test harness and adversarial test suites
- ✅ Policy violation and unauthorized tool usage detection
- ✅ Infrastructure hardening for many domains & tenants
- ✅ SLO/SLA metrics definitions and monitoring
- ✅ Tenancy-aware quotas and limits (LLM, vector DB, tool calls)
- ✅ Operational runbooks and incident playbooks
- ✅ Human-readable decision timelines
- ✅ Evidence tracking and attribution system
- ✅ Explanation API endpoints with quality scoring

## Architecture Principles

- **Domain Abstraction**: No hardcoding of domain-specific logic; all behavior is config-driven via Domain Packs and Tenant Policy Packs
- **Multi-Tenancy**: Strict isolation of data, memory, tools, and configurations per tenant
- **Agentic Orchestration**: Agents communicate via standardized contracts
- **Safety-First**: Guardrails, allow-lists, human-in-loop mechanisms, and comprehensive safety rules
- **Observability**: Integrated logging, metrics, dashboards, SLO/SLA monitoring, and explanation analytics
- **Explainability**: Full transparency with decision timelines, evidence tracking, and natural language explanations
- **Continuous Learning**: Autonomous optimization of policies, playbooks, and guardrails based on outcomes
- **Resilience**: LLM fallback strategies, circuit breakers, backpressure control, and graceful degradation
