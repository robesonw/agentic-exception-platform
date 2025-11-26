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
├── agents/           # Agent implementations
├── orchestrator/     # Agent pipeline orchestrator
└── audit/            # Audit trail and metrics

tests/                # Test suite
```

## Setup

### Prerequisites

- Python 3.11 or higher
- pip or poetry

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

## Phase 1 & Phase 2 MVP Status

**Phase 1 MVP:** ✅ COMPLETE (21 issues)
**Phase 2 MVP:** ✅ COMPLETE (25 issues)

**Total Issues Implemented:** 46/46 (100% complete)

### Documentation

- **Technical Documentation:** See `TECHNICAL_README.md` for comprehensive architecture, subsystems, and deployment guide
- **MVP Issues Summary:** See `docs/MVP_ISSUES_SUMMARY.md` for complete issue tracking
- **Phase 1 Issues:** `.github/ISSUE_TEMPLATE/phase1-mvp-issues.md`
- **Phase 2 Issues:** `.github/ISSUE_TEMPLATE/phase2-mvp-issues.md`

### Key Features Implemented

- ✅ Multi-tenant agentic orchestration pipeline
- ✅ Domain abstraction via Domain Packs and Tenant Policy Packs
- ✅ Advanced RAG system with production vector database
- ✅ Robust tool execution engine with circuit breakers
- ✅ Human-in-the-loop approval workflow
- ✅ Rich observability (metrics, dashboards, alerts)
- ✅ Admin APIs for pack and tool management
- ✅ Multi-domain simulation and testing
- ✅ Comprehensive test coverage (>85%)

## Architecture Principles

- **Domain Abstraction**: No hardcoding of domain-specific logic; all behavior is config-driven via Domain Packs and Tenant Policy Packs
- **Multi-Tenancy**: Strict isolation of data, memory, tools, and configurations per tenant
- **Agentic Orchestration**: Agents communicate via standardized contracts
- **Safety-First**: Guardrails, allow-lists, and human-in-loop mechanisms
- **Observability**: Integrated logging, metrics, and dashboards
