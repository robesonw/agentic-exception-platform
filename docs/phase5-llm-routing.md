# Phase 5 – LLM Routing & Provider Strategy  
SentinAI – Domain-Abstracted, Multi-Tenant Exception Platform

---

## 1. Purpose

This document defines how the platform selects and uses Large Language Models (LLMs) across:

- **Multiple domains** (Finance, Healthcare, Insurance, IT Ops, etc.)
- **Multiple tenants** (different client organizations)
- **Multiple providers** (Dummy, OpenRouter, optionally OpenAI later)

It complements:

- `docs/master_project_instruction_full.md`
- `docs/01-architecture.md`
- `docs/03-data-models-apis.md`
- `docs/phase5-copilot-mvp.md` (Co-Pilot behavior & API)

This spec **does not change** the Co-Pilot API. It only defines how the internal `LLMClient` implementation is selected and configured.

**For configuration and usage instructions, see:** `docs/phase5-llm-routing-usage.md`

---

## 2. Design Principles

1. **Provider-agnostic core**
   - Co-Pilot and agents use only the `LLMClient` interface.
   - No direct dependency on OpenAI / OpenRouter / Gemini from business logic.

2. **Config-driven routing**
   - Routing decisions (which model/provider to use) are driven by:
     - Environment variables
     - Optional configuration files (YAML/JSON)
   - No hard-coded provider names or models in the orchestrator.

3. **Safe defaults**
   - If misconfigured, the platform **falls back to DummyLLMClient**.
   - The system must not crash just because LLM keys are missing in dev.

4. **Domain- & tenant-aware**
   - Different domains (Finance vs Healthcare) may use different models.
   - In future, premium tenants can use higher-capacity models vs standard tenants.

5. **Security first**
   - No raw secrets in logs.
   - Ability to constrain outbound prompts for PHI/PII heavy domains.
   - Easy to replace or disable external providers in regulated environments.

---

## 3. Providers & LLMClient Implementations

The platform uses a **single abstraction**:

```py
# src/llm/base.py
class LLMClient(Protocol):
    async def generate(self, prompt: str, context: dict | None = None) -> LLMResponse:
        ...



