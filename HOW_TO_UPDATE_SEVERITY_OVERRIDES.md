# How to Update Severity Overrides (Change Exception Severity)

## Important: Severity Overrides are in Tenant Policy Packs, NOT Domain Packs!

Severity overrides are configured in **Tenant Policy Packs** via the `customSeverityOverrides` field, not in Domain Packs.

---

## Overview

The system uses **versioning** for packs - you cannot edit packs in place. To change a severity override, you need to:

1. **Get the current Tenant Policy Pack** JSON
2. **Modify the `customSeverityOverrides` array** to add/update your override
3. **Import the modified pack as a new version**
4. **Activate the new version**

---

## Step-by-Step Guide

### Step 1: Navigate to Packs Management

1. Go to: `http://localhost:3000/admin/packs`
2. Click on the **"Tenant Packs"** tab
3. Find your tenant's policy pack (e.g., `TENANT_FINANCE_001`)

### Step 2: View Current Pack Content

1. Click **"View"** button on the active pack version
2. This opens the pack detail view showing the JSON content
3. Look for the `customSeverityOverrides` field

**Current structure example:**
```json
{
  "tenantId": "TENANT_FINANCE_001",
  "domainName": "CapitalMarketsTrading",
  "customSeverityOverrides": [
    {
      "exceptionType": "REG_REPORT_REJECTED",
      "severity": "HIGH"
    },
    {
      "exceptionType": "SEC_MASTER_MISMATCH",
      "severity": "LOW"
    }
  ],
  "customGuardrails": { ... },
  "approvedTools": [ ... ],
  "humanApprovalRules": [ ... ],
  "retentionPolicies": { ... },
  "customPlaybooks": [ ... ]
}
```

### Step 3: Modify the Severity Override

**To change an existing exception type from HIGH to LOW:**

1. Find the exception type in `customSeverityOverrides` array
2. Change the `severity` value from `"HIGH"` to `"LOW"`

**Example - Changing POSITION_BREAK from HIGH to LOW:**
```json
"customSeverityOverrides": [
  {
    "exceptionType": "POSITION_BREAK",
    "severity": "LOW"  // Changed from "HIGH"
  },
  // ... other overrides
]
```

**To add a new severity override:**

Add a new object to the `customSeverityOverrides` array:
```json
"customSeverityOverrides": [
  // ... existing overrides
  {
    "exceptionType": "YOUR_EXCEPTION_TYPE",
    "severity": "LOW"
  }
]
```

**Valid severity values:** `"LOW"`, `"MEDIUM"`, `"HIGH"`, `"CRITICAL"`

### Step 4: Import the Modified Pack as New Version

1. Go back to the Packs Management page (`/admin/packs`)
2. Click **"Import Tenant Pack"** button
3. In the import dialog:
   - **Tenant ID**: Your tenant ID (e.g., `TENANT_FINANCE_001`)
   - **Version**: Use a new version number (e.g., if current is `v1.0`, use `v1.1`)
   - **Content**: Paste the modified JSON (with updated `customSeverityOverrides`)
4. Click **"Validate"** to check for errors
5. If validation passes, click **"Import"**

### Step 5: Activate the New Version

1. After import, the new pack version will appear in the list (status: `DRAFT`)
2. Find the new version in the table
3. Click **"Activate"** button
4. Confirm activation
5. The new version becomes active and severity overrides take effect

---

## Alternative: Using API Directly

If you prefer using the API:

### 1. Get Current Tenant Pack

```bash
GET /admin/packs/tenant/{tenant_id}/{version}
```

### 2. Modify the JSON

Edit the `customSeverityOverrides` array in the response JSON.

### 3. Import New Version

```bash
POST /admin/packs/tenant/import
Content-Type: application/json

{
  "tenant_id": "TENANT_FINANCE_001",
  "version": "v1.1",
  "content": {
    "tenantId": "TENANT_FINANCE_001",
    "domainName": "CapitalMarketsTrading",
    "customSeverityOverrides": [
      {
        "exceptionType": "POSITION_BREAK",
        "severity": "LOW"
      }
    ],
    // ... rest of pack content
  }
}
```

