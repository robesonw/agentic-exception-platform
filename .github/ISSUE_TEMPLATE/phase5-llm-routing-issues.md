# Phase 5 LLM Routing & Provider Strategy - GitHub Issues Checklist

## Component: LLM Routing Engine

### Issue LR-1: Implement Domain-Aware LLM Routing Logic
**Labels:** `component:llm-routing`, `phase:5`, `priority:high`
**Description:**
- Implement routing logic that selects LLM provider/model based on domain
- Support domain-specific model configurations (e.g., Finance domain uses different model than Healthcare)
- Integrate with existing Domain Pack system to read domain-specific LLM preferences
- Fallback to tenant-level configuration if domain-level not specified
- Fallback to global default if tenant-level not specified
- Reference: docs/phase5-llm-routing.md Section 2 (Design Principles - Domain- & tenant-aware), Section 4

**Dependencies:** Phase 2: Issue 22 (Domain Pack Loader)

**Acceptance Criteria:**
- [ ] Domain-aware routing logic implemented
- [ ] Domain Pack can specify preferred LLM provider/model per domain
- [ ] Tenant-level LLM configuration supported
- [ ] Global default fallback chain: domain → tenant → global → dummy
- [ ] Routing decisions logged (without exposing secrets)
- [ ] Unit tests for routing logic with various configurations

---

### Issue LR-2: Implement Tenant-Aware LLM Routing Logic
**Labels:** `component:llm-routing`, `phase:5`, `priority:high`
**Description:**
- Implement routing logic that selects LLM provider/model based on tenant
- Support tenant-specific model configurations (e.g., premium tenants use higher-capacity models)
- Integrate with Tenant Policy Pack system to read tenant-specific LLM preferences
- Support tenant-level overrides for domain defaults
- Reference: docs/phase5-llm-routing.md Section 2 (Design Principles - Domain- & tenant-aware), Section 4

**Dependencies:** Phase 2: Issue 22 (Domain Pack Loader), LR-1

**Acceptance Criteria:**
- [ ] Tenant-aware routing logic implemented
- [ ] Tenant Policy Pack can specify preferred LLM provider/model per tenant
- [ ] Tenant-level overrides domain-level configuration
- [ ] Tenant isolation enforced in routing decisions
- [ ] Routing decisions logged (without exposing secrets)
- [ ] Unit tests for tenant routing scenarios

---

### Issue LR-3: Implement Configuration File Support for LLM Routing
**Labels:** `component:llm-routing`, `phase:5`, `priority:medium`
**Description:**
- Implement support for YAML/JSON configuration files for LLM routing
- Support configuration files at multiple levels: global, tenant, domain
- Configuration file format should support:
  - Provider selection (dummy, openrouter, openai, etc.)
  - Model selection per provider
  - API key references (not raw keys)
  - Fallback chains
- Load and merge configurations with proper precedence (domain > tenant > global)
- Reference: docs/phase5-llm-routing.md Section 2 (Config-driven routing - Optional configuration files)

**Dependencies:** LR-1, LR-2

**Acceptance Criteria:**
- [ ] YAML configuration file support implemented
- [ ] JSON configuration file support implemented
- [ ] Multi-level configuration loading (global, tenant, domain)
- [ ] Configuration merging with proper precedence
- [ ] Configuration validation and error handling
- [ ] Hot-reload support for configuration files (optional)
- [ ] Unit tests for configuration file loading and merging

---

## Component: OpenRouter Provider Implementation

### Issue LR-4: Implement OpenRouter LLM Provider Client
**Labels:** `component:llm-provider`, `phase:5`, `priority:high`
**Description:**
- Implement `OpenRouterLLMClient` class that implements `LLMClient` Protocol from `src/llm/base.py`
- Integrate with OpenRouter API for LLM calls
- Support OpenRouter-specific features:
  - Multiple model selection via OpenRouter
  - API key authentication
  - Request/response handling
  - Error handling and retries
- Ensure provider-agnostic interface (no OpenRouter-specific code in business logic)
- Reference: docs/phase5-llm-routing.md Section 3 (Providers & LLMClient Implementations - OpenRouter)

**Dependencies:** Phase 5: Issue P5-1 (LLMClient Interface)

**Acceptance Criteria:**
- [ ] `OpenRouterLLMClient` class implemented
- [ ] Implements `LLMClient` Protocol correctly
- [ ] OpenRouter API integration functional
- [ ] Multiple model selection supported
- [ ] API key authentication implemented
- [ ] Error handling and retries functional
- [ ] Unit tests for OpenRouter provider
- [ ] Integration tests with OpenRouter API (mock or real)

---

### Issue LR-5: Integrate OpenRouter Provider into Factory
**Labels:** `component:llm-provider`, `phase:5`, `priority:high`
**Description:**
- Extend `load_llm_provider()` in `src/llm/factory.py` to support OpenRouter provider
- Add "openrouter" to `SUPPORTED_PROVIDERS` set
- Support OpenRouter-specific configuration:
  - `LLM_PROVIDER=openrouter`
  - `LLM_MODEL` (OpenRouter model identifier)
  - `LLM_API_KEY` (OpenRouter API key)
