# Compiled AI Benchmark Repository Plan

## Overview

This plan outlines the structure and implementation of the Compiled AI benchmark repository based on the research paper. The benchmark will enable systematic comparison of compiled AI vs runtime inference approaches for enterprise workflow automation.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              COMPILED AI BENCHMARK SYSTEM                                │
└─────────────────────────────────────────────────────────────────────────────────────────┘

                                      ┌─────────────┐
                                      │   YAML      │
                                      │   Spec      │
                                      └──────┬──────┘
                                             │
                                             ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                 CODE FACTORY                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                       │
│  │   Templates     │    │    Modules      │    │  Prompt Blocks  │                       │
│  │  ┌───────────┐  │    │  ┌───────────┐  │    │  ┌───────────┐  │                       │
│  │  │ Simple    │  │    │  │ Database  │  │    │  │ HIPAA     │  │                       │
│  │  │ Streaming │  │    │  │ HTTP      │  │    │  │ PCI-DSS   │  │                       │
│  │  │ Validator │  │    │  │ Notif     │  │    │  │ SOC2      │  │                       │
│  │  │ Batch     │  │    │  │ ...       │  │    │  │ ...       │  │                       │
│  │  └───────────┘  │    │  └───────────┘  │    │  └───────────┘  │                       │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘                       │
│            │                    │                      │                                 │
│            └────────────────────┼──────────────────────┘                                 │
│                                 ▼                                                        │
│                    ┌────────────────────────┐                                            │
│                    │    CONFIG AGENT        │                                            │
│                    │  • Parse YAML spec     │                                            │
│                    │  • Select template     │                                            │
│                    │  • Compose modules     │                                            │
│                    │  • Assemble prompt     │                                            │
│                    └───────────┬────────────┘                                            │
│                                │                                                         │
│                                ▼                                                         │
│                    ┌────────────────────────┐                                            │
│                    │      GENERATOR         │──────────┐                                 │
│                    │  • LLM prompt          │          │                                 │
│                    │  • Code extraction     │          │ Regeneration                    │
│                    │  • Max 5 attempts      │◄─────────┤ on failure                      │
│                    └───────────┬────────────┘          │                                 │
└────────────────────────────────┼───────────────────────┼─────────────────────────────────┘
                                 │                       │
                                 ▼                       │
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                          4-STAGE VALIDATION PIPELINE                                     │
│                                                                                          │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│   │  SECURITY   │───▶│   SYNTAX    │───▶│  EXECUTION  │───▶│  ACCURACY   │              │
│   │  (Stage 1)  │    │  (Stage 2)  │    │  (Stage 3)  │    │  (Stage 4)  │              │
│   │             │    │             │    │             │    │             │              │
│   │ • Bandit    │    │ • AST parse │    │ • Sandbox   │    │ • Golden    │              │
│   │ • Semgrep   │    │ • mypy      │    │ • Fixtures  │    │   outputs   │              │
│   │ • Secrets   │    │ • ruff      │    │ • Timeout   │    │ • Threshold │              │
│   │ • OWASP     │    │ • radon     │    │ • Coverage  │    │   check     │              │
│   └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘              │
│         │                  │                  │                  │                      │
│         │ FAIL             │ FAIL             │ FAIL             │ FAIL                 │
│         └──────────────────┴──────────────────┴──────────────────┼──────────────────────┤
│                                                                  │                      │
│                                     Regenerate ◄─────────────────┘       ✓ PASS        │
│                                                                                ▼        │
└────────────────────────────────────────────────────────────────────────────────┬────────┘
                                                                                 │
                                 ┌───────────────────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   VALIDATED ARTIFACT   │
                    │   • Temporal Activity  │
                    │   • Production-ready   │
                    │   • Zero runtime LLM   │
                    │   • Deterministic      │
                    └───────────┬────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   BENCHMARK     │   │    BASELINES    │   │     METRICS     │
