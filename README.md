# Agentic Exception Processing Platform (MVP)

Domain-Abstracted Agentic AI Platform for Multi-Tenant Exception Processing.

This repo implements the MVP described in `docs/06-mvp-plan.md`.

## Documentation

Start here:
- `docs/master_project_instruction_full.md` - Master project specification
- `docs/01-architecture.md` - System architecture
- `docs/03-data-models-apis.md` - Data models and API specifications
- `docs/06-mvp-plan.md` - MVP implementation plan
- `docs/phase6-persistence-mvp.md` - Phase 6: Persistence & State Management (see [Phase 6 section](#phase-6-persistence--state-management) below)
- `docs/playbooks-configuration.md` - Playbooks configuration guide (schema, conditions, actions, examples)
- `docs/playbooks-api.md` - Playbooks API reference (endpoints, schemas, examples)
- `docs/phase7-completion-report.md` - Phase 7 completion report (implementation status, how to run, limitations)
- `docs/phase8-tools-mvp.md` - Phase 8: Tool Registry & Execution MVP specification
- `docs/tools-guide.md` - Complete tool guide (schema, APIs, enable/disable, security, troubleshooting)

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
├── observability/    # Phase 3: SLO/SLA monitoring
├── infrastructure/   # Phase 6: Database models, repositories, session management
│   ├── db/          # Database models and session management
│   └── repositories/# DB-backed repository implementations
├── repository/       # Phase 6: Repository layer (DTOs, base classes)
└── copilot/          # Phase 5: Co-Pilot (uses Phase 6 repositories)

tests/                # Test suite
```

## Setup

### Prerequisites

- Python 3.11 or higher
- pip or poetry
- **Phase 6 (Required):**
  - PostgreSQL 12 or higher
  - Database connection configured via `DATABASE_URL` environment variable
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

4. **Phase 6: Database Setup:**
   
   **Option A: Using Docker (Recommended for Development)**
   ```bash
   # Start PostgreSQL in Docker
   # Windows (PowerShell):
   .\scripts\docker_db.ps1 start
   
   # Linux/Mac:
   ./scripts/docker_db.sh start
   
   # Or use docker-compose directly:
   docker-compose up -d postgres
   
   # Set database URL
   # Windows (PowerShell):
   $env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai"
   
   # Linux/Mac:
   export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai
   
   # Run initial migrations
   alembic upgrade head
   ```
   
   **Option B: Local PostgreSQL Installation**
   ```bash
   # Create database
   createdb -U postgres sentinai
   
   # Set database URL (or add to .env file)
   export DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@localhost:5432/sentinai
   
   # Run initial migrations
   alembic upgrade head
   ```
   
   See `docs/docker-postgres-setup.md` for Docker setup details.
   See `docs/database-migrations.md` for detailed migration instructions.

   **Option C: Full Stack with Docker Compose (Recommended for Quick Start)**
   
   **Quick Start Scripts:**
   
   **Linux/Mac:**
   ```bash
   # Start all services (infrastructure + backend + UI)
   ./scripts/start-all.sh
   
   # Start workers (in separate terminals or background)
   ./scripts/start-workers.sh
   
   # Check status
   ./scripts/status.sh
   
   # Stop all services
   ./scripts/stop-all.sh
   
   # Restart all services
   ./scripts/restart-all.sh
   ```
   
   **Windows (PowerShell):**
   ```powershell
   # Start all services (infrastructure + backend + UI)
   .\scripts\start-all.ps1
   
   # Start workers (in separate terminals or background)
   .\scripts\start-workers.ps1
   
   # Check status
   .\scripts\status.ps1
   
   # Stop all services
   .\scripts\stop-all.ps1
   
   # Restart all services
   .\scripts\restart-all.ps1
   ```
   
   **Manual Docker Compose:**
   ```bash
   # Start all services (PostgreSQL, Kafka, Backend API, UI)
   docker compose up --build
   
   # Or run in detached mode
   docker compose up -d --build
   
   # View logs
   docker compose logs -f
   
   # Stop all services
   docker compose down
   
   # Stop and remove volumes (clean slate)
   docker compose down -v
   ```
   
   Once running, access:
   - **API**: http://localhost:8000
   - **API Documentation**: http://localhost:8000/docs
   - **UI**: http://localhost:3000
   
   See [`docs/phase6-persistence-mvp.md`](docs/phase6-persistence-mvp.md#docker-compose-setup) for more details.

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

### Starting Workers (Required for Processing Exceptions)

**IMPORTANT**: The platform uses an event-driven architecture. After starting the API server, you **must** also start workers to process exceptions through the pipeline.

Workers consume events from Kafka and process exceptions through the agent pipeline:
- `IntakeWorker` → Normalizes exceptions
- `TriageWorker` → Classifies exceptions  
- `PolicyWorker` → Evaluates policies
- `PlaybookWorker` → Matches playbooks
- `ToolWorker` → Executes tools
- `FeedbackWorker` → Captures feedback

**Quick Start:**
```bash
# Terminal 1: Intake Worker
WORKER_TYPE=intake CONCURRENCY=1 GROUP_ID=intake-workers python -m src.workers

# Terminal 2: Triage Worker
WORKER_TYPE=triage CONCURRENCY=1 GROUP_ID=triage-workers python -m src.workers

# Terminal 3: Policy Worker
WORKER_TYPE=policy CONCURRENCY=1 GROUP_ID=policy-workers python -m src.workers

# Terminal 4: Playbook Worker
WORKER_TYPE=playbook CONCURRENCY=1 GROUP_ID=playbook-workers python -m src.workers
```

**See `docs/WORKERS_QUICK_START.md` for detailed instructions.**

**Note**: If exceptions are ingested but not processed, check that:
1. Kafka is running
2. Workers are running
3. Database is accessible
4. Environment variables are set correctly

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

## Phase 1, Phase 2, Phase 3, Phase 6, Phase 7 & Phase 8 MVP Status

**Phase 1 MVP:** ✅ COMPLETE (21 issues)
**Phase 2 MVP:** ✅ COMPLETE (25 issues)
**Phase 3 MVP:** ✅ COMPLETE (31 issues)
**Phase 6 MVP:** ✅ COMPLETE (Persistence & State Management)
**Phase 7 MVP:** ✅ COMPLETE (Playbooks & Actions)
**Phase 8 MVP:** ✅ COMPLETE (Tool Registry & Execution)

**Total Issues Implemented:** 117+ issues across all phases (100% complete)

### Documentation

- **Technical Documentation:** See `TECHNICAL_README.md` for comprehensive architecture, subsystems, and deployment guide
- **MVP Issues Summary:** See `docs/MVP_ISSUES_SUMMARY.md` for complete issue tracking
- **Phase 1 Issues:** `.github/ISSUE_TEMPLATE/phase1-mvp-issues.md`
- **Phase 2 Issues:** `.github/ISSUE_TEMPLATE/phase2-mvp-issues.md`
- **Phase 3 Issues:** `.github/ISSUE_TEMPLATE/phase3-mvp-issues.md`
- **Phase 8 Issues:** `.github/ISSUE_TEMPLATE/phase8-mvp-issues.md`

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

**Phase 6:**
- ✅ PostgreSQL-backed persistence (system-of-record database)
- ✅ DB-backed repositories for all core entities (exceptions, events, tenants, domain packs, policy packs, playbooks, tools)
- ✅ Append-only exception event log with full audit trail
- ✅ Tenant isolation enforced at database layer
- ✅ Idempotent write operations (upsert, append_if_new)
- ✅ Database migrations with Alembic
- ✅ Health check endpoints (`/health/db`)
- ✅ Comprehensive repository and API test coverage

**Phase 7:**
- ✅ Playbook matching service (condition-based selection from database)
- ✅ Playbook execution service (step-by-step execution with action executors)
- ✅ Agent integration (TriageAgent suggests, PolicyAgent assigns, ResolutionAgent aligns, FeedbackAgent computes metrics)
- ✅ Playbook API endpoints (recalculate, status, step completion)
- ✅ UI integration (playbook panel, step completion, timeline events)
- ✅ Playbook events (PlaybookAssigned, PlaybookRecalculated, PlaybookStepCompleted, PlaybookCompleted)
- ✅ Comprehensive playbook configuration and API documentation

**Phase 8:**
- ✅ Tool Registry with global and tenant-scoped tools
- ✅ Tool definition schema with JSON Schema validation
- ✅ Tool execution service with lifecycle events (requested, running, succeeded, failed)
- ✅ Tool enable/disable per tenant
- ✅ HTTP tool provider with URL allow-list enforcement
- ✅ Secret redaction in logs and events
- ✅ API key management via environment variables
- ✅ Tool execution APIs (execute, list executions, get execution detail)
- ✅ UI for tool management (list, detail, execute)
- ✅ Tool execution events in exception timeline
- ✅ Comprehensive security features (URL validation, secret masking, tenant isolation)
- ✅ Integration tests and >80% code coverage for tool components
- ✅ Complete documentation (schema, APIs, security, troubleshooting)

## Phase 6: Persistence & State Management

**If you want to understand how persistence works, start here:**

Phase 6 introduces **durable persistence** and **state management** for the platform. All exception data, events, and configurations are now stored in PostgreSQL, replacing the in-memory implementations from earlier phases.

### What Phase 6 Adds

- **PostgreSQL-backed persistence**: System-of-record database for all platform data
- **System-of-record tables**: Exceptions, tenants, domain packs, tenant policy packs, playbooks, tools, and more
- **Append-only event log**: Complete audit trail of all agent actions and state changes
- **DB-backed repositories**: All data access goes through repository layer with tenant isolation
- **Database migrations**: Alembic-based schema management
- **Health monitoring**: Database connectivity checks and health endpoints

### Quick Start

**Configure Database Connection:**

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env  # Linux/Mac
   copy .env.example .env  # Windows
   ```

2. Update `.env` with your database credentials (see [`docs/configuration.md`](docs/configuration.md) for details)

3. Or set the `DATABASE_URL` environment variable directly:

```bash
# Windows (PowerShell)
$env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai"

# Linux/Mac
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai
```

Or use individual components:
```bash
export DB_USER=postgres
export DB_PASSWORD=yourpassword
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=sentinai
```

**Run Migrations:**

```bash
# Create initial schema
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"
```

**Run Tests:**

```bash
# Run all repository tests
pytest tests/repository tests/infrastructure/repositories -v -m phase6

# Run API tests with DB
pytest tests/api/test_exceptions_api_phase6.py -v

# Run health check tests
pytest tests/api/test_health_db.py -v -m phase6
```

### Where to Read More

- **Configuration Guide**: [`docs/configuration.md`](docs/configuration.md) - Complete environment variable reference and configuration options
- **Full Phase 6 Documentation**: [`docs/phase6-persistence-mvp.md`](docs/phase6-persistence-mvp.md) - Complete specification, schema design, and implementation details
- **Database Setup**: [`docs/docker-postgres-setup.md`](docs/docker-postgres-setup.md) - Docker-based PostgreSQL setup
- **Migrations Guide**: [`docs/database-migrations.md`](docs/database-migrations.md) - Alembic migration workflow
- **Repository Tests**: [`tests/repository/README.md`](tests/repository/README.md) - Repository test suite documentation
- **Architecture**: [`docs/01-architecture.md`](docs/01-architecture.md) - System architecture (includes persistence layer and playbook flows)
- **Playbooks Configuration**: [`docs/playbooks-configuration.md`](docs/playbooks-configuration.md) - Playbook schema, conditions, actions, examples
- **Playbooks API**: [`docs/playbooks-api.md`](docs/playbooks-api.md) - API endpoints for playbook operations

## Phase 7: Playbooks & Actions

**If you want to understand how playbooks work, start here:**

Phase 7 introduces **playbook matching and execution** capabilities. Playbooks define sequences of steps that are automatically matched to exceptions and executed to resolve them.

### What Phase 7 Adds

- **Playbook Matching Service**: Condition-based playbook selection (domain, exception type, severity, SLA, policy tags)
- **Playbook Execution Service**: Step-by-step execution with action executors (notify, assign_owner, set_status, add_comment, call_tool)
- **Agent Integration**: 
  - TriageAgent suggests playbooks during classification
  - PolicyAgent approves and assigns playbooks to exceptions
  - ResolutionAgent aligns resolution plans with playbook steps
  - FeedbackAgent computes playbook execution metrics
- **Playbook API Endpoints**: Recalculate, get status, complete steps
- **UI Integration**: Playbook panel, step completion, timeline events
- **Playbook Events**: Complete event log for playbook lifecycle (assigned, recalculated, step completed, completed)

### Where to Read More

- **Configuration Guide**: [`docs/playbooks-configuration.md`](docs/playbooks-configuration.md) - Complete playbook configuration guide
- **API Reference**: [`docs/playbooks-api.md`](docs/playbooks-api.md) - Playbook API endpoints and examples
- **Full Phase 7 Documentation**: [`docs/phase7-playbooks-mvp.md`](docs/phase7-playbooks-mvp.md) - Complete specification and implementation details
- **Architecture**: [`docs/01-architecture.md`](docs/01-architecture.md) - System architecture (includes playbook flows)

### Key Concepts

- **Repository Pattern**: All database access goes through repositories (`src/infrastructure/repositories/` and `src/repository/`)
- **Tenant Isolation**: Every query enforces `tenant_id` filtering to prevent cross-tenant data leakage
- **Idempotent Operations**: Safe retry/replay with `upsert_exception` and `append_event_if_new`
- **Event Log**: Immutable append-only log of all exception lifecycle events

## Architecture Principles

- **Domain Abstraction**: No hardcoding of domain-specific logic; all behavior is config-driven via Domain Packs and Tenant Policy Packs
- **Multi-Tenancy**: Strict isolation of data, memory, tools, and configurations per tenant
- **Agentic Orchestration**: Agents communicate via standardized contracts
- **Safety-First**: Guardrails, allow-lists, human-in-loop mechanisms, and comprehensive safety rules
- **Observability**: Integrated logging, metrics, dashboards, SLO/SLA monitoring, and explanation analytics
- **Explainability**: Full transparency with decision timelines, evidence tracking, and natural language explanations
- **Continuous Learning**: Autonomous optimization of policies, playbooks, and guardrails based on outcomes
- **Resilience**: LLM fallback strategies, circuit breakers, backpressure control, and graceful degradation