- Ensure factory returns `OpenRouterLLMClient` when provider is "openrouter"
- Reference: docs/phase5-llm-routing.md Section 3 (Providers - OpenRouter)

**Dependencies:** LR-4

**Acceptance Criteria:**
- [ ] OpenRouter provider added to factory
- [ ] Factory returns `OpenRouterLLMClient` for provider="openrouter"
- [ ] Environment variable configuration supported
- [ ] Error handling for invalid OpenRouter configuration
- [ ] Unit tests for factory with OpenRouter provider

---

## Component: Enhanced Provider Factory

### Issue LR-6: Enhance Provider Factory with Domain/Tenant Routing
**Labels:** `component:llm-factory`, `phase:5`, `priority:high`
**Description:**
- Enhance `load_llm_provider()` to accept `domain: str` and `tenant_id: str` parameters
- Implement routing logic that selects provider/model based on domain and tenant
- Integrate with Domain Pack and Tenant Policy Pack for configuration
- Support fallback chain: domain config → tenant config → global env vars → dummy
- Ensure backward compatibility (existing code without domain/tenant still works)
- Reference: docs/phase5-llm-routing.md Section 2 (Config-driven routing), Section 4

**Dependencies:** LR-1, LR-2, LR-3

**Acceptance Criteria:**
- [ ] Factory accepts `domain` and `tenant_id` parameters
- [ ] Routing logic integrated into factory
- [ ] Domain/Tenant configuration lookup functional
- [ ] Fallback chain implemented correctly
- [ ] Backward compatibility maintained
- [ ] Unit tests for enhanced factory with routing

---

### Issue LR-7: Implement Provider Configuration Registry
**Labels:** `component:llm-factory`, `phase:5`, `priority:medium`
**Description:**
- Implement configuration registry that caches provider configurations per domain/tenant
- Support hot-reloading of configurations when Domain Packs or Tenant Policy Packs change
- Cache provider client instances to avoid recreation
- Implement configuration validation before caching
- Support configuration versioning and rollback
- Reference: docs/phase5-llm-routing.md Section 2 (Config-driven routing)

**Dependencies:** LR-3, LR-6

**Acceptance Criteria:**
- [ ] Configuration registry implemented
- [ ] Caching of provider configurations functional
- [ ] Hot-reloading support implemented
- [ ] Configuration validation before caching
- [ ] Versioning and rollback supported
- [ ] Unit tests for configuration registry

---

## Component: Security & Compliance

### Issue LR-8: Implement Secret Masking in Logs
**Labels:** `component:llm-security`, `phase:5`, `priority:high`
**Description:**
- Implement secret masking for LLM API keys in all log outputs
- Ensure no raw secrets appear in:
  - Application logs
  - Error messages
  - Debug output
  - Audit trails
- Mask API keys with pattern: `sk-***` or `***masked***`
- Ensure secret masking works across all LLM provider implementations
- Reference: docs/phase5-llm-routing.md Section 2 (Security first - No raw secrets in logs)

**Dependencies:** LR-4, LR-5

**Acceptance Criteria:**
- [ ] Secret masking implemented for all LLM providers
- [ ] API keys masked in logs
- [ ] Error messages sanitized
- [ ] Debug output sanitized
- [ ] Audit trails sanitized
- [ ] Unit tests verify no secrets in logs

---

### Issue LR-9: Implement Prompt Constraint System for PHI/PII Heavy Domains
**Labels:** `component:llm-security`, `phase:5`, `priority:medium`
**Description:**
- Implement prompt constraint system that can restrict or sanitize prompts for PHI/PII heavy domains
- Support domain-level configuration for prompt constraints
- Implement prompt sanitization (e.g., redact sensitive data before sending to LLM)
- Support prompt validation before sending to external providers
- Allow disabling external providers for regulated environments
- Reference: docs/phase5-llm-routing.md Section 2 (Security first - Ability to constrain outbound prompts)

**Dependencies:** LR-1, LR-2

**Acceptance Criteria:**
- [ ] Prompt constraint system implemented
- [ ] Domain-level prompt constraints configurable
- [ ] Prompt sanitization functional
- [ ] Prompt validation before external calls
- [ ] Provider disabling for regulated environments supported
- [ ] Unit tests for prompt constraints

---

## Component: Fallback & Error Handling

### Issue LR-10: Enhance Fallback Logic with Provider-Specific Fallbacks
**Labels:** `component:llm-fallback`, `phase:5`, `priority:medium`
**Description:**
- Enhance fallback logic to support provider-specific fallback chains
- Support fallback configuration: e.g., if OpenRouter fails, try OpenAI, then DummyLLM
- Integrate with existing `src/llm/fallbacks.py` circuit breaker and retry logic
- Support domain/tenant-specific fallback chains
- Ensure fallback decisions are logged and audited
- Reference: docs/phase5-llm-routing.md Section 2 (Safe defaults - falls back to DummyLLMClient)

