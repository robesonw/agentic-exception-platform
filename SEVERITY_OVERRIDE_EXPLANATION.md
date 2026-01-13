# Severity Override Precedence Explanation

## How Severity Overrides Should Work

According to the architecture design:

1. **Domain Pack** defines the **base/default severity** for each exception type via `severityRules`
2. **Tenant Policy Pack** `customSeverityOverrides` **overrides** the domain pack severity for specific exception types
3. **Final severity** = Tenant Policy Override (if exists) OR Domain Pack severity (if no override)

## Your Current Situation

### Domain Pack (CapitalMarketsTrading)
- Exception Type: `FIN_SETTLEMENT_FAIL`
- Severity Rule: `HIGH`
- Base severity: **HIGH**

### Tenant Policy Pack Override
- Exception Type: `FIN_SETTLEMENT_FAIL`
- Override Severity: `LOW`
- Intended final severity: **LOW** (should override HIGH)

## The Problem

**Severity overrides are NOT currently implemented in TriageAgent!**

Looking at `src/agents/triage.py`, the `_evaluate_severity()` method:
- Only uses domain pack severity rules
- Does NOT check tenant policy `customSeverityOverrides`
- Does NOT receive tenant policy as input

So currently, the system only uses domain pack severity, and tenant policy overrides are ignored.

## Why Your Exception Shows HIGH

The exception `d521df62-bd79-43a9-847a-43fcce35fd56` shows HIGH severity because:
1. TriageAgent evaluated severity using domain pack rules
2. Domain pack says `FIN_SETTLEMENT_FAIL` = HIGH
3. Tenant policy override is not checked/implemented
4. Result: HIGH (from domain pack only)

## Solution

To make severity overrides work, TriageAgent needs to be updated to:
1. Receive tenant policy pack as input
2. Check `customSeverityOverrides` after evaluating domain pack rules
3. Apply override if exception type matches

This is a **missing feature** that needs to be implemented.

## Your Tenant Pack is Correct

Your tenant pack JSON is correct:
- Exception type: `FIN_SETTLEMENT_FAIL` ✓ (matches domain pack)
- Override severity: `LOW` ✓
- Structure: Valid ✓

The override just isn't being applied by the code yet.

## Current Workaround

Until the feature is implemented:
- Exceptions will use domain pack severity only
- Tenant policy overrides are ignored
- You cannot change severity via tenant policy yet

## Next Steps

1. Verify that severity overrides are indeed missing (check TriageAgent code)
2. Implement the feature if missing
3. Test with new exceptions after implementation

