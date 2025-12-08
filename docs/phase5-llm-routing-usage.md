# Phase 5 – LLM Routing Configuration & Usage Guide

**For engineers configuring and operating the LLM routing system.**

---

## 1. Overview

The LLM routing layer is a **provider-agnostic abstraction** that selects and manages Large Language Model (LLM) providers based on domain and tenant configuration. It ensures that:

- **Business logic never depends on specific providers** (OpenAI, OpenRouter, etc.)
- **Different domains/tenants can use different models** (e.g., Healthcare uses dummy-only for compliance, Finance uses OpenRouter)
- **Safe defaults** prevent system crashes when misconfigured (falls back to DummyLLMClient)
- **Security first**: No secrets in logs, prompt constraints for PHI/PII domains

The Co-Pilot and all agents use only the `LLMClient` interface—they never call providers directly.

---

## 2. Environment Variables

### Core Variables

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `LLM_PROVIDER` | Default provider name | `openrouter`, `openai`, `dummy` | No (defaults to `dummy`) |
| `LLM_MODEL` | Default model identifier | `gpt-4.1-mini`, `openrouter:mistralai/mixtral-8x7b-instruct` | No |
| `LLM_API_KEY` | Generic API key (used if provider-specific key not set) | `sk-...` | No (required for external providers) |
| `LLM_ROUTING_CONFIG_PATH` | Path to YAML/JSON routing config file | `/path/to/llm-routing.yaml` | No (env-only routing if not set) |

### Provider-Specific Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API key (overrides `LLM_API_KEY` for OpenRouter) | `sk-or-v1-...` | No |

### Example Setup

```bash
# Basic setup with OpenRouter
export LLM_PROVIDER=openrouter
export LLM_MODEL=gpt-4.1-mini
export OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Or use routing config file
export LLM_ROUTING_CONFIG_PATH=/etc/platform/llm-routing.yaml
```

---

## 3. Routing Config File (YAML/JSON)

The routing config file allows **domain- and tenant-specific** provider/model selection with fallback chains.

### File Format

**YAML** (recommended):
```yaml
# Global defaults (used when no domain/tenant-specific config exists)
default_provider: openrouter
default_model: openrouter:gpt-4.1-mini
default_fallback_chain:
  - openrouter
  - openai
  - dummy

# Domain-specific routing
domains:
  Finance:
    provider: openrouter
    model: openrouter:mistralai/mixtral-8x7b-instruct
    fallback_chain:
      - openrouter
      - openai
      - dummy
  
  Healthcare:
    provider: dummy
    model: dummy-healthcare
    fallback_chain:
      - dummy  # No external providers for PHI/PII compliance
  
  Insurance:
    provider: openrouter
    model: openrouter:gpt-4.1-mini
    # No fallback_chain specified, inherits default_fallback_chain

# Tenant-specific routing (highest precedence)
tenants:
  TENANT_FINANCE_001:
    provider: openrouter
    model: openrouter:nousresearch/nous-hermes-2-mixtral-8x7b-dpo
    fallback_chain:
      - openrouter
      - dummy  # Premium tenant: simpler fallback
  
  TENANT_HEALTHCARE_001:
    provider: dummy
    model: dummy-healthcare-tenant
    fallback_chain:
      - dummy  # Tenant override: no external providers
```

**JSON** (also supported):
```json
{
  "default_provider": "openrouter",
  "default_model": "openrouter:gpt-4.1-mini",
  "default_fallback_chain": ["openrouter", "openai", "dummy"],
  "domains": {
    "Finance": {
      "provider": "openrouter",
      "model": "openrouter:mistralai/mixtral-8x7b-instruct",
      "fallback_chain": ["openrouter", "openai", "dummy"]
    },
    "Healthcare": {
      "provider": "dummy",
      "model": "dummy-healthcare",
      "fallback_chain": ["dummy"]
    }
  },
  "tenants": {
    "TENANT_FINANCE_001": {
      "provider": "openrouter",
      "model": "openrouter:nousresearch/nous-hermes-2-mixtral-8x7b-dpo",
      "fallback_chain": ["openrouter", "dummy"]
    }
  }
}
```

### Precedence Rules

**Provider/Model Selection:**
1. **Tenant-level** config (highest precedence)
2. **Domain-level** config
3. **Global default** (`default_provider`/`default_model`)
4. **Environment variables** (`LLM_PROVIDER`/`LLM_MODEL`)
5. **DummyLLMClient** (safety fallback)

**Fallback Chain Selection:**
1. **Tenant-level** `fallback_chain`
2. **Domain-level** `fallback_chain`
3. **Global default** `default_fallback_chain`
4. **`["dummy"]`** (safety fallback)

### Example: Request Flow

