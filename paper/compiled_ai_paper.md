# Compiled AI: Deterministic Code Generation for LLM-Based Workflow Automation

**Authors:**
- Geert Trooskens¹
- Aaron Karlsberg¹
- Anmol Sharma¹
- Lamara De Brouwer¹
- Walter A. De Brouwer¹˒²

¹XY.AI Labs, Palo Alto, CA
²Stanford University School of Medicine, Stanford, CA
Contact: foundation@xy.ai

---

## Abstract

We study *compiled AI*, a paradigm in which large language models generate executable code artifacts during a one-time compilation phase, after which workflows execute deterministically without further model invocation. By constraining generation to narrow business-logic functions embedded in validated templates, compiled AI trades runtime flexibility for predictability, auditability, and cost efficiency.

We introduce (i) a system architecture for constrained LLM-based code generation, (ii) a four-stage generation-and-validation pipeline that converts probabilistic model output into production-ready code artifacts, and (iii) an evaluation framework that measures operational metrics including token amortization, determinism, reliability, validation effectiveness, and cost. We evaluate compiled AI on enterprise workflow tasks and compare it against runtime inference baselines, showing that compilation substantially reduces token consumption and execution variance in well-specified, high-volume workflows.

---

## 1. Introduction

Large language models (LLMs) are increasingly deployed to automate enterprise workflows, evolving from question-answering systems toward autonomous agent architectures. Recent frameworks enable LLMs to reason over tools, APIs, and multi-step tasks at runtime, often through conversational or multi-agent interaction patterns. While these approaches demonstrate flexibility, they rely on repeated model invocation during execution, leading to high token consumption, variable latency, and non-deterministic behavior.

Empirical studies and industrial deployments have highlighted persistent reliability challenges in runtime agent systems, particularly in multi-step business workflows where success rates degrade due to specification ambiguity, inter-agent coordination failures, and stochastic model outputs. These limitations pose obstacles to deployment in enterprise environments, where determinism, auditability, and cost predictability are often strict requirements.

This paper investigates an alternative design point: *compiled AI*, a paradigm in which LLMs generate executable code artifacts during a one-time compilation phase, after which workflows execute deterministically without further model inference. The key observation motivating this work is that many enterprise workflows require intelligence to *design* but not to *execute* repeatedly. Once business logic is specified and validated, repeated execution can be handled by conventional software infrastructure.

Compiled AI represents a trade-off between flexibility and determinism. Rather than interpreting natural language or reasoning at runtime, an LLM is constrained to generate narrow business-logic functions within pre-validated templates. These generated artifacts are subjected to a multi-stage validation pipeline—including security analysis, syntactic verification, execution testing, and output accuracy checks—before deployment. After validation, workflows execute as static code with predictable latency, zero stochasticity, and near-zero marginal inference cost.

### Token Consumption: Compiled AI vs Runtime Inference

```
Total Tokens
     ^
     |                                    /  Runtime (linear growth)
     |                                  /
     |                                /
     |                              /
     |                            /
     |          Reduced cost   /
     |              area     /
     |                     /
     |                   /
     |                 /
     |--------------*----------------- Compiled (flat after generation)
     |            / |
     |          /   |
     |        /     |
     | Gen  /       |
     | cost         |
     |/             n* (break-even)
     +-----------------------------------------> Transactions (n)
                100    1K    10K    100K
```

*Figure 1: Token consumption comparison. Runtime token consumption grows linearly with transaction volume. Compiled AI incurs a one-time generation cost, then executes at near-zero marginal token cost. After the break-even point n*, compiled AI exhibits reduced total cost.*

### Contributions

This paper makes three contributions:

1. We introduce an architecture for constrained LLM-based code generation in which models produce bounded business-logic functions embedded in durable workflow templates, enabling deterministic execution (Section 3).

2. We present a four-stage generation-and-validation pipeline that empirically converts probabilistic model output into production-ready code artifacts through iterative regeneration (Section 3).

3. We define an evaluation framework that measures the operational viability of LLM-based workflow systems using metrics for token amortization, determinism, reliability, validation effectiveness, and cost (Section 4).

Our goal is not to replace runtime inference in all settings, but to provide a principled basis for identifying regimes—such as well-specified, high-volume workflows—where compilation yields operational advantages.

