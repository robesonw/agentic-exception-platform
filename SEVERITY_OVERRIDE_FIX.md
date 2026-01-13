# Severity Override Fix - Per-Event Tenant Policy Loading

## Problem

The initial implementation added severity override logic to TriageAgent, but workers were using stub tenant policies instead of loading real ones from the database. This meant severity overrides were never applied.

## Solution

Updated `TriageWorker.process_event()` to:
1. Load tenant policy from database per-event using `ActiveConfigLoader`
2. Create a new `TriageAgent` instance with the loaded tenant policy
3. Process the exception with the agent that has the real tenant policy

## Changes Made

### TriageWorker (`src/workers/triage_worker.py`)

Added tenant policy loading in `process_event()` method:

```python
# Load tenant policy from database for this tenant
tenant_policy = None
try:
    from src.infrastructure.db.session import get_db_session_context
    from src.infrastructure.repositories.active_config_loader import ActiveConfigLoader
    
    async with get_db_session_context() as session:
        config_loader = ActiveConfigLoader(session=session)
        tenant_policy = await config_loader.load_tenant_pack(tenant_id)
        if tenant_policy:
            logger.debug(
                f"Loaded tenant policy for tenant {tenant_id}: "
                f"has {len(tenant_policy.custom_severity_overrides)} severity overrides"
            )
except Exception as e:
    logger.warning(
        f"TriageWorker failed to load tenant policy for tenant {tenant_id}: {e}. "
        f"Using default/stub tenant policy."
    )
    # Continue with stub/None tenant policy - severity overrides won't apply

# Create TriageAgent instance with loaded tenant policy (or use instance tenant policy as fallback)
triage_agent = self.triage_agent
if tenant_policy:
    # Create new TriageAgent instance with loaded tenant policy
    triage_agent = TriageAgent(
        domain_pack=self.domain_pack,
        audit_logger=self.audit_logger,
        memory_index=self.memory_index,
        llm_client=self.llm_client,
        tenant_policy=tenant_policy,
    )

# Perform triage analysis using TriageAgent
decision = await triage_agent.process(exception)
```

## How It Works

1. **Event Processing**: When TriageWorker receives an `ExceptionNormalized` event
2. **Tenant Policy Loading**: Loads the active tenant policy pack from database for the event's `tenant_id`
3. **Agent Creation**: Creates a new TriageAgent instance with the loaded tenant policy
4. **Override Application**: TriageAgent's `_evaluate_severity()` checks `customSeverityOverrides` and applies them
5. **Fallback**: If loading fails, uses the instance TriageAgent (with stub/None tenant policy)

## Testing

To verify the fix works:

1. Ensure tenant policy pack is imported and activated in the database
2. Restart the triage worker
3. Generate a new exception with the override exception type (e.g., `FIN_SETTLEMENT_FAIL`)
4. Check logs for:
   - `"Loaded tenant policy for tenant {tenant_id}: has {N} severity overrides"`
   - `"Applied tenant policy severity override: {exception_type} -> {severity}"`
5. Verify exception severity in database/UI matches override (LOW), not domain pack (HIGH)

## Example

For exception type `FIN_SETTLEMENT_FAIL`:
- **Domain Pack**: HIGH severity
- **Tenant Policy Override**: LOW severity
- **Result**: LOW severity (override applied)

## Next Steps

The user should:
1. Restart the triage worker
2. Generate a NEW exception (existing exceptions won't change)
3. Check that the new exception has LOW severity instead of HIGH
4. Check worker logs to confirm tenant policy was loaded and override was applied