```python
# Request: domain="Finance", tenant_id="TENANT_FINANCE_001"

# 1. Check tenant config → Found: provider="openrouter", model="nous-hermes-2-mixtral-8x7b-dpo"
# 2. Use tenant config (tenant wins over domain)
# 3. Fallback chain: ["openrouter", "dummy"] (from tenant config)
```

```python
# Request: domain="Finance", tenant_id="TENANT_OTHER"

# 1. Check tenant config → Not found
# 2. Check domain config → Found: provider="openrouter", model="mistralai/mixtral-8x7b-instruct"
# 3. Use domain config
# 4. Fallback chain: ["openrouter", "openai", "dummy"] (from domain config)
```

---

## 4. Provider Setup Guides

### DummyLLM (Development/Testing)

**No configuration required.** DummyLLM is the default fallback and is used when:
- No provider is configured
- API keys are missing
- Provider name is invalid
- Routing config is not found

**Use cases:**
- Local development
- Testing without external API calls
- Regulated environments (Healthcare with PHI/PII restrictions)

**Behavior:**
- Returns mock responses based on prompt keywords
- No external API calls
- Always available

### OpenRouter

**Setup:**

1. **Get API Key:**
   - Sign up at [OpenRouter.ai](https://openrouter.ai)
   - Generate API key from dashboard
   - Copy key (format: `sk-or-v1-...`)

2. **Set Environment Variable:**
   ```bash
   export OPENROUTER_API_KEY=sk-or-v1-your-key-here
   # OR
   export LLM_API_KEY=sk-or-v1-your-key-here
   ```

3. **Configure Provider:**
   ```bash
   export LLM_PROVIDER=openrouter
   export LLM_MODEL=openrouter:gpt-4.1-mini
   ```

   Or in routing config:
   ```yaml
   domains:
     Finance:
       provider: openrouter
       model: openrouter:gpt-4.1-mini
   ```

**Model Identifiers:**

OpenRouter supports multiple models. Use the format: `openrouter:model-name`

Examples:
- `openrouter:gpt-4.1-mini` (OpenAI GPT-4.1 Mini)
- `openrouter:mistralai/mixtral-8x7b-instruct` (Mistral Mixtral)
- `openrouter:google/gemma-7b-it` (Google Gemma)
- `openrouter:nousresearch/nous-hermes-2-mixtral-8x7b-dpo` (Nous Hermes)

**Rate Limits & Error Behavior:**

- OpenRouter has rate limits based on your plan
- On rate limit errors, the system will:
  1. Log the error (without exposing API key)
  2. Fall back to next provider in fallback chain
  3. If all providers fail, return DummyLLMClient response

**Error Handling:**

The system automatically handles:
- HTTP errors (4xx, 5xx)
- Network timeouts
- Rate limit errors
- Invalid API keys

All errors trigger fallback to the next provider in the chain.

---

## 5. Fallback & Error Handling

### How Fallback Chains Work

When a provider fails (network error, rate limit, invalid response), the system automatically tries the next provider in the fallback chain.

**Example Chain:**
```yaml
fallback_chain:
  - openrouter
  - openai
  - dummy
```

**Flow:**
1. Try `openrouter` → If fails, continue to step 2
2. Try `openai` → If fails, continue to step 3
3. Try `dummy` → Always succeeds (safety fallback)

**Fallback Reasons:**
- Provider API error (HTTP 4xx/5xx)
- Network timeout
- Rate limit exceeded
- Invalid API key
- Provider returned error response

### Disabling External Providers

For regulated tenants (e.g., Healthcare with PHI/PII restrictions), you can disable external providers entirely:

```yaml
tenants:
  TENANT_HEALTHCARE_001:
    provider: dummy
    model: dummy-healthcare
    fallback_chain:
      - dummy  # Only dummy provider, no external calls
```

This ensures:
- No external API calls are made
- No PHI/PII data leaves the system
- All requests use DummyLLMClient

### Example: Finance Domain with Fallback

```yaml
domains:
  Finance:
    provider: openrouter
    model: openrouter:gpt-4.1-mini
    fallback_chain:
      - openrouter
      - openai
      - dummy
```

**Request Flow:**
1. Try OpenRouter with `gpt-4.1-mini`
2. If OpenRouter fails → Try OpenAI (if configured)
3. If OpenAI fails → Use DummyLLMClient (always succeeds)

---

## 6. Security & Privacy

### Secret Masking in Logs

**All API keys are automatically masked in logs.**

The system uses `mask_secret()` to ensure secrets never appear in:
- Application logs
- Error messages
- Debug output
- Audit trails

**Examples:**
- `sk-or-v1-1234567890` → `sk-***`
- `my-secret-token` → `***masked***`

**Verification:**
```python
from src.llm.utils import mask_secret

mask_secret("sk-or-v1-1234567890")  # Returns: "sk-***"
```

### Prompt Constraints for PHI/PII Domains

For Healthcare and other PHI/PII-heavy domains, prompts are automatically sanitized before sending to external providers.

**Healthcare Domain:**
- Patient IDs (MRN, patient_id) → `[REDACTED]`
- Email addresses → `[EMAIL_REDACTED]`
- Phone numbers → `[PHONE_REDACTED]`
- SSN → `SSN=[REDACTED]`

**Example:**
```python
# Original prompt
prompt = "Explain exception for patient_id: MRN-12345"

# After sanitization (Healthcare domain)
sanitized = "Explain exception for patient_id=[REDACTED]"
```

**Other Domains:**
- Finance, Insurance, etc. → Prompts pass through unchanged

### Disabling External Providers

For maximum security, you can disable external providers entirely:

```yaml
domains:
  Healthcare:
    provider: dummy
    fallback_chain:
      - dummy  # No external providers
```

This ensures:
- No external API calls
- No data leaves the system
- All requests use DummyLLMClient

---

## 7. Observability & Metrics

### Prometheus Metrics

The system exposes Prometheus metrics for monitoring and alerting.

**Metrics:**

1. **`llm_provider_selection_total`** (Counter)
   - Tracks provider/model selections per tenant/domain
   - Labels: `tenant_id`, `domain`, `provider`, `model`
   - Example: `llm_provider_selection_total{tenant_id="TENANT_001", domain="Finance", provider="openrouter", model="gpt-4.1-mini"}`

2. **`llm_fallback_events_total`** (Counter)
   - Tracks fallback events (provider A failed, provider B attempted)
   - Labels: `tenant_id`, `domain`, `from_provider`, `to_provider`
   - Example: `llm_fallback_events_total{tenant_id="TENANT_001", domain="Finance", from_provider="openrouter", to_provider="openai"}`

3. **`llm_routing_decision_seconds`** (Histogram)
   - Tracks routing decision latency
   - Labels: `tenant_id`, `domain`
   - Example: `llm_routing_decision_seconds{tenant_id="TENANT_001", domain="Finance"}`

### Example Queries

**Provider selection by tenant:**
```promql
sum(rate(llm_provider_selection_total{tenant_id="TENANT_001"}[5m])) by (provider)
```

**Fallback rate by domain:**
```promql
sum(rate(llm_fallback_events_total[5m])) by (domain, from_provider, to_provider)
```

**Routing latency (p95):**
```promql
histogram_quantile(0.95, sum(rate(llm_routing_decision_seconds_bucket[5m])) by (le, tenant_id, domain))
```

**Provider selection distribution:**
```promql
sum(llm_provider_selection_total) by (provider, domain)
```

### Exposing Metrics

To expose Prometheus metrics endpoint:

```python
# In src/api/main.py
try:
    from prometheus_client import make_asgi_app
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
except ImportError:
    logger.warning("prometheus_client not available, /metrics endpoint not mounted")
```

Then access metrics at: `http://localhost:8000/metrics`

---

## 8. Troubleshooting

### Common Issues

#### 1. Misconfigured Provider Name

**Symptom:** System falls back to DummyLLMClient even though API key is set.

**Cause:** Provider name doesn't match supported providers.

**Solution:**
- Check `LLM_PROVIDER` value (must be: `dummy`, `openrouter`, `openai`)
- Check routing config file for typos in provider names
- Provider names are case-insensitive but must match exactly

**Debug:**
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Check logs for:
# "Unsupported provider: <name>. Supported providers: ..."
```

#### 2. Missing API Key

**Symptom:** System falls back to DummyLLMClient, logs show "API key not provided".

**Cause:** `LLM_API_KEY` or provider-specific key (e.g., `OPENROUTER_API_KEY`) not set.

**Solution:**
```bash
# Set API key
export OPENROUTER_API_KEY=sk-or-v1-your-key-here
# OR
export LLM_API_KEY=sk-or-v1-your-key-here
```

**Debug:**
```bash
# Check if key is set (without exposing it)
python -c "import os; print('Key set:', bool(os.getenv('OPENROUTER_API_KEY')))"
```

#### 3. Routing Config Not Found

**Symptom:** System uses environment variables only, ignores domain/tenant config.

**Cause:** `LLM_ROUTING_CONFIG_PATH` not set or file doesn't exist.

**Solution:**
```bash
# Set config path
export LLM_ROUTING_CONFIG_PATH=/path/to/llm-routing.yaml

# Verify file exists
ls -la /path/to/llm-routing.yaml
```

**Debug:**
```bash
# Check logs for:
# "LLM routing config file not found: <path>"
```

#### 4. Provider API Errors

**Symptom:** Frequent fallbacks, errors in logs.

**Cause:** API key invalid, rate limits, network issues.

**Solution:**
- Verify API key is valid
- Check rate limits on provider dashboard
- Verify network connectivity
- Check provider status page

**Debug:**
```bash
# Enable debug logging to see detailed error messages
export LOG_LEVEL=DEBUG

# Check logs for:
# "OpenRouter API HTTP error: <status_code>"
# "LLM call failed with provider=..."
```

### Enabling Debug Logs

**Environment Variable:**
```bash
export LOG_LEVEL=DEBUG
```

**Python Code:**
```python
import logging
logging.getLogger("src.llm").setLevel(logging.DEBUG)
```

**What You'll See:**
- Provider selection decisions
- Routing config loading
- Fallback events
- API call attempts (without secrets)

### Testing Routing Configuration

**Manual Test:**
```python
from src.llm.factory import load_llm_provider

# Test domain-only routing
client = load_llm_provider(domain="Finance")
print(f"Provider: {type(client).__name__}")

# Test tenant routing
client = load_llm_provider(domain="Finance", tenant_id="TENANT_FINANCE_001")
print(f"Provider: {type(client).__name__}")
```

**Test with Routing Config:**
```python
from src.llm.routing_config import load_routing_config

# Load config
config = load_routing_config("/path/to/llm-routing.yaml")

# Test fallback chain resolution
chain = config.get_fallback_chain(domain="Finance", tenant_id="TENANT_001")
print(f"Fallback chain: {chain}")
```

### Hot Reload Configuration

To reload routing config without restarting the application:

```python
from src.llm.factory import reload_llm_routing_config

# Reload config and invalidate cached clients
reload_llm_routing_config()
```

**Note:** This is currently a manual operation. Future phases may add:
- Admin API endpoint for hot reload
- File watcher for automatic reload
- Distributed cache invalidation

---

## 9. Quick Reference

### Environment Variables Summary

```bash
# Required for external providers
export OPENROUTER_API_KEY=sk-or-v1-...

# Optional: Override defaults
export LLM_PROVIDER=openrouter
export LLM_MODEL=gpt-4.1-mini

# Optional: Use routing config file
export LLM_ROUTING_CONFIG_PATH=/path/to/llm-routing.yaml
```

### Routing Config Template

```yaml
default_provider: openrouter
default_model: openrouter:gpt-4.1-mini
default_fallback_chain:
  - openrouter
  - openai
  - dummy

domains:
  YourDomain:
    provider: openrouter
    model: openrouter:gpt-4.1-mini
    fallback_chain:
      - openrouter
      - dummy

tenants:
  YOUR_TENANT_ID:
    provider: openrouter
    model: openrouter:gpt-4.1-mini
    fallback_chain:
      - openrouter
      - dummy
```

### Precedence Quick Reference

1. **Tenant config** (highest)
2. **Domain config**
3. **Global default**
4. **Environment variables**
5. **DummyLLMClient** (safety fallback)

---

## 10. Integration with Co-Pilot

The Co-Pilot uses the LLM routing layer automatically. No special configuration is needed.

**How It Works:**
1. Co-Pilot receives request with `domain` and `tenant_id`
2. Calls `load_llm_provider(domain=domain, tenant_id=tenant_id)`
3. Routing layer resolves provider/model based on config
4. Co-Pilot uses the returned `LLMClient` to generate responses

**Example:**
```python
# In CopilotOrchestrator
llm_client = load_llm_provider(
    domain=request.domain,
    tenant_id=request.tenant_id
)
response = await llm_client.generate(prompt, context=rich_context)
```

The Co-Pilot never calls providers directly—it always goes through the routing layer.

---

## 11. Best Practices

1. **Use routing config files** for production (not just env vars)
2. **Set fallback chains** for all domains/tenants
3. **Disable external providers** for regulated tenants (Healthcare, etc.)
4. **Monitor metrics** for provider selection and fallback rates
5. **Test routing config** before deploying to production
6. **Use secret masking** (automatic, but verify in logs)
7. **Enable prompt constraints** for PHI/PII domains

---

## 12. Future Enhancements

- **Domain Pack Integration:** LLM preferences in Domain Packs
- **Tenant Policy Pack Integration:** LLM preferences in Tenant Policy Packs
- **Distributed Cache:** Redis-based registry for multi-instance deployments
- **Admin API:** Hot reload endpoint, routing config management
- **Advanced Prompt Constraints:** NER-based PHI/PII detection
- **Provider Health Checks:** Automatic provider health monitoring
- **Cost Tracking:** Per-tenant/provider cost metrics

---

**See Also:**
- `docs/phase5-llm-routing.md` - Technical specification
- `docs/phase5-copilot-mvp.md` - Co-Pilot API and behavior
- `config/llm-routing.sample.yaml` - Example configuration file