---

## 2. Related Work

### Novelty and Scope

Prior work on LLM-based agents, program-aided reasoning, and workflow synthesis has focused primarily on model capability—whether systems can generate or reason over programs. In contrast, this work treats production viability as a first-class concern. Our contributions are not a new code generation algorithm per se, but a systems-oriented study of how probabilistic LLM outputs can be converted into deterministic, auditable execution artifacts. To our knowledge, this is the first systematic evaluation of LLM-based workflow automation using operational and economic metrics such as token amortization, execution determinism, validation convergence, and cost at scale.

### 2.1 LLM Code Generation

Code generation capabilities have improved rapidly. On SWE-Bench Verified, models improved from 49.0% (Claude 3.5 Sonnet, late 2024) to 80.9% (Claude Opus 4.5, November 2025)—a 31.9 percentage point gain in twelve months.

| Benchmark | Model | Score | Human | Date |
|-----------|-------|-------|-------|------|
| SWE-Bench Verified | Claude Opus 4.5 | 80.9% | --- | Nov 2025 |
| SWE-Bench Verified | GPT-5.2 | 80.0% | --- | Dec 2025 |
| SWE-Bench Verified | Gemini 3 Pro | 76.2% | --- | Nov 2025 |
| HumanEval | Claude Opus 4.5 | 96.4% | 100% | Nov 2025 |
| BigCodeBench | GPT-4o | 60.0% | 97% | 2024 |
| τ-bench (retail) | GPT-4o | <50% | --- | Jun 2024 |
| LiveCodeBench | Claude Opus 4.5 | 68.3% | --- | Nov 2025 |

*Table 1: Code generation benchmark performance, December 2025. Note: HumanEval is now saturated (>95%); BigCodeBench reveals substantial gaps versus human performance.*

Anthropic CEO Dario Amodei stated at Dreamforce 2025 that "within Anthropic and within a number of companies that we work with," approximately 90% of code is now AI-generated. While this applies to select organizations rather than industry-wide, it suggests code generation is transitioning from assistance to primary production mode in leading AI-native companies.

Karpathy's "Software 2.0" framework characterized neural networks as an alternative programming paradigm. Research on program-aided reasoning demonstrates that code representations improve LLM performance: PAL improved mathematical reasoning, Program of Thoughts improved financial reasoning, and Chain of Code achieved 84% on BIG-Bench Hard.

### 2.2 Agent Frameworks and Their Limitations

Multi-agent systems coordinate multiple LLM instances. AutoGen enables conversational workflows; CrewAI provides role-based orchestration; LangChain offers composability abstractions.

These frameworks emphasize flexibility and expressiveness, often at the expense of determinism and predictable execution behavior in multi-step workflows. As a result, they can be challenging to deploy in environments that require strict auditability or cost predictability. Salesforce reports that leading AI agents exhibit approximately 35% success rates in multi-turn business scenarios. Cemri et al. analyzed 150 multi-agent systems across six frameworks and observed failure rates between 41–87%, with specification problems (41.8%) and inter-agent coordination failures (36.9%) accounting for approximately 79% of observed breakdowns.

Even with "deterministic" settings, LLM outputs exhibit variance: Atil et al. found accuracy varies up to 15% across runs at temperature=0, with the gap between best and worst possible performance reaching 70%. These observations motivate exploration of alternative architectures that reduce execution-time variance.

### 2.3 Workflow Orchestration

Durable execution engines provide reliability properties. Temporal offers state management, automatic retries, and fault tolerance. Production deployments support these at scale:

- **Netflix**: transient failure rates from 4% to 0.0001%
- **Coinbase**: velocity improvements for complex financial workflows
- **Maersk**: feature delivery from 60-80 days to 5-10 days
- **Replit**: scaled to millions of concurrent environments

Our work combines LLM code generation with durable execution, generating Temporal activities rather than invoking models at runtime.

### 2.4 LLM-Based Workflow Automation

