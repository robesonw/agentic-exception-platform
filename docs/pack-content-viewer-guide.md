---
title: "Pack Content Viewer - User Guide"
description: "How to use the enhanced Pack Content Viewer for domain packs and tenant packs"
phase: "12-13"
created: "2024-01-20"
---

# Pack Content Viewer - Admin Guide

## Overview

The Pack Content Viewer has been upgraded to provide comprehensive visibility into domain packs and tenant packs beyond basic metadata. This guide covers the new functionality.

## Accessing Pack Content

1. **Navigate to Admin → Domain Packs or Tenant Packs**
2. **Click "View" on any pack in the list**
3. **The content viewer will open with 5 tabs:**

### Tab 1: Overview

- **Purpose**: High-level metadata and summary
- **Shows**:
  - Pack name, version, checksum
  - Created date and active status
  - Quick summary of contents (playbook count, tool count, etc.)
  - Domain classification

### Tab 2: Raw JSON

- **Purpose**: Technical inspection of the full pack content
- **Shows**: Complete JSON structure with syntax highlighting
- **Use Case**: Debugging, technical validation

### Tab 3: Playbooks

- **Purpose**: Structured view of all playbooks in the pack
- **Shows**:
  - Playbook table with ID, name, description, trigger conditions
  - Expandable sections for each playbook
  - Step-by-step breakdown with types and parameters
  - Condition logic for execution paths

### Tab 4: Tools

- **Purpose**: Tool definitions with security considerations
- **Shows**:
  - Accordion view of all tools
  - Tool parameters with **automatic secret redaction**
  - Input/output schemas
  - Safety: Passwords, API keys, tokens are masked as `***REDACTED***`

### Tab 5: Policies

- **Purpose**: Policy document and rule summary
- **Shows**:
  - Policy clauses organized by type
  - Enforcement levels (enforce/warn/log)
  - Compliance requirements
  - Integration points

## Security Features

### Secret Redaction

The viewer automatically redacts sensitive information:

- **Password fields**: `password`, `pwd`, `secret`
- **API credentials**: `api_key`, `auth_token`, `credential`
- **Connection strings**: Database URLs with embedded passwords
- **Environment variables**: Any field containing sensitive patterns

**Example**:

```json
// Original
{
  "database_url": "postgresql://user:secret123@localhost:5432/db",
  "api_key": "sk-abc123def456"
}

// Displayed
{
  "database_url": "postgresql://***REDACTED***:***REDACTED***@localhost:5432/db",
  "api_key": "***REDACTED***"
}
```

## Navigation Tips

1. **Quick Overview**: Start with the "Overview" tab for a summary
2. **Technical Details**: Use "Playbooks" and "Tools" tabs for operational understanding
3. **Debugging**: Use "Raw JSON" tab when investigating configuration issues
4. **Compliance**: Check "Policies" tab for governance and audit requirements

## Performance Notes

- **List views** (main pack tables) do NOT load full content for performance
- **Detail views** (when clicking "View") load complete pack content
- Large packs may take a moment to render all tabs

## Future Enhancements

- **Playbook Diagrams**: Visual workflow representation (planned)
- **Tool Testing**: Direct tool parameter validation (planned)
- **Policy Simulation**: Test policy rules against sample data (planned)

---

## Technical Implementation

### Backend Changes

- Enhanced `PackResponse` model with `content_json` field
- Updated `/api/onboarding/domain-packs/{id}` and `/api/onboarding/tenant-packs/{id}` endpoints
- Maintained performance separation between list and detail operations

### Frontend Changes

- New `PackContentViewer.tsx` component with tabbed interface
- Integrated into existing `PacksPage.tsx` admin interface
- Automatic secret redaction in tool parameters
- Material-UI based responsive design

### Security Considerations

- Server-side tenant isolation maintained
- Client-side secret redaction as additional safety layer
- Audit logging for pack content access (existing infrastructure)
- RBAC enforcement for admin-only access (existing middleware)

---

_This enhancement is part of Phase 12-13 UI improvements to the SentinAI Exception Processing Platform._
