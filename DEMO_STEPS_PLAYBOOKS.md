# Demo Steps - Admin Playbooks Registry

## ✅ VERIFIED WORKING - Demo Navigation Path

### Prerequisites Verified ✅

- Backend: http://localhost:8000 (running)
- Frontend: http://localhost:3000 (running)
- Database: 10 playbooks from CMT3 domain pack (populated)
- Registry API: Returns real data (verified)

### Demo Steps

#### 1. Navigate to Domain Packs (Show Context)

```
Admin Dashboard → Packs → Domain Packs
```

**What to show:**

- Active CMT3 domain pack (version v1.0)
- Click "View Details" to show the pack contains playbooks
- Highlight that this pack is ACTIVE and contains 5 playbook definitions

#### 2. Navigate to Playbooks Registry (Main Feature)

```
Admin Dashboard → Playbooks
```

**What to show:**

- Registry table displays 10 playbooks (5 exception types shown)
- Each playbook auto-generated from domain pack:
  - Name: "Playbook for {EXCEPTION_TYPE}"
  - ID: "CMT3.{exception_type_lowercase}"
  - Domain: CMT3
  - Source: domain pack
  - Steps count: 4-6 steps per playbook

#### 3. Demonstrate Registry Features

**Filter by Domain:**

- Select "CMT3" from domain filter
- Shows all 5 playbook types for that domain

**View Playbook Details:**

- Click "View Details" on any playbook
- Modal shows:
  - Step-by-step workflow
  - Exception type mapping
  - Source pack attribution
  - Auto-generated descriptions

**Demo Data Available:**

1. **MISMATCHED_TRADE_DETAILS** (6 steps)
2. **FAILED_ALLOCATION** (4 steps)
3. **POSITION_BREAK** (4 steps)
4. **SETTLEMENT_FAIL** (4 steps)
5. **REG_REPORT_REJECTED** (4 steps)

### Key Points to Highlight

#### Technical Implementation

- **Field Extraction Fix**: Registry properly extracts playbooks from domain packs
- **Auto-Generation**: Missing names/IDs generated from exception types
- **Read-Only Interface**: Safe for demo (no accidental changes)
- **Real Data**: Not mock data - actual extracted from active domain pack

#### Business Value

- **Aggregation**: Shows all playbooks across domain and tenant packs
- **Override Logic**: Tenant packs override domain (when present)
- **Operational View**: Admin can see all automated workflows
- **Audit Trail**: Source pack attribution for governance

### API Verification Commands

```powershell
# Show active packs
Invoke-RestMethod -Uri "http://localhost:8000/admin/packs/domain" -Headers @{"x-api-key"="test-api-key-123"; "x-tenant-id"="tenant_001"}

# Show registry content
Invoke-RestMethod -Uri "http://localhost:8000/admin/playbooks/registry" -Headers @{"x-api-key"="test-api-key-123"; "x-tenant-id"="tenant_001"}
```

### Expected Demo Outcome

- **Before**: "No records found" (issue was field extraction)
- **After**: 10 playbooks displayed with proper names and metadata
- **Navigation**: Smooth flow from Domain Packs → Playbooks Registry
- **Functionality**: All filtering, details modal, and pagination working

## Status: ✅ DEMO READY
