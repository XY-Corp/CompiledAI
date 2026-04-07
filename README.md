# Compiled AI

**Paper:** [Compiled AI: Deterministic Code Generation for LLM-Based Workflow Automation](https://services.arxiv.org/html/submission/7435705/view) (arXiv 2026)

> This repository contains the code, benchmark suite, and evaluation framework accompanying the paper.

---

A benchmark suite for evaluating **Compiled AI** — a paradigm where LLMs generate executable code artifacts during a one-time "compilation" phase, eliminating runtime inference costs.

## The Problem

Current LLM-based automation approaches suffer from:
- **High per-transaction costs** — every request requires LLM inference
- **Non-deterministic outputs** — identical inputs can produce different results
- **Latency variability** — P99 latency is unpredictable
- **Reliability gaps** — 35-65% failure rates in multi-turn scenarios

## The Solution: Compiled AI

Instead of calling LLMs at runtime, Compiled AI:
1. **Generates code once** from a YAML specification
2. **Validates through 4 stages** (Security → Syntax → Execution → Accuracy)
3. **Executes deterministically** with zero runtime LLM costs

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
                                                                                 ▼
                                                                    ┌────────────────────────┐
                                                                    │   VALIDATED ARTIFACT   │
                                                                    │   • Temporal Activity  │
                                                                    │   • Production-ready   │
                                                                    │   • Zero runtime LLM   │
                                                                    │   • Deterministic      │
                                                                    └────────────────────────┘
```

## Installation

```bash
# Clone the repository
git clone https://github.com/XY-Corp/CompiledAI.git
cd CompiledAI

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

## Quick Start

```bash
# Set up API keys
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY and/or OPENAI_API_KEY

# Run the benchmark
uv run python run_benchmark.py --dataset bfcl --baseline code_factory
```

## Metrics

The benchmark evaluates 7 metric categories:

| Category | Key Metrics | Competitive Target |
|----------|-------------|-------------------|
| **Token Efficiency** | Compression ratio, LOC/token, Break-even N* | >4x compression |
| **Latency** | TTFT, TPOT, P50, P99, Jitter | TTFT <2s, TPOT <200ms |
| **Consistency** | Semantic entropy, Exact match rate | Entropy = 0 |
| **Reliability** | Task completion, Error rate | >50% completion |
| **Code Quality** | Cyclomatic complexity, Coverage, pass@k | Cyclomatic <10 |
| **Validation** | First-pass rate, Regen attempts | >70% first-pass |
| **Cost** | Generation cost, TCO, Determinism Advantage | DA > 1 |

### Break-Even Analysis

Compiled AI becomes cost-effective after N* executions:

```
N* = Generation_Cost / Runtime_Cost_Per_Execution
```

For function-calling tasks: **N* ≈ 17 executions** (paper result, BFCL evaluation).

## Task Categories

| Category | Example Tasks |
|----------|---------------|
| Document Processing | EOB extraction, Invoice parsing |
| Data Transformation | Schema mapping, Normalization |
| Decision Logic | Eligibility checks, Routing rules |
| API Orchestration | Multi-system updates, Webhooks |

## Datasets

The paper evaluates on two external benchmark datasets:

| Dataset | Instances | Description |
|---------|-----------|-------------|
| **BFCL v3** | 400 | Berkeley Function Calling Leaderboard — function calling accuracy |
| **DocILE** | 5,680 invoices | Document Information Extraction — KILE and LIR metrics |

### Download Datasets

```bash
# Download BFCL from HuggingFace (free)
python scripts/download_bfcl.py

# Download DocILE (requires access token from https://docile.rossum.ai/)
./scripts/download_dataset_docile.sh YOUR_TOKEN annotated-trainval datasets/docile --unzip
```

Downloaded data goes into `datasets/` (excluded from git).

## Security Validation Pipeline

CompiledAI includes a 3-gate security validation pipeline that protects against prompt injection, data leakage, and vulnerable code generation.

### Architecture

```
User Prompt → INPUT GATE → Compilation → CODE GATE → Execution → OUTPUT GATE → Result
              (validates     (LLM Coder    (validates    (runs        (checks for
               user input)    generates     generated     code)         leakage)
                              code)         code)
```

| Gate | Validators | Purpose |
|------|-----------|---------|
| **INPUT GATE** | PromptInjectionValidator, PIIScanner | Block malicious prompts, detect PII |
| **CODE GATE** | CodeShieldValidator | Block vulnerable generated code |
| **OUTPUT GATE** | CanaryManager | Detect system prompt leakage |

### Running Security Benchmarks

```bash
# INPUT GATE tests (prompt injection + PII detection)
uv run python run_benchmark.py --dataset security_input_gate --baseline code_factory

# CODE GATE tests (vulnerable code detection - 20 deterministic fixtures)
uv run python run_benchmark.py --dataset security_code_gate_fixtures

# OUTPUT GATE tests (canary leakage detection)
uv run python run_benchmark.py --dataset security_output_gate --baseline code_factory

# Direct validator testing with confusion matrix metrics
uv run python scripts/run_security_benchmark.py --category input_injection
```

### Security Benchmark Results

| Gate | Dataset | Instances | Success Rate |
|------|---------|-----------|--------------|
| INPUT GATE | `security_input_gate` | 55 | 96.7% |
| CODE GATE | `security_code_gate_fixtures` | 20 | 100% |
| OUTPUT GATE | `security_output_gate` | 40 | 87.5% |


## Baselines

Compare against:
- **Direct LLM** — Per-transaction inference
- **LangChain Agent** — Tool-using agent
- **Multi-Agent** — AutoGen-style coordination
- **Human Code** — Hand-written implementation

## Project Structure

```
CompiledAI/
├── src/compiled_ai/
│   ├── factory/          # Code generation (Templates, Modules, Prompts)
│   ├── validation/       # 4-stage validation pipeline
│   ├── baselines/        # Comparison implementations
│   ├── metrics/          # All 7 metric categories
│   ├── runner/           # Benchmark execution & dataset loading
│   └── utils/            # LLM client, logging, sandbox
├── datasets/             # Downloaded datasets (gitignored)
│   ├── xy_benchmark/     # Internal benchmark tasks
│   └── bfcl_v3/          # BFCL function calling (download required)
│       # DocILE goes in datasets/docile/ (download required)
├── scripts/              # CLI entry points & dataset downloaders
├── results/              # Benchmark results (gitignored)
└── tests/                # Unit & integration tests
```

## Development

```bash
# Install dev dependencies
uv sync --group dev

# Run tests
pytest

# Type checking
mypy src/

# Linting
ruff check src/
```

## Research

Based on evaluation frameworks and datasets including:
- **BFCL v3** — Berkeley Function Calling Leaderboard (gorilla-llm)
- **DocILE** — Document Information Extraction benchmark
- **Pan & Wang 2025** — Break-even analysis for code generation
- **AgentBench** — Multi-turn agent benchmark (ICLR 2024)

## License

MIT

## Citation

If you use this work, please cite:

```bibtex
@article{trooskens2026compiledai,
  title={Compiled AI: Deterministic Code Generation for LLM-Based Workflow Automation},
  author={Trooskens, Geert and Karlsberg, Aaron and Sharma, Anmol and De Brouwer, Lamara
          and Van Puyvelde, Max and Young, Matthew and Thickstun, John
          and Alterovitz, Gil and De Brouwer, Walter A.},
  journal={arXiv preprint},
  year={2026}
}
```

> **Note:** `results/`, `logs/`, and `workflows/` are generated at runtime and are not tracked in git.
