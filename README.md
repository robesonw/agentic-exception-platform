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

Coverage threshold: Tests will fail if coverage is below 80%.

## Phase 1 MVP Status

This is the foundational scaffolding phase. Business logic implementation is tracked in:
- `.github/ISSUE_TEMPLATE/phase1-mvp-issues.md`

Current status: Structural scaffolding complete. Ready for business logic implementation.

## Architecture Principles

- **Domain Abstraction**: No hardcoding of domain-specific logic; all behavior is config-driven via Domain Packs and Tenant Policy Packs
- **Multi-Tenancy**: Strict isolation of data, memory, tools, and configurations per tenant
- **Agentic Orchestration**: Agents communicate via standardized contracts
- **Safety-First**: Guardrails, allow-lists, and human-in-loop mechanisms
- **Observability**: Integrated logging, metrics, and dashboards