│   RUNNER        │   │                 │   │                 │
│                 │   │ • Direct LLM    │   │ • Token Effic.  │
│ • Task suite    │   │ • LangChain     │   │ • Latency       │
│ • Parallel      │   │ • Multi-agent   │   │ • Consistency   │
│ • Progress      │   │ • Human code    │   │ • Reliability   │
│                 │   │                 │   │ • Code Quality  │
└────────┬────────┘   └────────┬────────┘   │ • Validation    │
         │                     │            │ • Cost/TCO      │
         └─────────────────────┤            └────────┬────────┘
                               │                     │
                               ▼                     │
                    ┌────────────────────────┐       │
                    │   RESULTS COLLECTOR    │◄──────┘
                    │   • JSON/Parquet       │
                    │   • Aggregation        │
                    │   • Statistical        │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │      REPORTING         │
                    │   • HTML reports       │
                    │   • Comparison tables  │
                    │   • Visualizations     │
                    │   • Break-even plots   │
                    └────────────────────────┘


┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                              METRICS DETAIL                                              │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  TOKEN EFFICIENCY          LATENCY (MLPerf)        CONSISTENCY                          │
│  ──────────────────        ───────────────         ───────────                          │
│  • Compression: >4x        • TTFT: <2000ms         • Semantic entropy                   │
│  • LOC/token               • TPOT: <200ms          • Exact match rate                   │
│  • Amortization factor     • P50, P95, P99         • Schema compliance                  │
│  • Break-even N*           • Jitter                • Output variance = 0                │
│                                                                                          │
│  RELIABILITY               CODE QUALITY            COST                                  │
│  ───────────────           ────────────            ──────────                           │
│  • Task completion >50%    • Cyclomatic <10        • Generation cost                    │
│  • Error rate              • Cognitive <15         • Runtime cost/tx                    │
│  • Failure modes           • Coverage >80%         • TCO comparison                     │
│  • Recovery rate           • pass@k                • Determinism Advantage              │
│                                                                                          │
│  VALIDATION PIPELINE                                                                     │
│  ───────────────────                                                                     │
│  • First-pass rate: >70% competitive, >90% excellent                                    │
│  • Mean regen attempts: <2 (ChatGPT avg: 1.6)                                           │
│  • False positive rate: <10%                                                            │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Repository Structure

