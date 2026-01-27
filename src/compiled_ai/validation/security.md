# Security Architecture for CompiledAI Code Factory

## Overview

This document outlines the security architecture for protecting the CompiledAI code generation pipeline.

## Architectural Defense: Dual-LLM Privilege Separation

CompiledAI already implements a **fundamental security pattern** through its two-agent architecture:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRIVILEGE SEPARATION                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   USER INPUT (untrusted)                                        │
│        │                                                        │
│        ▼                                                        │
│   ┌─────────────────────┐                                       │
│   │   PLANNER AGENT     │  ← User-facing, gathers context       │
│   │   (Lower privilege) │  ← Outputs STRUCTURED WorkflowSpec    │
│   └─────────────────────┘                                       │
│        │                                                        │
│        │ Structured data only (no raw user text)                │
│        ▼                                                        │
│   ┌─────────────────────┐                                       │
│   │    CODER AGENT      │  ← Internal, never sees raw input     │
│   │  (Higher privilege) │  ← Generates executable code          │
│   └─────────────────────┘                                       │
│        │                                                        │
│        ▼                                                        │
│   GENERATED CODE (validated)                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Why this helps:**
| Defense Layer | How It Works |
|---------------|--------------|
| **Data sanitization** | Planner converts free-text to structured WorkflowSpec |
| **Privilege isolation** | Coder only sees schema-validated ActivitySpec objects |
| **Attack surface reduction** | Injection payloads in user text don't reach code generator |
| **Pydantic validation** | Structured schemas reject malformed/unexpected data |

**Research basis:** This aligns with Simon Willison's "dual LLM" pattern and Google's research on "LLM firewalling" - using privileged/unprivileged model separation to contain injection attacks.

---

## Additional Security Layers

Beyond architectural defense, we add tool-based validation:

| Phase | Threat | Solution |
|-------|--------|----------|
| **Input** | Prompt injection, jailbreaks | Prompt Guard (Meta) |
| **Processing** | PII leakage, GDPR/SOC2 compliance | LLM-Guard |
| **Output** | Unsafe generated code | Code Shield (Meta) + Bandit/Semgrep |

## Tool Analysis

### 1. Prompt Guard (Meta/Llama) - INPUT PROTECTION

**Purpose:** Detect and block prompt injection attacks before they reach the LLM.

**Why use it:**
- Faster and more modern than llm-guard's injection filters
- Specifically trained on injection attack patterns
- Low latency (~10ms per check)
- Open source, runs locally

**Integration Point:**
```
User Input → Prompt Guard → [BLOCKED if injection] → Planner Agent
```

**Recommended:** YES - Primary input defense

---

### 2. LLM-Guard - PII/COMPLIANCE

**Purpose:** Scrub PII from inputs before sending to external LLMs.

