# Compiled AI Benchmark

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
git clone https://github.com/your-org/CompiledAI.git
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
python scripts/run_benchmark.py --task document_processing/eob_extraction
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

For typical workflows: **N* < 100 executions** (often < 10).

## Task Categories

| Category | Example Tasks |
|----------|---------------|
| Document Processing | EOB extraction, Invoice parsing |
| Data Transformation | Schema mapping, Normalization |
| Decision Logic | Eligibility checks, Routing rules |
| API Orchestration | Multi-system updates, Webhooks |

## Datasets

The benchmark includes both internal and external datasets:

### Available Datasets

| Dataset | Tasks | Instances | Description |
|---------|-------|-----------|-------------|
| **XY_Benchmark** | 5 | 12 | Internal benchmark (classification, normalization, API selection) |
| **BFCL v3** | 9 | 2,810 | Berkeley Function Calling Leaderboard (function calling accuracy) |
| **AgentBench** | 5 | 146 | Multi-turn agent tasks (OS, DB, KG, ALFWorld, Avalon) |
| **DocILE** | — | — | Document extraction (requires access token) |

### Download Datasets

```bash
# Download BFCL from HuggingFace (free)
python scripts/download_bfcl.py

# Download AgentBench from GitHub (free)
python scripts/download_agentbench.py

# Download DocILE (requires token from https://docile.rossum.ai/)
./scripts/download_docile.sh YOUR_TOKEN
```

### Load Datasets

```python
from compiled_ai.runner import DatasetLoader

loader = DatasetLoader("datasets")

# Load internal benchmark
xy = loader.load("xy_benchmark")

# Load external datasets
bfcl = loader.load_external("bfcl", "datasets/bfcl_v4")
agentbench = loader.load_external("agentbench", "datasets/agentbench")

# With filtering options
bfcl_simple = loader.load_external(
    "bfcl", "datasets/bfcl_v4",
    categories=["simple", "multiple"],
    max_per_category=100
)
```

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
| INPUT GATE | `security_input_gate` | 55 | 80% |
| CODE GATE | `security_code_gate_fixtures` | 20 | 100% |
| OUTPUT GATE | `security_output_gate` | 40 | 91.7% |


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
│   ├── bfcl_v4/          # BFCL function calling (download required)
│   └── agentbench/       # AgentBench multi-turn (download required)
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
- **MLPerf Inference** — Latency measurement standards
- **BFCL v3** — Berkeley Function Calling Leaderboard (gorilla-llm)
- **AgentBench** — Multi-turn agent benchmark (ICLR 2024)
- **DocILE** — Document Information Extraction benchmark
- **τ-Bench** — Tool-agent benchmark (Yao et al., 2024)
- **CLASSic Framework** — ICLR 2025 Workshop
- **Pan & Wang 2025** — Break-even analysis for code generation

## License

MIT

## Citation

```bibtex
@article{compiledai2025,
  title={Compiled AI: From Runtime Inference to Deterministic Execution},
  year={2025}
}
```