**Dependencies:** LR-6, Phase 3: Issue P3-6 (LLM Fallback Strategies)

**Acceptance Criteria:**
- [ ] Provider-specific fallback chains implemented
- [ ] Fallback configuration per domain/tenant supported
- [ ] Integration with circuit breaker functional
- [ ] Fallback decisions logged and audited
- [ ] Unit tests for fallback chains

---

## Component: Observability & Monitoring

### Issue LR-11: Implement LLM Routing Metrics and Observability
**Labels:** `component:llm-observability`, `phase:5`, `priority:medium`
**Description:**
- Implement metrics collection for LLM routing decisions:
  - Provider selection per domain/tenant
  - Model selection per domain/tenant
  - Fallback events
  - Routing decision latency
- Expose metrics in Prometheus format
- Add structured logging for routing decisions (without secrets)
- Support tenant-scoped metrics isolation
- Reference: docs/phase5-llm-routing.md Section 2 (Design Principles)

**Dependencies:** LR-6, Phase 1: Issue 16 (Basic Observability)

**Acceptance Criteria:**
- [ ] Routing metrics collection implemented
- [ ] Metrics exposed in Prometheus format
- [ ] Structured logging for routing decisions
- [ ] Tenant-scoped metrics isolation
- [ ] Unit tests for metrics collection

---

## Component: Testing

### Issue LR-12: Implement Comprehensive Tests for LLM Routing
**Labels:** `component:testing`, `phase:5`, `priority:high`
**Description:**
- Write comprehensive test suite for LLM routing functionality:
  - Test domain-aware routing
  - Test tenant-aware routing
  - Test configuration file loading and merging
  - Test fallback chains
  - Test provider selection logic
  - Test secret masking
  - Test prompt constraints
- Ensure test coverage >80% for routing module
- Include integration tests with mock providers
- Reference: docs/phase5-llm-routing.md

**Dependencies:** LR-1 through LR-11

**Acceptance Criteria:**
- [ ] Comprehensive test suite implemented
- [ ] Test coverage >80% for routing module
- [ ] Integration tests with mock providers
- [ ] All tests passing
- [ ] Test results documented

---

## Component: Documentation

### Issue LR-13: Document LLM Routing Configuration and Usage
**Labels:** `component:documentation`, `phase:5`, `priority:medium`
**Description:**
- Create comprehensive documentation for LLM routing:
  - Configuration guide (environment variables, config files)
  - Domain/Tenant configuration examples
  - Provider setup guides (OpenRouter, OpenAI, Dummy)
  - Fallback configuration examples
  - Security best practices
  - Troubleshooting guide
- Update existing documentation to reference routing system
- Reference: docs/phase5-llm-routing.md

**Dependencies:** LR-1 through LR-12

**Acceptance Criteria:**
- [ ] Configuration guide created
- [ ] Provider setup guides created
- [ ] Examples and best practices documented
- [ ] Troubleshooting guide created
- [ ] Existing documentation updated

---

## Summary

**Total Issues:** 13
**High Priority:** 8
**Medium Priority:** 5
**Low Priority:** 0

**Components Covered:**
- LLM Routing Engine (3 issues)
- OpenRouter Provider Implementation (2 issues)
- Enhanced Provider Factory (2 issues)
- Security & Compliance (2 issues)
- Fallback & Error Handling (1 issue)
- Observability & Monitoring (1 issue)
- Testing (1 issue)
- Documentation (1 issue)

**Phase 5 LLM Routing Milestones (from docs/phase5-llm-routing.md):**
- Provider-agnostic core implemented
- Config-driven routing functional
- Safe defaults (fallback to DummyLLMClient)
- Domain- & tenant-aware routing
- Security first (no secrets in logs, prompt constraints)
- OpenRouter provider integrated
- Configuration file support (YAML/JSON)

**Key Phase 5 LLM Routing Focus Areas:**
1. **Provider-Agnostic Core**: Co-Pilot and agents use only `LLMClient` interface, no direct provider dependencies
2. **Config-Driven Routing**: Routing decisions driven by environment variables and optional config files (YAML/JSON)
3. **Safe Defaults**: Platform falls back to DummyLLMClient if misconfigured
4. **Domain- & Tenant-Aware**: Different domains/tenants can use different models/providers
5. **Security First**: No raw secrets in logs, ability to constrain prompts for PHI/PII heavy domains
6. **OpenRouter Integration**: Full OpenRouter provider support with API integration
7. **Configuration Management**: Multi-level configuration (global, tenant, domain) with proper precedence

**Spec References:**
- docs/phase5-llm-routing.md - Phase 5 LLM Routing & Provider Strategy specification
- docs/phase5-copilot-mvp.md - Phase 5 AI Co-Pilot MVP specification (uses LLM routing)
- docs/01-architecture.md - Overall architecture document
- docs/03-data-models-apis.md - Backend API schemas and data models

