# Colon Prefix Fix - Complete Implementation

## Problem
Exception types were being generated with colon prefixes (e.g., `: fin_settlement_fail`) instead of the correct format (`FIN_SETTLEMENT_FAIL`), causing:
- Tenant policy severity overrides to not match
- Inconsistent exception type formats
- Mixed results (some exceptions with colons, some without)

## Root Cause Analysis
After investigation, the issue was caused by:
1. **Catalog cache persistence**: The `DemoCatalogLoader` uses a class-level cache that could contain old values with colon prefixes even after the catalog file was edited
2. **Multiple code paths**: Exceptions are created both directly in DB and via Kafka events, requiring normalization at multiple points
3. **Insufficient defensive normalization**: While normalization existed, it needed to be applied at the earliest possible point (when selecting from catalog)

## Fixes Applied

### 1. Defensive Normalization in `_weighted_choice` Method
**File:** `src/demo/scenario_engine.py` (lines 604-622)
**Fix:** Added normalization immediately after selecting a value from the catalog
```python
def _weighted_choice(self, choices: list[WeightedChoice]) -> str:
    """Select a value based on weights."""
    if not choices:
        return ""
    
    values = [c.value for c in choices]
    weights = [c.weight for c in choices]
    
    selected = random.choices(values, weights=weights, k=1)[0]
    
    # Defensive normalization: strip any leading colons and normalize case
    # This ensures we never return a value with colon prefix, even if catalog has it
    if selected:
        while selected.startswith(':'):
            selected = selected[1:]
        selected = selected.strip()
        if selected and selected.islower():
            selected = selected.upper()
    
    return selected
```

### 2. Force Catalog Reload
**File:** `src/demo/scenario_engine.py` (line 632-636)
**Fix:** Clear cache and force reload to ensure fresh catalog is loaded
```python
def _get_catalog(self) -> DemoCatalog:
    """Get or load demo catalog."""
    if self._catalog is None:
        # Force reload to ensure we get fresh catalog (clears any stale cache)
        DemoCatalogLoader.clear_cache()
        self._catalog = DemoCatalogLoader.load(force_reload=True)
    return self._catalog
```

### 3. Enhanced Normalization in Scenario Engine
**File:** `src/demo/scenario_engine.py` (lines 455-470)
**Fix:** Enhanced normalization with logging (already existed, enhanced with logging)
```python
if exc_type:
    original_exc_type = exc_type  # For logging
    # Strip ALL leading colons (handles ":value", "::value", etc.)
    while exc_type.startswith(':'):
        exc_type = exc_type[1:]
    # Strip leading/trailing whitespace
    exc_type = exc_type.strip()
    # Convert to uppercase if it's all lowercase
    if exc_type and exc_type.islower():
        exc_type = exc_type.upper()
    # Log normalization for debugging
    if original_exc_type != exc_type:
        logger.info(
            f"Normalized exception type: {repr(original_exc_type)} -> {repr(exc_type)} "
            f"(scenario={scenario.scenario_id})"
        )
```

### 4. Defensive Normalization in Intake Agent
**File:** `src/agents/intake.py` (lines 130-137)
**Fix:** Normalization when extracting exception type from raw payload (already existed)
```python
if exception_type:
    # Strip ALL leading colons (handles ":value", "::value", etc.)
    while exception_type.startswith(':'):
        exception_type = exception_type[1:]
    # Strip leading/trailing whitespace
    exception_type = exception_type.strip()
    if exception_type and exception_type.islower():
        exception_type = exception_type.upper()
```

## Triple Protection Layer

Normalization now happens at THREE points to ensure colon prefixes are always stripped:

1. **Source Level** (`_weighted_choice`): Strips colons when selecting from catalog
2. **Scenario Engine Level**: Normalizes after selection (redundant but defensive)
3. **Intake Agent Level**: Final defensive normalization when processing events

## Verification

The fixes ensure that:
- ✅ Colon prefixes are stripped at the source (when selecting from catalog)
- ✅ Catalog cache is cleared and force-reloaded to avoid stale values
- ✅ Multiple normalization points provide defense-in-depth
- ✅ Case normalization ensures consistent uppercase format
- ✅ Debug logging tracks normalization for troubleshooting

## Testing

After applying these fixes:
1. Restart all services (to clear any in-memory caches)
2. Generate new exceptions from demo page
3. Verify all new exceptions have clean exception types (no colon prefix)
4. Verify severity overrides work correctly (FIN_SETTLEMENT_FAIL should be LOW)

## Files Modified

- `src/demo/scenario_engine.py`: Added normalization in `_weighted_choice`, enhanced `_get_catalog` with force_reload, added logging
- `src/agents/intake.py`: Already had normalization (verified correct)

## Status

✅ **COMPLETE** - All fixes applied and verified in code. Services need to be restarted for changes to take effect.

