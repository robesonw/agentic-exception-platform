# Demo Data Seeding Guide

This guide explains how to use the demo data seeder to populate the SentinAI platform with realistic sample data for demonstrations and testing.

## Overview

The demo data seeder generates comprehensive sample data across all platform capabilities (Phases 4-8):

- **Tenants**: Pre-configured demo tenants (Finance and Healthcare)
- **Domain Packs**: Domain-specific configurations
- **Tenant Policy Packs**: Tenant-specific policy configurations
- **Exceptions**: Realistic exception records with various attributes
- **Exception Events**: Full event timelines for each exception
- **Playbooks**: Resolution playbooks with multiple steps
- **Tools**: Global and tenant-scoped tool definitions
- **Tool Executions**: Tool execution records linked to exceptions
- **Tool Enablements**: Per-tenant tool enablement policies

## Quick Start

### Prerequisites

1. Database is set up and accessible (configured via `DATABASE_URL`)
2. Virtual environment is activated (`.venv`)
3. Dependencies are installed

### Basic Usage

Seed a single tenant:

```bash
python scripts/seed_demo_data.py --tenant TENANT_FINANCE_001 --domain CapitalMarketsTrading --count 200 --reset
```

Seed all configured tenants:

```bash
python scripts/seed_demo_data.py --all-tenants --count 500 --reset
```

## Command-Line Options

### Required Arguments

- `--tenant TENANT_ID`: Tenant identifier to seed (e.g., `TENANT_FINANCE_001`)
- `--domain DOMAIN_NAME`: Domain name (`CapitalMarketsTrading` or `HealthcareClaimsAndCareOps`)

**OR**

- `--all-tenants`: Seed all configured tenants (cannot be used with `--tenant` or `--domain`)

### Optional Arguments

- `--count N`: Number of exceptions to generate per tenant (default: 100)
- `--reset`: Clear existing demo data for tenant(s) before seeding
- `--seed N`: Random seed for deterministic generation (useful for reproducible tests)

## Configured Tenants

The seeder includes two pre-configured demo tenants:

### TENANT_FINANCE_001
- **Name**: Finance Trading Demo Tenant
- **Domain**: CapitalMarketsTrading
- **Exception Types**: Settlement failures, allocation mismatches, position discrepancies, regulatory report rejections, etc.
- **Tools**: Trading system tools (getOrder, getAllocations, repairAllocation, etc.)

### TENANT_HEALTH_001
- **Name**: Healthcare Claims Demo Tenant
- **Domain**: HealthcareClaimsAndCareOps
- **Exception Types**: Missing authorizations, code mismatches, provider credential issues, patient demographic conflicts, etc.
- **Tools**: Healthcare system tools (getClaim, getAuthorization, reprocessClaim, etc.)

## What Gets Generated

### Tenants
- Active tenant records with proper metadata

### Domain Packs
- Loaded from sample files in `domainpacks/` directory
- Includes entity definitions, exception types, severity rules, tools, playbooks, and guardrails

### Tenant Policy Packs
- Loaded from sample files in `tenantpacks/` directory
- Includes custom severity overrides, guardrails, approved tools, human approval rules, and retention policies

### Exceptions
- Realistic exception IDs (e.g., `EXC-FIN-20250115-00001`)
- Distributed timestamps over the last 7 days
- Various severities (LOW, MEDIUM, HIGH, CRITICAL)
- Multiple statuses (OPEN, ANALYZING, RESOLVED, ESCALATED)
- SLA deadlines (some near breach)
- Entity identifiers, amounts, source systems
- Linked to playbooks (80% of exceptions)

### Exception Events
- Full event timelines for each exception:
  - `ExceptionIngested`
  - `ExceptionCreated`
  - `TriageCompleted` (with suggested playbook)
  - `PolicyEvaluated` (with selected playbook)
  - `PlaybookStarted`
  - `PlaybookStepCompleted` (for each step)
  - `ToolExecutionRequested` / `ToolExecutionCompleted` (for call_tool steps)
  - `ResolutionSuggested` (for resolved exceptions)
  - `PlaybookCompleted` (for resolved exceptions)
  - `FeedbackCaptured` (for resolved exceptions)