```
CompiledAI/
├── README.md                          # Project overview, quickstart
├── pyproject.toml                     # Python project config (uv/poetry)
├── .env.example                       # Environment variables template
│
├── paper/                             # Research paper
│   ├── compiled_ai_paper.md
│   └── compiled_ai_arxiv_paper_v2.pdf
│
├── src/
│   └── compiled_ai/
│       ├── __init__.py
│       │
│       ├── factory/                   # Code Foundry (Generation System)
│       │   ├── __init__.py
│       │   ├── config_agent.py        # Orchestrates generation
│       │   ├── generator.py           # LLM code generation
│       │   ├── assembler.py           # Combines template + generated code
│       │   │
│       │   ├── templates/             # Pre-built code templates
│       │   │   ├── __init__.py
│       │   │   ├── base.py            # Base template class
│       │   │   ├── simple_agent.py    # Synchronous request-response
│       │   │   ├── streaming_agent.py # Chunked data processing
│       │   │   ├── validator_agent.py # Input validation with fallback
│       │   │   └── batch_agent.py     # Bulk processing with checkpointing
│       │   │
│       │   ├── modules/               # Functional capability modules
│       │   │   ├── __init__.py
│       │   │   ├── base.py            # Base module class
│       │   │   ├── database.py        # Connection pooling, queries
│       │   │   ├── http.py            # API calls with retries
│       │   │   └── notification.py    # Email, SMS, webhook delivery
│       │   │
│       │   └── prompts/               # Reusable prompt fragments
│       │       ├── __init__.py
│       │       ├── base.py            # Prompt block assembly
│       │       ├── hipaa.py           # HIPAA compliance constraints
│       │       ├── pci_dss.py         # PCI-DSS rules
│       │       └── soc2.py            # SOC 2 compliance
│       │
│       ├── validation/                # 4-Stage Validation Pipeline
│       │   ├── __init__.py
│       │   ├── pipeline.py            # Orchestrates all stages
│       │   ├── security.py            # Stage 1: Bandit, Semgrep analysis
│       │   ├── syntax.py              # Stage 2: AST, mypy, ruff
│       │   ├── execution.py           # Stage 3: Sandboxed test execution
│       │   └── accuracy.py            # Stage 4: Golden dataset comparison
│       │
│       ├── baselines/                 # Baseline Implementations
│       │   ├── __init__.py
│       │   ├── direct_llm.py          # Per-transaction LLM calls
│       │   ├── langchain_agent.py     # LangChain workflow
│       │   └── multi_agent.py         # AutoGen-style multi-agent
│       │
│       ├── metrics/                   # Evaluation Metrics
│       │   ├── __init__.py
│       │   ├── token_efficiency.py    # GenTokens, RuntimeTokens, BreakEven
│       │   ├── latency.py             # P50, P99, Jitter, ColdStart
│       │   ├── consistency.py         # OutputVariance, Reproducibility
│       │   ├── reliability.py         # TaskCompletion, ErrorRate, MTBF
│       │   ├── code_quality.py        # Security, Type, Lint, Complexity
│       │   ├── validation_metrics.py  # FirstPassRate, RegenDistribution
│       │   └── cost.py                # CostPerTx, TCO, CostRatio
│       │
│       ├── runner/                    # Benchmark Execution
│       │   ├── __init__.py
│       │   ├── benchmark.py           # Main benchmark runner
│       │   ├── experiment.py          # Single experiment execution
│       │   └── reporter.py            # Results aggregation & reporting
│       │
│       └── utils/                     # Shared utilities
│           ├── __init__.py
│           ├── llm_client.py          # LLM API wrapper (Claude, OpenAI)
│           ├── sandbox.py             # Code execution sandbox
│           └── logging.py             # Structured logging
│
├── tasks/                             # Benchmark Task Suite
│   ├── README.md                      # Task documentation
│   │
│   ├── document_processing/           # Category 1
│   │   ├── eob_extraction/
│   │   │   ├── spec.yaml              # Workflow specification
│   │   │   ├── test_inputs/           # Input fixtures
│   │   │   └── golden_outputs/        # Expected outputs
│   │   └── invoice_parsing/
│   │       ├── spec.yaml
│   │       ├── test_inputs/
│   │       └── golden_outputs/
│   │
│   ├── data_transformation/           # Category 2
│   │   ├── schema_mapping/
│   │   │   ├── spec.yaml
│   │   │   ├── test_inputs/
│   │   │   └── golden_outputs/
│   │   └── data_normalization/
│   │       ├── spec.yaml
│   │       ├── test_inputs/
│   │       └── golden_outputs/
│   │
│   ├── decision_logic/                # Category 3
│   │   ├── eligibility_check/
│   │   │   ├── spec.yaml
│   │   │   ├── test_inputs/
│   │   │   └── golden_outputs/
│   │   ├── routing_rules/
│   │   │   ├── spec.yaml
│   │   │   ├── test_inputs/
│   │   │   └── golden_outputs/
│   │   └── classification/
│   │       ├── spec.yaml
│   │       ├── test_inputs/
│   │       └── golden_outputs/
│   │
│   └── api_orchestration/             # Category 4
│       ├── multi_system_update/
│       │   ├── spec.yaml
│       │   ├── test_inputs/
│       │   └── golden_outputs/
│       └── webhook_handler/
│           ├── spec.yaml
│           ├── test_inputs/
│           └── golden_outputs/
│
├── results/                           # Benchmark results (gitignored)
│   └── .gitkeep
│
├── scripts/                           # CLI scripts
│   ├── run_benchmark.py               # Main entry point
│   ├── generate_report.py             # Generate HTML/PDF reports
│   └── compare_methods.py             # Compare compiled vs runtime
│
└── tests/                             # Unit & integration tests
    ├── conftest.py
    ├── test_factory/
    ├── test_validation/
    ├── test_baselines/
    └── test_metrics/
```

