# Playbooks Registry Demo Checklist

## Overview

The Admin Playbooks page provides a read-only registry view of all playbooks from active domain and tenant packs, implementing override logic where tenant playbooks take precedence over domain playbooks.

## Demo Preparation Checklist

### 1. Backend Setup ✅

- [ ] Verify `/admin/playbooks/registry` endpoint is working
- [ ] Confirm active domain packs exist in database
- [ ] Confirm active tenant packs exist in database
- [ ] Test override logic with tenant playbooks overriding domain playbooks
- [ ] Verify pagination and filtering functionality

### 2. Data Verification

- [ ] At least 1 active domain pack with playbooks
- [ ] At least 1 active tenant pack with playbooks
- [ ] Include at least 1 playbook override scenario (same playbook_id in domain and tenant)
- [ ] Verify playbook metadata includes:
  - playbook_id, name, description
  - exception_type or applies_to field
  - steps with tool references
  - domain and version information

### 3. Frontend Features

- [ ] Admin → Playbooks navigation working
- [ ] Registry table displays correctly
- [ ] Filters working (domain, exception type, source, search)
- [ ] Pagination working
- [ ] Actions working:
  - View Details (opens details modal)
  - View Diagram (placeholder functionality)
  - View Source Pack (placeholder functionality)

### 4. Demo Scenarios

#### Scenario 1: Basic Registry View

1. Navigate to Admin → Playbooks
2. Verify table shows playbooks from active packs
3. Point out columns:
   - Playbook ID and Name
   - Domain and Source (domain/tenant)
   - Step and Tool counts
   - Override indicators

#### Scenario 2: Filtering and Search

1. Filter by domain (show domain-specific playbooks)
2. Filter by source (show only domain or tenant playbooks)
3. Search by playbook name or ID
4. Clear filters to show all playbooks

#### Scenario 3: Override Demonstration

1. Show a playbook that exists in both domain and tenant packs
2. Explain that tenant version takes precedence
3. Show override indicator in the registry
4. Open details view to show override information

#### Scenario 4: Details View

1. Click "View Details" on any playbook
2. Show playbook metadata:
   - Basic information (ID, name, domain, type)
   - Step and tool counts
   - Source pack information
   - Override information (if applicable)
3. Demonstrate additional actions:
   - View Workflow Diagram (future feature)
   - View Source Pack (deep link)

### 5. Key Demo Points

#### Technical Architecture

- **Registry Aggregation**: Combines playbooks from all active packs
- **Override Logic**: Tenant packs override domain packs for same playbook_id
- **Read-Only Design**: View-only interface, no editing capabilities
- **Source Traceability**: Clear indication of which pack each playbook comes from

#### Business Value

- **Centralized View**: Single location to see all available playbooks
- **Multi-Tenant Support**: Tenant customizations visible alongside domain defaults
- **Operational Visibility**: Easy to see what playbooks are active and available
- **Troubleshooting**: Clear source tracking for debugging pack issues

### 6. Error Scenarios to Test

- [ ] No active packs (empty state)
- [ ] Packs with malformed playbook JSON (graceful handling)
- [ ] API connection issues (error display)
- [ ] Large number of playbooks (pagination performance)

### 7. Future Enhancements (Demo Context)

- **Workflow Diagram Viewer**: Visual representation of playbook steps
- **Deep Pack Navigation**: Direct links to source pack details
- **Execution History**: Link to exception history where playbooks were used
- **Playbook Analytics**: Usage statistics and performance metrics

## Demo Script

### Opening (30 seconds)

"The Admin Playbooks page provides a unified registry view of all playbooks available in your environment. This aggregates playbooks from both domain packs (organizational defaults) and tenant packs (customizations)."

### Registry Overview (60 seconds)

"Here you can see all active playbooks with key metadata: the playbook ID, name, which domain it applies to, whether it comes from a domain or tenant pack, and how many steps and tools it contains. Notice the override indicators showing where tenant playbooks take precedence."

### Filtering Demo (45 seconds)

"The filtering system lets you narrow down playbooks by domain, exception type, source pack type, or search by name. This is especially useful in large environments with hundreds of playbooks."

### Details View (60 seconds)

"The details view shows comprehensive metadata about each playbook, including its source pack information and any override relationships. This provides full traceability for operations and troubleshooting."

### Closing (15 seconds)

"This read-only registry provides operational visibility into your playbook inventory while maintaining the configuration through the pack management system."

## Success Criteria

- ✅ Registry loads within 3 seconds with realistic data volume
- ✅ All filters work correctly and provide immediate feedback
- ✅ Override logic is clearly visible and explained
- ✅ Navigation to/from other admin pages works seamlessly
- ✅ Details view provides actionable information
- ✅ No browser console errors during demo