### Playbooks
- 6 playbooks per tenant
- Each playbook has 3-6 steps
- Steps include: notify, assign_owner, set_status, add_comment, call_tool, escalate
- Matching conditions based on domain, exception type, severity, and policy tags

### Tools
- **Global Tools** (3): Available to all tenants
  - `notifySlack`, `sendEmail`, `createJiraTicket`
- **Tenant Tools** (3 per tenant): Tenant-specific tools
  - Finance: `getOrder`, `getAllocations`, `repairAllocation` (and others)
  - Healthcare: `getClaim`, `getAuthorization`, `reprocessClaim` (and others)
- **Dummy Tool** (1 per tenant): For testing dummy tool provider

### Tool Executions
- Created for exceptions that have `call_tool` steps in their playbooks
- Linked to exceptions via `exception_id`
- Includes input/output payloads
- 90% success rate (10% failures for realism)

### Tool Enablements
- All tenant tools are enabled by default
- Explicit enablement records created for tenant-scoped tools

## Deterministic Seeding

Use the `--seed` option for reproducible data generation:

```bash
python scripts/seed_demo_data.py --all-tenants --count 100 --seed 42
```

With the same seed, the same data will be generated (useful for testing and demos).

## Resetting Data

Use the `--reset` flag to clear existing demo data before seeding:

```bash
python scripts/seed_demo_data.py --tenant TENANT_FINANCE_001 --domain CapitalMarketsTrading --count 200 --reset
```

**Warning**: This will delete all data for the specified tenant(s), including:
- Exceptions and events
- Playbooks and steps
- Tool definitions and executions
- Tenant policy packs

Tenant records and domain packs are preserved.

## Data Realism

The seeder generates realistic data:

- **Timestamps**: Distributed over the last 7 days
- **SLA Deadlines**: Based on severity (CRITICAL: 2h, HIGH: 8h, MEDIUM: 24h, LOW: 72h)
- **Amounts**: Domain-appropriate ranges (Finance: $1K-$1M, Healthcare: $100-$50K)
- **Status Distribution**: 40% OPEN, 30% ANALYZING, 20% RESOLVED, 10% ESCALATED
- **Event Timelines**: Realistic time gaps between events (minutes to hours)
- **Tool Execution**: 90% success rate, realistic input/output payloads

## UI Friendliness

The generated data is designed to showcase all UI features:

- **Exceptions List**: Populated with various statuses, severities, and domains
- **Exception Detail**: Shows playbook panel with step statuses
- **Timeline View**: Displays full event history with tool executions
- **Tools Page**: Lists all tools (global + tenant) with recent executions
- **Analytics**: Event counts and durations suitable for dashboard visualization

## Troubleshooting

### Database Connection Errors

Ensure `DATABASE_URL` is set correctly:

```bash
export DATABASE_URL="postgresql+asyncpg://user:password@localhost/dbname"
```

### Foreign Key Constraint Errors

If you see foreign key errors, use `--reset` to clear existing data first.

### Missing Domain Pack Files

If domain pack files are missing, the seeder will create minimal packs. For full functionality, ensure sample files exist in:
- `domainpacks/finance.sample.json`
- `domainpacks/healthcare.sample.json`
- `tenantpacks/tenant_finance.sample.json`
- `tenantpacks/tenant_healthcare.sample.json`

## Testing

Run the smoke test to verify seeding works:

```bash
pytest tests/integration/test_demo_seed_smoke.py -v
```

## Examples

### Small Demo (Quick)
```bash
python scripts/seed_demo_data.py --all-tenants --count 50 --reset
```

### Full Demo (Comprehensive)
```bash
python scripts/seed_demo_data.py --all-tenants --count 500 --reset
```

### Single Tenant, Deterministic
```bash
python scripts/seed_demo_data.py --tenant TENANT_FINANCE_001 --domain CapitalMarketsTrading --count 200 --seed 12345 --reset
```

## Architecture Notes

The seeder follows the repository pattern and respects tenant isolation:

- All data generation respects tenant boundaries
- Uses existing repositories (no raw SQL)
- Follows the same patterns as production code
- Safe for use in development and demo environments

## Security Notes

- Demo data uses dummy endpoints (`http://localhost:8000/demo/tools/...`)
- API keys are masked in logs (value: `demo-key-12345`)
- No external calls are made during seeding
- All data is clearly marked as demo data in payloads