Recent work has explored LLM-driven workflow generation. WorkflowLLM constructs WorkflowBench with 106,763 samples covering 1,503 APIs, training models to generate Python-style workflow code from specifications—a paradigm shift from traditional RPA to "Agentic Process Automation." FlowMind generates workflows that prevent runtime hallucinations via structured intermediate representations. In embedded systems, spec2code combines LLM generation with formal verification critics, producing industrial-quality code from ACSL specifications.

These approaches share our insight that LLMs should generate *artifacts* rather than reason at runtime. Our contribution extends this to enterprise workflow automation with explicit evaluation metrics.

### 2.5 Industrial Deployments

Recent large-scale deployments of agentic systems demonstrate growing demand for automated task execution. These systems typically rely on runtime inference, motivating exploration of alternative architectures that reduce execution-time variance and inference cost.

**Relation to Program Synthesis:** Compiled AI shares surface similarities with prior work on program synthesis and specification-driven code generation. However, our focus differs in two respects. First, we evaluate generated artifacts primarily through operational metrics—such as determinism, regeneration convergence, and token amortization—rather than synthesis correctness alone. Second, we study LLM generation as a component within a production workflow system, where validation, retries, and execution cost are first-class concerns. As a result, our contributions are systems-oriented rather than algorithmic.

### 2.6 Formal Methods and Constrained Generation

The challenge of verifying LLM-generated code has sparked renewed interest in formal methods integration. Dalrymple et al. propose a "Guaranteed Safe AI" framework combining world models, safety specifications, and formal verifiers—conceptually aligned with our validation pipeline approach.

Constrained decoding provides compile-time constraints: Mündler et al. demonstrate that type-constrained generation reduces compilation errors by >50% while improving pass@1 by 3.5–37%. For healthcare specifically, Neupane et al. present a framework for HIPAA-compliant agentic AI systems, integrating attribute-based access control with PHI sanitization pipelines.

Our work operationalizes these insights for enterprise workflows, using templates and validation stages rather than formal proofs to support practical compliance requirements.

---

## 3. System Architecture

### 3.1 Design Principles

Our system implements four principles:

**Principle 1: Constrained Generation.** We limit LLM generation to narrow, well-defined functions. The model produces business logic (20-50 lines); templates provide infrastructure. This bounds the output space, reducing hallucination risk.

**Principle 2: Compilation over Interpretation.** Generated code is validated, tested, and deployed as static artifacts. Runtime behavior is deterministic. The LLM exits the execution loop.

**Principle 3: Validation as Requirement.** Every artifact passes a four-stage pipeline before deployment—possible precisely because we generate code rather than interpret configurations.

**Principle 4: Compliance by Construction.** Regulatory constraints (HIPAA, PCI-DSS, SOC 2) are encoded in templates and prompt blocks, ensuring generated code inherits compliance properties.

### 3.2 Component Overview

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌──────────┐    ┌────────────────────────────┐    ┌──────────┐
│  YAML   │───>│ Config  │───>│   LLM   │───>│ Assemble │───>│    Validation Pipeline     │───>│ Temporal │
│  Spec   │    │  Agent  │    │Generate │    │          │    │ Security│Syntax│Exec│Acc  │    │ Activity │
└─────────┘    └─────────┘    └─────────┘    └──────────┘    └────────────────────────────┘    └──────────┘
  Intent           │              ^                                    │                        Deterministic
                   │              │                                    │
            ┌──────┴──────┐       │                                    │
            │  Libraries  │       │                                    │
            │ Templates   │───────┘                                    │
            │ Modules     │                                            │
            │ Prompts     │                                            │
            └─────────────┘          <──── Regenerate on failure ──────┘
```

*Figure 2: The code foundry architecture. Business intent (YAML) enters the fab; validated Temporal activities emerge. The LLM runs once at generation time—not at transaction time.*

**Config Agent.** Receives YAML specifications and orchestrates generation: selecting templates, modules, and compliance constraints.

**Template Library.** Pre-built, tested code templates:
- `SimpleAgent`: Synchronous request-response
- `StreamingAgent`: Chunked data processing
- `ValidatorAgent`: Input validation with fallback
- `BatchAgent`: Bulk processing with checkpointing

**Module Library.** Functional capabilities: `DatabaseModule` (connection pooling), `HTTPModule` (API calls with retries), `NotificationModule` (delivery channels).

**Prompt Blocks.** Reusable prompt fragments encoding domain constraints (HIPAA handling, PCI-DSS rules).

### 3.3 Generation Process

```
Algorithm: Code Foundry Generation Process

