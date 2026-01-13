# Domain Pack Activation Deactivation Fix

## Problem

When activating a new domain pack version (e.g., v1.1), the previous active version (e.g., v1.0) remained active, resulting in multiple active versions for the same domain.

This is problematic because:
- Only one version should be active at a time for a given domain
- Multiple active versions can cause confusion about which version is actually being used
- The system should enforce a single active version per domain

## Root Cause

The activation endpoint (`POST /admin/packs/activate`) in `src/api/routes/onboarding.py` only set the status of the pack being activated to `ACTIVE`, but did not deactivate other active versions of the same domain.

## Solution

Updated the activation endpoint to:

1. **Before activating a new version:**
   - Find all existing `ACTIVE` domain packs with the same domain name
   - Set their status to `DEPRECATED` (except the pack being activated)
   - Log the deactivation for audit purposes

2. **Then activate the new version:**
   - Set the new pack's status to `ACTIVE` (if it was `DRAFT`)

This ensures only one version is active at a time for a given domain.

## Code Changes

**File**: `src/api/routes/onboarding.py`

**Method**: `activate_packs()` (around line 1558)

**Changes**:
- Added logic to query existing active packs using `domain_pack_repo.list_domain_packs(domain=domain_name, status=PackStatus.ACTIVE)`
- Iterate through existing active packs and deactivate them (set status to `PackStatus.DEPRECATED`)
- Skip the pack being activated (check `existing_pack.id != domain_pack_validated.id`)
- Added logging for each deactivated pack

## Expected Behavior After Fix

1. ✅ User activates domain pack v1.1
2. ✅ System finds existing active v1.0 (same domain)
3. ✅ System deactivates v1.0 (status → DEPRECATED)
4. ✅ System activates v1.1 (status → ACTIVE)
5. ✅ Only v1.1 is active for that domain

## Testing

To verify the fix:

1. **Activate v1.0** (should become active)
2. **Activate v1.1** (v1.0 should be deactivated, v1.1 should be active)
3. **Check UI**: Only v1.1 should show as "active" in the packs list
4. **Check database**: v1.0 status should be "deprecated", v1.1 status should be "active"

## Related Files

- `src/api/routes/onboarding.py` - Fixed activation endpoint
- `src/infrastructure/repositories/onboarding_domain_pack_repository.py` - Used for listing and updating pack status
- `src/infrastructure/db/models.py` - PackStatus enum (ACTIVE, DEPRECATED, DRAFT)

## Notes

- The fix applies to domain packs only (not tenant packs, as they may have different behavior)
- Status `DEPRECATED` is used for deactivated packs (preserves history)
- The deactivation happens in the same transaction as activation (atomic operation)