---

## Implementation Phases

### Phase 1: Core Infrastructure
**Estimated scope: Foundation components**

1. **Project Setup**
   - Initialize Python project with pyproject.toml
   - Configure dependencies (anthropic, openai, bandit, mypy, ruff, pytest)
   - Set up development tooling (ruff, pre-commit)

2. **LLM Client Abstraction**
   - Unified interface for Claude and OpenAI APIs
   - Token counting and tracking
   - Response caching for development

3. **Basic Metrics Framework**
   - Token efficiency metrics
   - Timing/latency measurement
   - Results storage format (JSON/Parquet)

### Phase 2: Code Foundry
**Estimated scope: Generation pipeline**

1. **Templates**
   - Base template class with slot injection
   - SimpleAgent template (basic workflow)
   - Implement remaining templates

2. **Modules**
   - Module interface and composition
   - DatabaseModule with mock support
   - HTTPModule with mock server

3. **Config Agent**
   - YAML spec parser
   - Template/module selection logic
   - Prompt assembly

4. **Generator**
   - LLM prompt construction
   - Code extraction from response
   - Regeneration on validation failure

### Phase 3: Validation Pipeline
**Estimated scope: 4-stage validation**

1. **Security Stage**
   - Bandit integration
   - Semgrep rules
   - Custom security checks

2. **Syntax Stage**
   - AST parsing validation
   - mypy type checking
   - ruff linting

3. **Execution Stage**
   - Sandbox environment (subprocess/Docker)
   - Test fixture runner
   - Timeout handling

4. **Accuracy Stage**
   - Golden output comparison
   - Semantic similarity metrics
   - Threshold configuration

### Phase 4: Task Suite
**Estimated scope: Benchmark tasks**

1. **Document Processing Tasks**
   - EOB extraction (healthcare)
   - Invoice parsing (finance)

2. **Data Transformation Tasks**
   - Schema mapping
   - Data normalization

3. **Decision Logic Tasks**
   - Eligibility checking
   - Routing rules
   - Classification

4. **API Orchestration Tasks**
   - Multi-system update
   - Webhook handling

### Phase 5: Baselines
**Estimated scope: Comparison implementations**

1. **Direct LLM Baseline**
   - Per-transaction prompt
   - Token/latency measurement

2. **LangChain Baseline**
   - Equivalent agent implementation
   - Tool definitions

3. **Multi-Agent Baseline**
   - AutoGen-style setup
   - Agent coordination

### Phase 6: Benchmark Runner & Reporting
**Estimated scope: Execution and analysis**

1. **Benchmark Runner**
   - CLI interface
   - Parallel execution
   - Progress tracking

2. **Metrics Collection**
   - All 7 metric categories
   - Statistical aggregation

3. **Reporting**
   - HTML report generation
   - Comparison tables
   - Visualization (matplotlib/plotly)

---

## Task Specification Schema (YAML)