Input: Workflow specification S, Template library T, Module library M
Output: Validated Temporal activity A

1.  t ← SelectTemplate(S, T)
2.  m ← SelectModules(S, M)
3.  p ← AssemblePrompt(S, t, m)
4.  code ← LLMGenerate(p)                    // One-time generation
5.  A ← Assemble(t, m, code)
6.  for stage in {Security, Syntax, Execution, Accuracy}:
7.      result ← Validate(A, stage)
8.      if result = FAIL:
9.          code ← Regenerate(p, result.errors)
10.         A ← Assemble(t, m, code)
11. return A                                  // Deterministic artifact
```

### 3.4 Validation Pipeline

**Stage 1: Security.** Static analysis via Bandit, Semgrep, custom rules. Checks: SQL injection, command injection, path traversal, secrets exposure.

**Stage 2: Syntax.** AST parsing, type checking (mypy), linting (ruff). Ensures well-formed, typed code.

**Stage 3: Execution.** Sandboxed execution against test fixtures. Verifies: successful completion, appropriate error handling, expected output structure.

**Stage 4: Accuracy.** Output comparison against golden datasets. Task-specific thresholds.

### 3.5 Bounded Agentic Invocation

Some steps require runtime judgment. Our architecture supports *bounded agentic invocation*: generated code may call LLMs for specific subtasks (e.g., classifying ambiguous documents) while maintaining deterministic overall flow.

Constraints on bounded invocations:
- Defined input/output schemas with validation
- Fallback logic for invalid responses
- Drift monitoring on output distributions
- Human escalation for low-confidence cases

---

## 4. Evaluation Framework for Compiled AI

Existing benchmarks for LLM systems primarily measure task-level capability, such as code correctness or tool-use success rates. While necessary, these metrics are insufficient for evaluating production workflow automation systems, where economic efficiency, determinism, and reliability are often more critical than expressiveness.

We therefore evaluate compiled AI as a systems artifact rather than a reasoning agent. Our framework quantifies token amortization, execution variance, validation convergence, and total cost of ownership, enabling principled comparison with runtime inference approaches.

### 4.1 Token Efficiency Metrics

Token consumption determines the economic viability of compiled vs. runtime approaches.

| Metric | Definition | Interpretation |
|--------|------------|----------------|
| **GenTokens** | Tokens consumed during code generation | One-time upfront cost |
| **RuntimeTokens**(n) | Tokens consumed processing n transactions | Should be ≈ 0 for compiled AI |
| **TotalTokens**(n) | GenTokens + RuntimeTokens(n) | Full cost comparison |
| **BreakEven** | n* where compiled < runtime | ROI threshold |
| **CompressionRatio** | Prompt tokens / Generated LOC | Efficiency of "compilation" |

*Table 2: Token efficiency metrics*

For compiled AI, **RuntimeTokens**(n) = 0 for pure deterministic execution, or **RuntimeTokens**(n) = k · n where k << 1 for bounded agentic invocations. The break-even point:

```
n* = GenTokens_compiled / (RuntimeTokens_per-tx,runtime - RuntimeTokens_per-tx,compiled)
```

### 4.2 Latency Metrics

Enterprise SLAs require predictable response times.

| Metric | Definition | Target (Compiled AI) |
|--------|------------|---------------------|
| **P50Latency** | Median end-to-end latency | < 100ms |
| **P99Latency** | 99th percentile latency | < 500ms |
| **Jitter** | P99 - P50 | < 100ms |
| **ColdStart** | Time to first response | One-time (generation) |

*Table 3: Latency metrics*

Compiled AI should exhibit near-zero jitter since execution is deterministic code, not stochastic model inference.

### 4.3 Consistency and Determinism Metrics

Compliance requirements demand reproducible behavior.

| Metric | Definition | Target |
|--------|------------|--------|
| **OutputVariance** | Entropy of outputs for identical inputs | 0 (deterministic) |
| **Reproducibility** | Same input → same output across runs | 100% |
| **AuditCompleteness** | % of execution paths fully traceable | 100% |
| **TemporalDrift** | Behavior change over time without code changes | 0 |

*Table 4: Consistency metrics*

**Measurement protocol:** Run N=1000 identical inputs through each system. Compute output entropy H = -Σ pᵢ log pᵢ where pᵢ is the frequency of distinct output i. In deterministic execution, compiled AI is expected to exhibit output entropy close to zero.

### 4.4 Reliability Metrics

Production systems require high success rates.

| Metric | Definition | Baseline |
|--------|------------|----------|
| **TaskCompletion** | % transactions successfully processed | Agent: 35% |
| **ErrorRate** | % requiring human intervention | --- |
| **MTBF** | Mean time between failures | --- |
| **RecoveryRate** | % of failures auto-recovered via retry | --- |

*Table 5: Reliability metrics*

The 35% agent success rate from Salesforce provides a baseline. Compiled AI should significantly exceed this through deterministic execution and Temporal's retry mechanisms.

### 4.5 Code Quality Metrics

Generated code must meet production standards.

| Metric | Tool | Target | Human Baseline |
|--------|------|--------|----------------|
| **SecurityScore** | Bandit | 0 high/critical | 0 |
| **TypeCoverage** | mypy | > 90% | ~85% |
| **LintScore** | ruff/pylint | > 8.0/10 | ~8.5 |
| **Complexity** | radon | < 10 cyclomatic | ~8 |
| **TestPassRate** | pytest | 100% | 100% |

*Table 6: Code quality metrics*

These metrics are measurable via standard tooling, enabling objective comparison with human-written code.

### 4.6 Validation Pipeline Metrics

Unique to compiled AI: measuring the effectiveness of the generation-validation loop.

| Metric | Definition |
|--------|------------|
| **FirstPassRate**_stage | % passing stage on first generation attempt |
| **OverallFirstPass** | % passing all stages without regeneration |
| **RegenDistribution** | Distribution of regeneration attempts needed |
| **FailureMode** | Categorization of validation failures |
| **TimeToValid** | Wall-clock time from spec to validated artifact |

*Table 7: Validation pipeline metrics*

This data is novel—no published work reports validation pipeline effectiveness for LLM-generated production code.

### 4.7 Cost Metrics

CFO-level evaluation requires total cost of ownership.

| Metric | Formula |
|--------|---------|
| **CostPerTx**(n) | GenCost/n + RuntimeCostPerTx + InfraCostPerTx |
| **InfraCost** | Temporal cluster + compute + storage |
| **TCO**(n, t) | Total cost for n tx/month over t months |
| **CostRatio** | TCO_compiled / TCO_runtime at scale |

*Table 8: Cost metrics*

At sufficient scale, compiled AI's **CostRatio** should approach the infrastructure-only cost, as inference cost amortizes to near-zero.

### 4.8 Benchmark Suite Summary

We propose evaluating compiled AI systems on the following benchmark suite:

| Category | Primary Metric | Measurement Method |
|----------|---------------|-------------------|
| Token Efficiency | **BreakEven** | Token counting at n ∈ {100, 1K, 10K, 100K} |
| Latency | **P99Latency**, **Jitter** | Distribution over 10K requests |
| Consistency | **OutputVariance** | Entropy over 1K identical inputs |
| Reliability | **TaskCompletion** | Success rate over test suite |
| Code Quality | **SecurityScore** | Static analysis tooling |
| Validation | **OverallFirstPass** | Pipeline instrumentation |
| Cost | **CostRatio** | TCO model at 1M tx/month |

*Table 9: Compiled AI benchmark suite*

---

## 5. Experimental Setup

We evaluate our system using the framework defined in Section 4.

### 5.1 Task Suite

We construct a benchmark of [N] enterprise workflow tasks spanning four categories:

| Category | Example Tasks | Count | Avg. Complexity |
|----------|--------------|-------|-----------------|
| Document Processing | EOB extraction, invoice parsing | [N] | [X] steps |
| Data Transformation | Schema mapping, normalization | [N] | [X] steps |
| Decision Logic | Eligibility, routing, classification | [N] | [X] steps |
| API Orchestration | Multi-system updates, webhooks | [N] | [X] steps |

*Table 10: Task suite composition*

### 5.2 Baselines

We compare against four approaches:

1. **Direct LLM**: Task description sent to LLM per transaction
2. **LangChain**: Equivalent workflow using LangChain abstractions
3. **Multi-agent**: AutoGen-style multi-agent implementation
4. **Human code**: Hand-written Temporal activities (upper bound)

### 5.3 Implementation Details

[Models used (Claude Opus 4.5, GPT-5.2), API versions, infrastructure specs, Temporal cluster configuration]

---

## 6. Results

### 6.1 Token Efficiency

| Method | GenTokens | RuntimeTokens | Total | BreakEven | CompressionRatio |
|--------|-----------|---------------|-------|-----------|------------------|
| Direct LLM | 0 | [X] | [X] | --- | --- |
| LangChain | 0 | [X] | [X] | --- | --- |
| Multi-agent | 0 | [X] | [X] | --- | --- |
| Compiled AI | [X] | [X] | [X] | [N] tx | [X]:1 |

*Table 11: Token consumption per 1,000 transactions*

[Analysis: Break-even typically at N transactions. At 10K+ transactions, compiled AI exhibits X% cost reduction.]

### 6.2 Latency

| Method | P50 | P99 | Jitter | ColdStart |
|--------|-----|-----|--------|-----------|
| Direct LLM | [X] | [X] | [X] | [X] |
| LangChain | [X] | [X] | [X] | [X] |
| Multi-agent | [X] | [X] | [X] | [X] |
| Compiled AI | [X] | [X] | [X] | [X] |
| Human code | [X] | [X] | [X] | N/A |

*Table 12: Latency distribution (milliseconds)*

[Analysis: Compiled AI latency approaches human-written code. Jitter near-zero vs. high variance in runtime approaches.]

### 6.3 Consistency

| Method | OutputVariance (H) | Reproducibility | AuditCompleteness |
|--------|-------------------|-----------------|-------------------|
| Direct LLM | [X] | [X]% | [X]% |
| LangChain | [X] | [X]% | [X]% |
| Multi-agent | [X] | [X]% | [X]% |
| Compiled AI | [0] | [100]% | [100]% |

*Table 13: Consistency metrics (1,000 identical inputs)*

[Analysis: Compiled AI exhibits near-zero output variance. Runtime approaches show non-trivial output variance even for identical inputs.]

### 6.4 Reliability

| Method | TaskCompletion | ErrorRate | RecoveryRate |
|--------|----------------|-----------|--------------|
| Direct LLM | [X]% | [X]% | N/A |
| LangChain | [X]% | [X]% | N/A |
| Multi-agent | 35% (baseline) | [X]% | N/A |
| Compiled AI | [X]% | [X]% | [X]% |
| Human code | [X]% | [X]% | [X]% |

*Table 14: Reliability metrics*

### 6.5 Code Quality

| Source | Security | TypeCov | LintScore | Complexity | TestPass |
|--------|----------|---------|-----------|------------|----------|
| Compiled AI | [X] | [X]% | [X] | [X] | [X]% |
| Human code | 0 | 85% | 8.5 | 8 | 100% |

*Table 15: Code quality metrics for generated artifacts*

### 6.6 Validation Pipeline Effectiveness

| Stage | FirstPassRate | After Regen |
|-------|---------------|-------------|
| Security | [X]% | [X]% |
| Syntax | [X]% | [X]% |
| Execution | [X]% | [X]% |
| Accuracy | [X]% | [X]% |
| **Overall (all stages)** | [X]% | [X]% |

*Table 16: Validation pipeline pass rates*

| Attempts | 0 | 1 | 2 | 3 | 4+ |
|----------|---|---|---|---|-----|
| % of tasks | [X] | [X] | [X] | [X] | [X] |

*Table 17: Regeneration attempt distribution*

### 6.7 Cost Analysis

| Method | Inference | Infrastructure | Total TCO | CostRatio |
|--------|-----------|----------------|-----------|-----------|
| Direct LLM | $[X] | $[X] | $[X] | [X]× |
| LangChain | $[X] | $[X] | $[X] | [X]× |
| Multi-agent | $[X] | $[X] | $[X] | [X]× |
| Compiled AI | $[X] | $[X] | $[X] | 1× |

*Table 18: Total cost of ownership at 1M transactions/month*

---

## 7. Early Deployment Observations

We report preliminary observations from early deployments of our system in healthcare workflow automation. These observations are intended to illustrate feasibility rather than provide statistically rigorous production benchmarks.

### 7.1 Deployment Context

- [N] healthcare organizations
- [M] months of operation
- [X] total transactions processed
- Workflow types: EOB processing, prior authorization, claims adjudication

### 7.2 Preliminary Metrics

[Table: Uptime, error rates, human escalation rates, observed cost differences]

### 7.3 Case Study: [Anonymized Customer]

[Detailed deployment description]

---

## 8. Discussion

We emphasize that compiled AI is not a general replacement for runtime inference. Rather, it represents a complementary design point optimized for well-specified, high-volume workflows where determinism, auditability, and cost predictability are primary concerns.

### 8.1 When Compiled AI Excels

Our approach is well-suited for workflows that are:

- **High-volume**: Amortizing generation cost requires sufficient transactions
- **Well-specified**: Business logic expressible in structured specifications
- **Compliance-sensitive**: Auditability and determinism are requirements
- **Latency-sensitive**: Runtime inference latency is unacceptable

Healthcare administrative workflows exemplify these requirements. Qiu et al. identify administrative workflow automation as a candidate application for LLM-based systems, while regulatory frameworks increasingly emphasize auditability.

### 8.2 When Runtime Inference Excels

Runtime approaches remain appropriate for:

- **Low-volume, high-variance tasks**: Generation cost doesn't amortize
- **Genuinely open-ended problems**: Cannot be reduced to code
- **Rapid prototyping**: Iteration speed matters more than production efficiency

### 8.3 The Constraint Advantage

Constraining generation improves reliability. By limiting LLM output to narrow functions within tested templates, we bound the space of possible errors. The model cannot hallucinate incorrect API calls or database schemas—these come from pre-tested templates.

This trades flexibility for reliability: appropriate for enterprise deployments where predictability matters more than generality.

### 8.4 Relationship to Existing Benchmarks

Our evaluation framework complements existing benchmarks:

- **SWE-Bench**: Measures code generation capability (prerequisite for compiled AI)
- **τ-bench**: Measures tool use (relevant for bounded agentic invocations)
- **Our framework**: Measures production viability (token economics, consistency, reliability)

We argue that capability benchmarks alone are insufficient—production deployment requires the operational metrics we define.

---

## 9. Limitations

**Specification quality.** Our approach assumes users can accurately specify workflows. The "specification problem" remains fundamental—iterative refinement is often necessary.

**Bounded applicability.** Not all workflows reduce to deterministic code. Tasks requiring genuine creativity or adaptation to novel situations may require runtime inference.

**Generation failures.** Despite validation, some specifications fail to produce working code. [Report failure rate.]

**Model dependence.** Generated code quality depends on the underlying LLM. Model updates may change behavior, requiring re-validation.

**Benchmark limitations.** Our proposed framework has not yet been adopted by other systems, limiting cross-system comparability. We release our benchmark suite to encourage adoption.

---

## 10. Conclusion

We studied compiled AI as a systems design point for LLM-based workflow automation, emphasizing validation, determinism, and token amortization over runtime flexibility. Our contributions include:

1. A system architecture constraining generation to narrow functions within validated templates
2. A four-stage generation-and-validation pipeline that converts probabilistic model output into production-ready code artifacts
3. An evaluation framework measuring operational metrics: token amortization, determinism, reliability, validation effectiveness, and cost

[Summarize key empirical findings.]

The approach trades flexibility for determinism, cost efficiency, and auditability—properties relevant for enterprise deployment in well-specified, high-volume workflow regimes. We release our evaluation framework and benchmark suite to enable systematic comparison of compiled and runtime AI approaches.

### Future Work

- Natural language specification (currently YAML)
- Automatic workflow decomposition from high-level intent
- Continuous optimization from execution telemetry
- Formal verification of generated code properties
- Cross-system benchmark adoption

---

## Appendix A: Example Generated Code

```python
# Template: SimpleAgent | Modules: Database, HTTP
# Generated from: eob_processing_v2.yaml
# Validation: PASS (Security, Syntax, Execution, Accuracy)

