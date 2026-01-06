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
                                                                    │   • Executable code    │
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
│   ├── runner/           # Benchmark execution
│   └── utils/            # LLM client, logging, sandbox
├── tasks/                # Benchmark task suite
├── scripts/              # CLI entry points
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

Based on evaluation frameworks including:
- MLPerf Inference (latency standards)
- AgentBench (ICLR 2024)
- τ-Bench (Yao et al., 2024)
- CLASSic Framework (ICLR 2025 Workshop)
- Pan & Wang 2025 (break-even analysis)

## License

MIT

## Citation

```bibtex
@article{compiledai2025,
  title={Compiled AI: From Runtime Inference to Deterministic Execution},
  year={2025}
}
```
