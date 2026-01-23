# CompiledAI - Essentials

## What It Is

**CompiledAI** is a research benchmark suite for deterministic LLM-based workflow automation. Instead of calling LLMs at runtime (expensive, non-deterministic), it generates code once during "compilation," then executes deterministically with zero marginal LLM cost.

**Authors:** Geert Trooskens, Aaron Karlsberg, Anmol Sharma, Lamara De Brouwer, Walter A. De Brouwer
**Affiliation:** XY.AI Labs, Stanford University School of Medicine

---

## The Problem

Current LLM agents suffer from:
- High per-transaction inference costs
- Non-deterministic outputs (identical inputs → different results)
- Unpredictable latency (P99 variance)
- Reliability gaps (35-65% failure rates in multi-turn workflows)

## The Solution

```
Generate Once → Validate Thoroughly → Execute Deterministically
```

**Break-Even:** Compiled AI beats runtime inference after N* executions:
```
N* = Generation_Cost / Runtime_Cost_Per_Execution
```
Typically **N* < 100** (often < 10)

---

## Tech Stack

| Category | Tools |
|----------|-------|
| Language | Python 3.11+ |
| Package Manager | uv (recommended) |
| LLM Providers | Anthropic Claude Opus 4.5, OpenAI GPT-4o, Google Gemini |
| Code Generation | PydanticAI agents |
| Workflow Execution | Temporal (prod), XY Local Workflow Executor (test) |
| Validation | Bandit, Semgrep, mypy, ruff, radon |
| Data | Pydantic v2, PyYAML, jsonschema |

---

## Architecture

```
YAML Spec (task definition)
         │
         ▼
┌─────────────────────┐
│    CONFIG AGENT     │  Parse spec, select templates
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│    CODE FACTORY     │
│  ┌───────────────┐  │
│  │ Planner Agent │  │  Design workflow structure
│  └───────────────┘  │
│  ┌───────────────┐  │
│  │  Coder Agent  │  │  Generate YAML + Python
│  └───────────────┘  │
└─────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│       4-STAGE VALIDATION PIPELINE           │
├─────────────────────────────────────────────┤
│ Stage 1: SECURITY   │ Bandit, Semgrep       │
│ Stage 2: SYNTAX     │ AST, mypy, ruff       │
│ Stage 3: EXECUTION  │ Sandbox, fixtures     │
│ Stage 4: ACCURACY   │ Golden output match   │
└─────────────────────────────────────────────┘
         │
         ▼
   TEMPORAL ACTIVITY
   (Deterministic, validated, production-ready)
```

**Self-Healing:** Auto-regenerates on validation failure (max 5 attempts)

---

## Project Structure

```
CompiledAI/
├── src/compiled_ai/
│   ├── factory/
│   │   ├── code_factory/          # Core generation system
│   │   │   ├── factory.py         # Main orchestrator
│   │   │   ├── agents.py          # Planner + Coder agents
│   │   │   ├── template_registry.py
│   │   │   ├── semantic_search.py
│   │   │   └── llm_adapter.py
│   │   ├── activities/            # Pre-built templates
│   │   └── XYLocalWorkflowExecutor/
│   ├── validation/                # 4-stage pipeline
│   ├── baselines/                 # Comparison implementations
│   │   ├── direct_llm.py
│   │   ├── code_factory.py
│   │   ├── langchain_agent.py
│   │   └── multi_agent.py
│   ├── metrics/                   # 7 evaluation categories
│   │   ├── token_efficiency.py
│   │   ├── latency.py
│   │   ├── consistency.py
│   │   ├── reliability.py
│   │   ├── code_quality.py
│   │   ├── validation_pipeline.py
│   │   └── cost.py
│   ├── runner/                    # Benchmark execution
│   └── evaluation/                # Output evaluators
│
├── datasets/
│   ├── xy_benchmark/              # 5 tasks, 12 instances
│   ├── bfcl_v4/                   # 9 categories, 2,810 instances
│   └── agentbench/                # 5 environments, 146 instances
│
├── workflows/                     # Generated artifacts
├── results/                       # Benchmark results (97+ files)
├── paper/                         # Research documentation
│   ├── compiled_ai_paper.md
│   └── framework.md               # Evaluation framework
│
├── scripts/
│   ├── run_benchmark.py           # Main runner
│   ├── run_bfcl_benchmark.py
│   └── run_agentbench_benchmark.py
│
└── tests/
```