def process_business_logic(eob_data: dict) -> ProcessedEOB:
    """Extract and validate EOB fields.

    Generated: 2025-12-15 | Tokens: 847 | LOC: 42
    """
    claim_id = eob_data.get("claim_id")
    patient_id = eob_data.get("patient", {}).get("id")

    # Validate required fields
    if not claim_id or not patient_id:
        raise ValidationError("Missing required identifiers")

    # Extract payment information
    payments = []
    for line in eob_data.get("line_items", []):
        payment = Payment(
            service_code=line["code"],
            billed=Decimal(line["billed_amount"]),
            allowed=Decimal(line["allowed_amount"]),
            paid=Decimal(line["paid_amount"]),
            reason_code=line.get("adjustment_reason")
        )
        payments.append(payment)

    # Calculate totals
    total_billed = sum(p.billed for p in payments)
    total_paid = sum(p.paid for p in payments)

    return ProcessedEOB(
        claim_id=claim_id,
        patient_id=patient_id,
        payments=payments,
        total_billed=total_billed,
        total_paid=total_paid,
        processing_date=datetime.utcnow()
    )
```

## Appendix B: Benchmark Suite Specification

We release our benchmark suite at [GitHub URL]. The suite includes:

- [N] workflow specifications (YAML)
- Golden outputs for accuracy validation
- Measurement scripts for all seven metric categories
- Baseline implementations (Direct LLM, LangChain, Multi-agent)

## Appendix C: Healthcare Regulatory Context

As of July 2025, the FDA has authorized over 1,250 AI-enabled medical devices. The Predetermined Change Control Plan (PCCP) guidance enables pre-specified algorithm updates without new submissions.

Our workflow automation systems generally fall outside FDA device jurisdiction (administrative processes, not clinical decisions), but code generation supports regulatory scrutiny: artifacts can be validated, documented, and audited as required by HIPAA and SOC 2.

---

## References

1. Anthropic (2025). Introducing Claude Opus 4.5. Technical report, November 2025.
2. Chen, W., Ma, X., Wang, X., & Cohen, W.W. (2023). Program of Thoughts Prompting. *TMLR*.
3. CrewAI (2024). Framework for orchestrating role-playing autonomous AI agents.
4. Gao, L., et al. (2023). PAL: Program-aided Language Models. *ICML*.
5. Jimenez, C.E., et al. (2024). SWE-bench: Can Language Models Resolve Real-World GitHub Issues? *ICLR*.
6. Karpathy, A. (2017). Software 2.0. *Medium*.
7. LangChain (2022). Harrison Chase.
8. Li, C., et al. (2024). Chain of Code: Reasoning with a Language Model-Augmented Code Emulator. *ICML*.
9. Salesforce (2025). CRMArena-Pro: Holistic Assessment of LLM Agents.
10. Temporal Technologies (2024). Temporal Documentation.
11. Wu, Q., et al. (2024). AutoGen: Enabling Next-Gen LLM Applications. *COLM*.
12. FDA (2025). AI/ML-Enabled Medical Devices.
13. Zhuo, T.Y., et al. (2024). BigCodeBench. *ICLR 2025*.
14. Yao, S., et al. (2024). τ-bench: A Benchmark for Tool-Agent-User Interaction.
15. Cemri, M., et al. (2025). Why Do Multi-Agent LLM Systems Fail?
16. Atil, N., et al. (2024). Non-Determinism of "Deterministic" LLM Settings.
17. Fan, S., et al. (2024). WorkflowLLM.
18. Zeng, J., et al. (2024). FlowMind: Automatic Workflow Generation with LLMs.
19. Patil, M., et al. (2024). spec2code.
20. Dalrymple, D., et al. (2024). Towards Guaranteed Safe AI.
21. Mündler, N., et al. (2025). Type-Constrained Code Generation.
22. Amodei, D. (2025). Conversation with Marc Benioff at Dreamforce 2025.
23. Qiu, S., et al. (2024). LLM-based agentic systems in medicine and healthcare. *Nature Machine Intelligence*.
24. Neupane, A., et al. (2025). Towards a HIPAA Compliant Agentic AI System in Healthcare.