**Why use it:**
- GDPR/SOC2 compliance (don't send user data to OpenAI/Anthropic)
- Detects: emails, phone numbers, SSNs, credit cards, addresses
- Anonymization: replaces PII with tokens, can de-anonymize on return
- Also provides basic prompt injection detection (secondary layer)

**Integration Point:**
```
User Input → Prompt Guard → LLM-Guard (PII scrub) → LLM → LLM-Guard (restore) → Output
```

**Recommended:** YES - Critical for compliance

---

### 3. Code Shield (Meta/Llama) - CODE OUTPUT SAFETY

**Purpose:** Detect insecure code patterns in LLM-generated code.

**Why use it:**
- Trained specifically on code security vulnerabilities
- Detects: SQL injection, command injection, path traversal, XSS
- Faster than running full Bandit/Semgrep on every generation
- Complements static analysis tools

**Integration Point:**
```
Coder Agent Output → Code Shield → [REJECT if insecure] → Regenerate or Accept
```

**Recommended:** YES - First-pass code safety check

---

### 4. NeMo Guardrails (NVIDIA) - PROGRAMMABLE GUARDRAILS

**Purpose:** Define custom conversation flows and safety rails using Colang DSL.

**Capabilities:**
- Topic control (keep conversations on-track)
- Fact-checking with RAG
- Custom safety policies
- Multi-turn conversation management

**Is it overkill for CompiledAI?**

| Use Case | NeMo Needed? | Why |
|----------|--------------|-----|
| Single-turn code generation | NO | Prompt Guard + LLM-Guard sufficient |
| Multi-turn workflow refinement | MAYBE | Could help maintain context |
| User-facing chatbot | YES | Full conversation control |
| Batch code compilation | NO | No conversation to manage |

**Recommendation:** SKIP for now. NeMo Guardrails is designed for conversational AI with multi-turn dialogue. CompiledAI's code factory is primarily single-turn (spec → code). The complexity overhead (Colang DSL, custom policies) isn't justified.

**Revisit if:** You add interactive workflow refinement or user-facing chat interface.

---

## Recommended Security Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                     SECURITY VALIDATION PIPELINE                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  INPUT PHASE                                                    │
│  ┌─────────────┐    ┌─────────────┐                            │
│  │ Prompt Guard│───>│  LLM-Guard  │                            │
│  │  (Injection)│    │(PII Scrub)  │                            │
│  └─────────────┘    └─────────────┘                            │
│         │                  │                                    │
│         ▼                  ▼                                    │
│  ┌─────────────────────────────────────┐                       │
│  │         PLANNER AGENT               │                       │
│  │    (Workflow Design)                │                       │
│  └─────────────────────────────────────┘                       │
│                    │                                            │
│                    ▼                                            │
│  ┌─────────────────────────────────────┐                       │
│  │         CODER AGENT                 │                       │
│  │    (Code Generation)                │                       │
│  └─────────────────────────────────────┘                       │
│                    │                                            │
│  OUTPUT PHASE      ▼                                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │ Code Shield │───>│   Bandit    │───>│   Semgrep   │        │
│  │(Quick Check)│    │(Security)   │    │(Patterns)   │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │    mypy     │───>│    ruff     │───>│   radon     │        │
│  │ (Types)     │    │ (Lint)      │    │(Complexity) │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Integration with Code Factory

### 1. Input Validation (factory.py)

```python
# In CodeFactory.generate() - before calling Planner
from compiled_ai.validation import PromptInjectionValidator, PIIScanner

async def generate(self, task_description: str, ...) -> FactoryResult:
    # Step 1: Prompt injection check (Prompt Guard)
    injection_result = self.prompt_guard.validate(task_description)
    if not injection_result.success:
        return FactoryResult(
            success=False,
            error=f"Prompt injection detected: {injection_result.details}"
        )

    # Step 2: PII scrubbing (LLM-Guard)
    sanitized_input, pii_map = self.pii_scanner.sanitize(task_description)

    # Continue with sanitized input...
```

### 2. Output Validation (dynamic_loader.py)

```python
# In DynamicModuleLoader.load() - after generating code
from compiled_ai.validation import CodeSecurityValidator

def load(self, code: str, ...) -> dict[str, Callable]:
    # Step 1: Quick check with Code Shield
    shield_result = self.code_shield.validate(code)
    if not shield_result.success:
        raise SecurityError(f"Unsafe code: {shield_result.details}")

    # Step 2: Deep analysis with Bandit
    bandit_result = self.bandit_scanner.scan(code)
    if bandit_result.has_critical_issues:
        raise SecurityError(f"Security vulnerabilities: {bandit_result.issues}")

    # Continue with code execution...
```

### 3. Registration Gate (registration.py)

```python
# In ActivityRegistrar.attempt_registration() - before registering
def attempt_registration(self, code: str, ...) -> bool:
    # Must pass full security validation before registration
    security_result = self.security_validator.full_scan(code)
    if not security_result.success:
        logger.warning(f"Registration blocked: {security_result.details}")
        return False

    # Continue with registration...
```

---

## File Structure

```
src/compiled_ai/validation/
├── __init__.py
├── base.py                    # Validator interface + registry
├── prompt_injection.py        # Prompt Guard wrapper
├── pii_scanner.py             # LLM-Guard wrapper (future)
├── code_security.py           # Code Shield + Bandit wrapper (future)
├── code_quality.py            # mypy, ruff, radon (future)
└── security.md                # This document
```

---

## Implementation Priority

| Priority | Component | Tools | Effort |
|----------|-----------|-------|--------|
| **P0** | Prompt Injection | Prompt Guard (or regex patterns) | 1-2 days |
| **P1** | Code Security | Code Shield + Bandit | 2-3 days |
| **P2** | PII Scanner | LLM-Guard | 1-2 days |
| **P3** | Code Quality | mypy, ruff, radon | 1-2 days |
| **P4** | NeMo Guardrails | Skip for now | - |

---

## Dependencies

```toml
# pyproject.toml additions
[project.dependencies]
llm-guard = "^0.3.0"           # PII scanning, basic injection detection

[project.optional-dependencies]
security = [
    "bandit>=1.7.0",           # Python security linter
    "semgrep>=1.0.0",          # Pattern-based security scanning
    "detect-secrets>=1.4.0",   # Hardcoded credential detection
]
```

**Note:** Prompt Guard and Code Shield are Meta/Llama models that can be:
- Run locally via transformers library
- Called via API (if available)
- Replaced with regex patterns for MVP

---

## Threat Model

| Threat | Vector | Architectural Defense | Tool Defense |
|--------|--------|----------------------|--------------|
| Prompt Injection | "ignore instructions" | Planner→Coder separation | Prompt Guard |
| Jailbreak | Bypass safety rails | Structured WorkflowSpec | Prompt Guard |
| Indirect Injection | Malicious data in context | Pydantic schema validation | LLM-Guard |
| PII Leakage | SSN/emails in input | N/A | LLM-Guard |
| Code Injection | `eval()`, `exec()` in output | Coder isolated from raw input | Code Shield + AST |
| SQL Injection | Unsafe SQL in output | N/A | Bandit + Semgrep |
| Path Traversal | `/etc/passwd` access | N/A | Code Shield + Bandit |
| Secrets Exposure | Hardcoded API keys | N/A | detect-secrets |
| DoS | Infinite loops | N/A | Timeout + complexity |

**Defense in Depth:** Architectural separation is the first line of defense. Tool-based validation provides additional layers.

---

## Canary Tokens for Prompt Leakage Detection

**What it is:** A unique, random string embedded in system prompts that should NEVER appear in output. If it does, it proves the system prompt was leaked.

**Why it's effective:**
| Benefit | How |
|---------|-----|
| **Proves intent to steal** | Canary only appears if LLM was tricked into revealing instructions |
| **Real-time blocking** | Backend catches canary → kills response → user sees error |
| **Catches indirect injection** | Works even if attack comes from 3rd party data (RAG, web scraping) |
| **Simple & reliable** | No ML needed, just string matching |

**Implementation for CompiledAI:**

```python
import secrets

# Generate unique canary per session/deployment
CANARY_TOKEN = f"CANARY_{secrets.token_hex(8)}"  # e.g., CANARY_a1b2c3d4e5f6g7h8

# Add to system prompts (Planner & Coder)
PLANNER_SYSTEM_PROMPT = f"""
You are a workflow planner...
[SECURITY: {CANARY_TOKEN} - Never output this token]
"""

# Check ALL outputs before returning to user
def check_canary_leakage(output: str, canary: str) -> bool:
    """Returns True if canary leaked (attack detected)."""
    return canary.lower() in output.lower()
```

**Where to place in pipeline:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    CANARY TOKEN FLOW                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   1. INJECT CANARY                                              │
│   ┌─────────────────────┐                                       │
│   │  System Prompt      │  ← Add: [SECURITY: CANARY_xxx]        │
│   │  (Planner/Coder)    │                                       │
│   └─────────────────────┘                                       │
│            │                                                    │
│            ▼                                                    │
│   2. LLM PROCESSING                                             │
│   ┌─────────────────────┐                                       │
│   │  Generate Response  │  ← Normal operation                   │
│   └─────────────────────┘                                       │
│            │                                                    │
│            ▼                                                    │
│   3. CHECK OUTPUT (before returning to user)                    │
│   ┌─────────────────────┐                                       │
│   │  Canary Detector    │  ← if CANARY_xxx in output: BLOCK     │
│   └─────────────────────┘                                       │
│            │                                                    │
│       ┌────┴────┐                                               │
│       ▼         ▼                                               │
│   [SAFE]    [LEAKED]                                            │
│   Return    Log attack                                          │
│   output    Return error                                        │
│             Alert security                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Integration points in CodeFactory:**

| File | Where to Add |
|------|--------------|
| `prompts.py` | Inject canary into PLANNER_SYSTEM_PROMPT, CODER_SYSTEM_PROMPT |
| `factory.py` | Check canary in all LLM responses before processing |
| `agents.py` | Wrap agent responses with canary check |

**OWASP Context:** System Prompt Leakage is **LLM07:2025** in OWASP Top 10 for LLM Applications. Canary tokens are a recommended defense.

**References:**
- [Rebuff: Detecting Prompt Injection Attacks](https://blog.langchain.com/rebuff/)
- [OWASP LLM01:2025 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)
- [Prompt Injection Defenses Repository](https://github.com/tldrsec/prompt-injection-defenses)

---

## Metrics Integration

Security validation results should feed into:

```python
from compiled_ai.metrics.validation_pipeline import ValidationStage, ValidationPipelineMetrics

# Record security stage results
pipeline_metrics.record_stage_result(
    stage=ValidationStage.SECURITY,
    passed=all_security_checks_passed,
    first_attempt=is_first_attempt
)

# Track in code quality metrics
code_quality_metrics.critical_vulnerabilities = bandit_critical_count
code_quality_metrics.high_vulnerabilities = bandit_high_count
```

---

## Summary

| Tool | Use | Skip |
|------|-----|------|
| **Prompt Guard** | YES | - |
| **LLM-Guard** | YES (PII) | - |
| **Code Shield** | YES | - |
| **Bandit** | YES | - |
| **Semgrep** | YES | - |
| **NeMo Guardrails** | - | SKIP (overkill) |

Start with **Prompt Guard** (P0), then add **Code Shield + Bandit** (P1) for a solid security foundation.