```yaml
# Example: tasks/document_processing/eob_extraction/spec.yaml
name: eob_extraction
version: "1.0"
category: document_processing
description: Extract structured data from Explanation of Benefits documents

template: SimpleAgent
modules:
  - database
  - http

compliance:
  - hipaa

input_schema:
  type: object
  properties:
    eob_document:
      type: string
      description: Raw EOB document text or PDF path
    patient_id:
      type: string
  required: [eob_document, patient_id]

output_schema:
  type: object
  properties:
    claim_id:
      type: string
    patient_id:
      type: string
    payments:
      type: array
      items:
        type: object
        properties:
          service_code: {type: string}
          billed: {type: number}
          allowed: {type: number}
          paid: {type: number}
    total_billed: {type: number}
    total_paid: {type: number}

business_logic: |
  Extract claim ID and patient ID from the EOB header.
  Parse each line item to extract service code, billed amount,
  allowed amount, and paid amount. Calculate totals.
  Validate all required fields are present.

test_cases:
  - name: basic_eob
    input_file: test_inputs/basic_eob.json
    expected_output_file: golden_outputs/basic_eob.json
  - name: multi_line_eob
    input_file: test_inputs/multi_line_eob.json
    expected_output_file: golden_outputs/multi_line_eob.json

accuracy_threshold: 0.95
complexity: medium
```

---

## Key Metrics Implementation

### Token Efficiency
```python
@dataclass
class TokenMetrics:
    gen_tokens: int           # One-time generation cost
    runtime_tokens_per_tx: float  # Per-transaction (should be ~0 for compiled)
    break_even_n: int         # n* where compiled < runtime
    compression_ratio: float  # prompt_tokens / generated_loc
```

### Consistency
```python
def measure_output_variance(system, inputs: list, n_runs: int = 1000) -> float:
    """Compute entropy of outputs for identical inputs."""
    outputs = [system.run(inputs) for _ in range(n_runs)]
    unique_outputs = Counter(json.dumps(o, sort_keys=True) for o in outputs)
    probs = [c/n_runs for c in unique_outputs.values()]
    return -sum(p * log(p) for p in probs if p > 0)  # Should be 0 for compiled
```

### Validation Pipeline
```python
@dataclass
class ValidationMetrics:
    first_pass_rate: dict[str, float]  # Per-stage first pass rates
    overall_first_pass: float          # All stages without regen
    regen_distribution: list[int]      # [0, 1, 2, 3, 4+] attempt counts
    time_to_valid: float               # Seconds from spec to valid artifact
```

---

## Dependencies

```toml
[project]
dependencies = [
    # LLM APIs
    "anthropic>=0.40.0",
    "openai>=1.50.0",

    # Validation tools
    "bandit>=1.8.0",
    "mypy>=1.13.0",
    "ruff>=0.8.0",
    "radon>=6.0.0",

    # Workflow/Agent frameworks (for baselines)
    "langchain>=0.3.0",
    "autogen>=0.4.0",

    # Data handling
    "pyyaml>=6.0",
    "pydantic>=2.10.0",
    "jsonschema>=4.23.0",

    # Testing & metrics
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "numpy>=2.0.0",
    "pandas>=2.2.0",

    # Reporting
    "rich>=13.9.0",
    "plotly>=5.24.0",
    "jinja2>=3.1.0",
]
```

---

## Success Criteria

1. **Functional Benchmark**: Can generate code from YAML specs, validate through 4 stages, and produce working Temporal-compatible activities

2. **Baseline Comparison**: All 4 baselines (Direct LLM, LangChain, Multi-agent, Human code) implemented and measurable

3. **Complete Metrics**: All 7 metric categories producing data:
   - Token efficiency with break-even calculation
   - Latency distribution (P50, P99, Jitter)
   - Consistency (entropy = 0 for compiled)
   - Reliability (completion rate)
   - Code quality scores
   - Validation pipeline pass rates
   - TCO comparison

4. **Task Coverage**: At least 2 tasks per category (8+ total tasks)

5. **Reproducible Results**: Deterministic benchmark execution with seed control

---

## Next Steps

1. [ ] Initialize project with pyproject.toml
2. [ ] Implement LLM client abstraction
3. [ ] Build SimpleAgent template
4. [ ] Create first task spec (EOB extraction)
5. [ ] Implement validation pipeline stages
6. [ ] Build benchmark runner
7. [ ] Add remaining templates and tasks
8. [ ] Implement baselines
9. [ ] Generate comparison report