---

## Key Components

### Code Factory (`factory/code_factory/`)

| File | Purpose |
|------|---------|
| `factory.py` | Main orchestrator with regeneration loop |
| `agents.py` | PydanticAI Planner + Coder agents |
| `template_registry.py` | Searchable activity templates |
| `semantic_search.py` | Embedding-based template discovery |
| `llm_adapter.py` | Multi-provider abstraction |
| `compilation_metrics.py` | Token amortization tracking |

### Validation Pipeline (`validation/`)

| Stage | Tools | Checks |
|-------|-------|--------|
| Security | Bandit, Semgrep | Injection, malware, key leaks |
| Syntax | AST, mypy, ruff, radon | Types, linting, complexity <10 |
| Execution | Sandbox, fixtures | Test cases, coverage >80% |
| Accuracy | Golden outputs | Schema compliance, output match |

### Metrics Engine (`metrics/`)

| Category | Key Metrics |
|----------|-------------|
| Token Efficiency | Compression ratio (>4x), Break-even N* |
| Latency | TTFT (<500ms), TPOT (<200ms), P99 |
| Consistency | Semantic entropy, Exact match rate |
| Reliability | Task completion (>50%), Error rates |
| Code Quality | Cyclomatic complexity (<10), pass@k |
| Validation | First-pass rate (>70%), Regen attempts |
| Cost | Determinism Advantage (>1 = winning) |

### Baselines (`baselines/`)

| Baseline | Description |
|----------|-------------|
| Direct LLM | Per-transaction inference (control) |
| Code Factory | Compiled with template reuse |
| LangChain Agent | Tool-using agent framework |
| Multi-Agent | AutoGen-style coordination |

---

## Benchmark Datasets

| Dataset | Instances | Focus |
|---------|-----------|-------|
| XY_Benchmark | 12 | Internal: classification, normalization, extraction |
| BFCL v3 | 2,810 | Function calling accuracy |
| AgentBench | 146 | Multi-turn agents (OS, DB, Web) |

---

## Competitive Targets

| Metric | Competitive | Excellent |
|--------|-------------|-----------|
| Compression Ratio | >4x | >10x |
| Break-Even N* | <100 | <10 |
| TTFT | <500ms | <200ms |
| Exact Match Rate | >80% | >95% |
| Task Completion | >50% | >75% |
| Cyclomatic Complexity | <10 | <5 |
| First-Pass Rate | >70% | >90% |
| Determinism Advantage | >1 | >10 |

---

## Quick Start

```bash
# Install
uv sync

# Configure
cp .env.example .env
# Add: ANTHROPIC_API_KEY=your_key

# Run benchmarks
python scripts/run_benchmark.py
python scripts/run_bfcl_benchmark.py
python scripts/run_xy_benchmark.py

# Development
pytest
mypy src/
ruff check src/
```

---

## Key Files

| File | Purpose |
|------|---------|
| `scripts/run_benchmark.py` | Main interactive runner |
| `BENCHMARK_PLAN.md` | Implementation specification |
| `paper/framework.md` | Evaluation framework |
| `paper/compiled_ai_paper.md` | Research paper |
| `src/compiled_ai/factory/code_factory/factory.py` | Core orchestrator |

---

## Research Contributions

**Novel Metrics:**
1. **Compression Ratio** - Output tokens / Input tokens
2. **Token Amortization Factor** - Gen tokens / Expected executions
3. **Determinism Advantage** - Runtime cost × N / Generation cost
4. **Break-Even N*** - Executions for cost parity
5. **First-Pass Rate** - Validation pass without regeneration

**Research Foundations:**
- MLPerf Inference (latency standards)
- BFCL v3 (function calling benchmark)
- AgentBench (multi-turn evaluation, ICLR 2024)
- Semantic Entropy (Nature 2024)
- Pan & Wang 2025 (break-even analysis)