### 4. Activate New Version

```bash
POST /admin/packs/activate
Content-Type: application/json

{
  "tenant_id": "TENANT_FINANCE_001",
  "domain_pack_version": "v1.0",  // Keep same domain pack version
  "tenant_pack_version": "v1.1",  // New tenant pack version
  "require_approval": false
}
```

---

## How Severity Overrides Work

1. **Domain Pack** defines base severity rules for exception types
2. **Tenant Policy Pack** `customSeverityOverrides` **overrides** the domain pack severity for specific exception types
3. When an exception is processed:
   - TriageAgent first applies domain pack severity rules
   - PolicyAgent then applies tenant policy severity overrides
   - Final severity = override value (if override exists) OR domain pack value (if no override)

**Important Notes:**
- Overrides are tenant-specific (each tenant can have different overrides)
- Overrides only apply to exceptions processed AFTER the new pack version is activated
- Existing exceptions in the database are NOT automatically updated
- To update existing exceptions, you may need to reprocess them

---

## Example: Complete Workflow

**Goal:** Change `POSITION_BREAK` exception severity from HIGH to LOW

1. **Current Pack Version:** `v1.0`
   ```json
   "customSeverityOverrides": [
     {
       "exceptionType": "POSITION_BREAK",
       "severity": "HIGH"
     }
   ]
   ```

2. **Modified Pack (new version `v1.1`):**
   ```json
   "customSeverityOverrides": [
     {
       "exceptionType": "POSITION_BREAK",
       "severity": "LOW"
     }
   ]
   ```

3. **Import as `v1.1`** → Status: DRAFT

4. **Activate `v1.1`** → Status: ACTIVE

5. **Result:** All new `POSITION_BREAK` exceptions will be triaged as LOW severity

---

## Troubleshooting

### "Pack validation failed"
- Check JSON syntax
- Ensure `tenantId` and `domainName` match existing tenant/domain
- Ensure `customSeverityOverrides` array has valid structure
- Ensure severity values are: LOW, MEDIUM, HIGH, or CRITICAL

### "Version already exists"
- Use a different version number (increment: v1.0 → v1.1 → v1.2)
- Or use the `overwrite=true` parameter (if supported)

### "Override not taking effect"
- Ensure the new pack version is **ACTIVE**
- Check that exception types match exactly (case-sensitive)
- Verify the exception was processed AFTER activation
- Existing exceptions in database are not automatically updated

### "Can't find Tenant Pack"
- Ensure you're on the "Tenant Packs" tab (not "Domain Packs")
- Check that tenant ID is correct
- Verify you have admin permissions

---

## Current UI Limitations

**Note:** The current UI at `/admin/packs` supports:
- ✅ Viewing pack content
- ✅ Importing new pack versions
- ✅ Activating pack versions
- ❌ **Direct editing of pack JSON in UI** (not implemented)
- ❌ **In-place updates** (versioning is required)

**Workaround:**
1. View current pack → Copy JSON
2. Edit JSON in external editor
3. Import modified JSON as new version
4. Activate new version

---

## Best Practices

1. **Version Naming:** Use semantic versioning (v1.0, v1.1, v2.0)
2. **Test First:** Import as DRAFT, validate, then activate
3. **Document Changes:** Keep track of what overrides changed and why
4. **Backup:** Keep a copy of working pack versions
5. **Validate:** Always validate before importing
6. **Review:** Review changes carefully before activating (changes are immediate)

---

## Related Documentation

- Pack Management Guide: `docs/pack-management-guide.md`
- Tenant Policy Pack Schema: `docs/03-data-models-apis.md`
- Domain Pack Schema: `docs/05-domain-pack-schema.md`

