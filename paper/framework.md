# Evaluation Framework for Compiled AI: Benchmarks, Metrics, and Protocols

**Bottom Line Up Front:** This comprehensive evaluation framework provides specific benchmarks, datasets, metrics, and protocols across seven dimensions needed to empirically validate "Compiled AI" for LLM-based workflow automation. The framework spans **token efficiency** (LLMLingua compression ratios, break-even formulas), **latency** (MLPerf TTFT/TPOT standards), **consistency** (semantic entropy, SelfCheckGPT), **reliability** (AgentBench, τ-Bench), **code quality** (cyclomatic complexity, pass@k), **validation pipelines** (quality gate metrics), and **cost** (TCO frameworks from NVIDIA and academic literature)—plus comparison baselines against LangChain, AutoGen, and CrewAI, and healthcare-specific benchmarks including n2c2/MIMIC datasets and CAQH standards.

---

## Token efficiency demands novel metrics for compiled approaches

For measuring token consumption in one-time code generation versus repeated runtime inference, the field lacks established benchmarks—creating an opportunity for novel contributions.

**Core Metrics:**
| Metric | Formula | Source |
|--------|---------|--------|
| **Compression Ratio** | Output Code Tokens / Input Prompt Tokens | Proposed |
| **LOC per Token** | Lines of Code Generated / Total Tokens Consumed | Proposed |
| **Token Amortization Factor** | Generation_Tokens / Expected_Executions | Proposed |
| **Break-Even Executions** | Generation_Cost / Runtime_Cost_Per_Execution | Pan & Wang 2025 |

**LLMLingua compression research** (Microsoft) establishes baselines: up to **20x compression ratio** with minimal performance loss, and 17.1% performance improvement at 4x compression. The **ENAMEL benchmark** (arXiv 2406.06647) provides the first rigorous efficiency evaluation with the eff@k metric generalizing pass@k from correctness to efficiency.

**Break-even calculations** follow the Pan & Wang framework (arXiv 2509.18101): for small models (24-32B parameters), break-even occurs in **0.3-3 months** at >50M tokens/month; for medium models (70-120B), **2.3-34 months**. For Compiled AI specifically, where generated code execution cost approaches zero, the break-even formula simplifies dramatically: once generation cost is amortized over executions, deterministic code provides **infinite cost advantage**.

**Cost benchmarks** show LLM inference declining **10x per year** (a16z "LLMflation" analysis), with GPT-3 at $60/1M tokens (2021) dropping to equivalent-capability models at $0.06/1M tokens (2024)—a 1,000x reduction.

---

## Latency measurement follows MLPerf standards with percentile reporting

**MLCommons/MLPerf Inference** provides authoritative latency benchmarks with specific constraints for LLMs:

| Metric | Definition | MLPerf Constraint |
|--------|------------|-------------------|
| **TTFT** (Time to First Token) | Request submission to first token generation | 2,000ms for LLAMA2-70B |
| **TPOT** (Time Per Output Token) | Inter-token latency | 200ms (~240 words/minute reading speed) |
| **ITL** | (E2E_latency - TTFT) / (Output_tokens - 1) | Per NVIDIA GenAI-Perf |

**Percentile reporting requirements:** Report P50, P90, P95, and P99 for complete distribution understanding. P99 requires **1,000+ samples** for stable estimation. The **bootstrap percentile method** with B ≥ 1,000 resamples provides 95% confidence intervals.

**Cold start latency** dominates serverless LLM deployments. Per HydraServe research (arXiv:2502.15524), LLAMA2-70B cold start reaches **30-90 seconds** including model fetching (~26s for 130GB from S3 at 5GB/s), GPU memory loading (~2s), and runtime initialization. Warm latency measurement requires excluding warm-up requests and documenting cache state.

**Competitive baselines:**
| Metric | Acceptable | Good | Excellent |
|--------|------------|------|-----------|
| TTFT | <2,000ms | <500ms | <200ms |
| TPOT/ITL | <200ms | <50ms | <10ms |
| Throughput (TPS) | >10 | >100 | >1,000 |

---

## Consistency benchmarks reveal temperature=0 provides no determinism guarantee

**Critical finding:** Testing Qwen3-235B at temperature=0 with 1,000 identical completions produced **80 unique outputs**; the most common occurred only 78 times, with first divergence at token 103 (Thinking Machines Lab, 2025). Root causes include floating-point arithmetic, Mixture-of-Experts routing, GPU parallelism, and tie-breaking.

**Semantic Entropy** (Farquhar et al., Nature 2024) measures uncertainty over meanings rather than tokens: `H_s = -Σ P(g_j) log₂ P(g_j)` where g_j represents semantic groups. Reduction from **3.1 to 1.5 bits** indicates moving from ~8 to ~3 effective choices.

**Reproducibility testing protocol:**
1. Fix all parameters: temperature=0, seed (if available), top_p=1, top_k=0
2. Run N identical inputs (N ≥ 50 minimum; 1,000+ for rigorous testing)
3. Measure exact match rate, BERTScore distribution, token-level divergence point
4. Report: Binary classification achieves ~99% reproducibility; complex generation only 60-80%

**Self-Consistency** (Wang et al., 2022) demonstrates **+17.9% improvement on GSM8K** through majority voting over multiple reasoning paths. **SelfCheckGPT** (EMNLP 2023) provides zero-resource hallucination detection with AUC-PR 0.65-0.80 using N=3 samples.

**Schema conformance benchmarks:** JSONSchemaBench provides ~10,000 real-world schemas. OpenAI's structured outputs achieve **100% schema compliance** in strict mode versus 35% with prompting alone. Model comparison shows Claude 3.5 Sonnet at 100% (simple) / 85-95% (complex), GPT-4o at 100% / 90-100%.

---

## Reliability benchmarks span multi-step workflows and error recovery

**AgentBench** (ICLR 2024) provides the first systematic LLM-as-Agent evaluation across 8 environments: Operating System, Database, Knowledge Graph, Digital Card Game, Lateral Thinking Puzzles, House Holding, Web Shopping, and Web Browsing. GPT-4 shows strong capabilities; open-source models (<70B) exhibit significant performance gaps.

**τ-Bench** (Yao et al., 2024) tests airline domain workflows with 300+ flight entries, 500 synthetic user profiles, 2,000+ bookings, and 50 structured scenarios evaluating policy interpretation, API execution, and consistency.

**CLASSic Framework** (ICLR 2025 Workshop) proposes five-dimensional evaluation:
- **C**ost: API usage, token consumption, infrastructure overhead
- **L**atency: End-to-end response time
- **A**ccuracy: Workflow selection correctness (best: 76.1%)
- **S**tability: Consistency across diverse inputs (domain-specific: 72%)
- **S**ecurity: Resilience to adversarial inputs, prompt injection

**Task completion rate** formula: `TCR = Successfully_completed_tasks / Total_attempted_tasks`. For milestone-based scoring: `Progress = Σ(milestone_weight × milestone_achieved) / Σ milestone_weight`.

**Failure mode categories** to track: tool selection errors, parameter errors, reasoning failures, context loss, timeout/infinite loops. **ToolEmu** safety benchmark provides 36 high-stakes tools with 144 test cases for risk assessment.

---

## Code quality metrics combine established software engineering standards

**Static Analysis Metrics:**
| Metric | Formula/Tool | Good Threshold |
|--------|--------------|----------------|
| **Cyclomatic Complexity** | V(G) = E - N + 2P | <10 per method |
| **Cognitive Complexity** | SonarQube | <15 per function |
| **Halstead Volume** | V = N × log₂(n) | Varies by module |
| **Maintainability Index** | 171 - 5.2×ln(V) - 0.23×G - 16.2×ln(LOC) | >65 (>85 excellent) |
| **Technical Debt Ratio** | Remediation_Cost / Development_Cost | <5% |

**Security scanning benchmarks:** Semgrep baseline precision is **35.7%**; hybrid SAST+LLM approaches achieve **89.5%** precision (91% false positive reduction). SonarQube security ratings: A (0 vulnerabilities) through E (blocker-severity issues).

**Test coverage targets:**
| Metric | Formula | Good Threshold |
|--------|---------|----------------|
| Line Coverage | (executed lines / total) × 100 | ≥80% |
| Branch Coverage | (executed branches / total) × 100 | ≥75% |
| Mutation Score | mutants_killed / (killed + survived) × 100 | >70% |

**Pass@k** remains the primary code generation metric: `pass@k = 1 - C(n-c,k)/C(n,k)`. Current SOTA: HumanEval >90% pass@1 for frontier models; BigCodeBench ~65%; SWE-bench Verified ~72%.

---

## Validation pipeline metrics measure regeneration convergence

**Quality Gate Thresholds:**
```yaml
quality_gate:
  coverage:
    lines: ≥80%
    branches: ≥75%
  complexity:
    method_cognitive: ≤15
    method_cyclomatic: ≤10
  security:
    critical_vulnerabilities: 0
  duplication: <3%
  maintainability_rating: ≥B
```

**Pipeline-specific metrics:**
| Metric | Formula | Competitive Target |
|--------|---------|-------------------|
| First-Pass Rate | (first_attempt_pass / total) × 100 | >70% |
| Mean Regeneration Attempts | Average attempts until valid | <2 |
| Time-to-Valid | Mean(validation_end - submission_time) | Varies |
| False Positive Rate | (false_rejections / total_rejections) × 100 | <10% |

Research finding: ChatGPT achieves satisfactory solutions in **~1.6 attempts** on average (Miah & Zhu, 2024). For multi-stage pipelines: `Cumulative_Pass_Rate = ∏(Stage_Pass_Rate(Si))`.

---

## Cost benchmarks enable TCO comparison against runtime inference

**NVIDIA TCO Framework:**
```
Number_of_Servers = (N_instances × GPUs_per_instance) / GPUs_per_server
Yearly_Server_Cost = (Initial_Cost / Depreciation_Years) + Yearly_Software + Yearly_Hosting
Cost_per_1M_Tokens = (Cost_per_1K_Prompts × 1000) / (ISL + OSL)
```

**Infrastructure costs** (self-hosted): Hardware (GPUs) represents 70-80% of deployment costs. Example: 1x DGX Server = $320,000; 4-year depreciation; minimal deployment = $125,000-$190,000/year.

**Commercial API Pricing (January 2026):**
| Provider/Model | Input ($/1M) | Output ($/1M) |
|----------------|--------------|---------------|
| OpenAI GPT-4o | $2.50 | $10.00 |
| Anthropic Claude 4 Sonnet | $3.00 | $15.00 |
| Google Gemini 2.5 Pro | $1.25 | $10.00 |

**Prompt caching comparison:** Cache hit reduces costs by **81-90%**. Example: 1,000 requests with 10k token context costs $33.15 without caching, $6.18 with caching.

**Compiled AI cost advantage formula:**
```
Determinism_Advantage = Runtime_Inference_Cost × N_executions / Generation_Cost
```
When DA > 1, compiled approach is more efficient. For deterministic code with near-zero runtime cost, **DA approaches infinity** after break-even execution count.

---

## Comparison baselines against LangChain, AutoGen, and CrewAI

**Framework Overhead Comparison (AIMultiple Benchmark, Dec 2025):**
| Framework | Overhead (ms) | Tokens (Travel Planner) | Key Characteristic |
|-----------|---------------|------------------------|-------------------|
| DSPy | 3.53 | 2,030 | Fastest framework |
| Haystack | 5.90 | 1,570 | Most token-efficient |
| LlamaIndex | 6.00 | 1,600 | Best data retrieval |
| LangChain | 10.00 | 3,187 | Heavy memory management |
| LangGraph | 14.00 | 2,589 | Best state handling |
| CrewAI | - | 5,339 | 5s deliberation delay |
| AutoGen | - | 3,316 | Moderate, predictable |

**Benchmark Performance:**
- **AutoGen on GAIA**: #1 accuracy across all three difficulty levels (March 2024), outperforming single-agent solutions by ~8%
- **CrewAI claims**: 5.76x faster than LangGraph for certain QA tasks
- **SWE-Kit (LangGraph)**: 48.6% on SWE-bench (4th overall, 2nd open-source)

**Standard benchmark tasks for comparison:**
| Benchmark | Tasks | Top Performance |
|-----------|-------|-----------------|
| **AgentBench** | 8 environments, 1,014 test | GPT-4 strong; open-source gap |
| **GAIA** | 466 questions, 3 levels | Human 92%; GPT-4 plugins 15%; best AI ~65% |
| **WebArena** | 812 web tasks | ~54.8% (Gemini 2.5 Pro) |
| **SWE-bench** | 2,294 GitHub issues | ~72% Verified (frontier+scaffold) |
| **TaskBench** | Tool graph evaluation | GPT-4 59-71% v-F1 |

---

## Healthcare benchmarks span EOB, prior authorization, and claims

**Prior Authorization Turnaround (CMS-0057-F, effective 2026-2027):**
| Request Type | Required Response |
|--------------|------------------|
| Expedited/Urgent | 72 hours |
| Standard | 7 calendar days |

Current ePA performance: **62% of requests** receive determination within 2 hours; average response time **3 minutes 54 seconds**.

**Claims Adjudication (CAQH Index 2024):**
- Best-in-class auto-adjudication rate: **>85%** without manual intervention
- Top performers: Up to **99%** adjudication quality and payment accuracy
- Manual claim processing cost: $10.13/transaction vs electronic: $2.41/transaction
- Total healthcare administrative spend: ~$90 billion annually; potential savings from full automation: **$20 billion**

**PHI Detection (i2b2 2014 De-identification Challenge):**
| Model | F1-Score |
|-------|----------|
| Transformer-DeID RoBERTa | 0.924 |
| BERT-based systems (challenge winner) | 0.936 |
| DATE category (best PHI type) | 0.976 |

**ICD/CPT Code Prediction:**
| Model | Performance |
|-------|-------------|
| BERT/ClinicalBERT (Top-50 F1) | 0.80-0.81 |
| GPT-4 exact match (ICD-9/10, CPT) | 45.9% / 33.9% / 49.8% |
| GPT-4 equivalent match | 80% / 78% / 83.5% |

**Document OCR benchmarks:** Structured lab reports achieve **95-97%** field-level accuracy; clean printed text **98%+**; complex forms **80-90%**; handwritten text **20-96%** (highly variable).

---

## Recommended datasets span code generation and healthcare

**Tier 1 Essential Datasets:**
| Dataset | Size | Focus | Access |
|---------|------|-------|--------|
| **SWE-bench Verified** | 500 issues | Real-world SE workflows | HuggingFace |
| **BigCodeBench** | 1,140 tasks | Tool composition (139 libraries) | HuggingFace |
| **TaskBench** | Multiple domains | Task automation | Microsoft/HuggingFace |
| **JSONSchemaBench** | ~10,000 schemas | Structured output | EPFL |

**Tier 2 Complementary:**
| Dataset | Size | Focus |
|---------|------|-------|
| **DS-1000** | 1,000 problems | Data science (7 libraries) |
| **InterCode** | 200-1034 tasks | Interactive execution |
| **LiveCodeBench** | 1,055+ problems | Contamination-free |
| **ToolBench** | 16,464 APIs | API workflows |

**Healthcare Datasets:**
| Dataset | Size | Focus | Access |
|---------|------|-------|--------|
| **n2c2/i2b2** | 500-1,300 records per challenge | Clinical NLP gold standard | DBMI Data Portal (DUA) |
| **MIMIC-III** | 40,000+ patients, 2M+ notes | Critical care | PhysioNet |
| **CMS DE-SynPUF** | Synthetic Medicare claims | Claims processing | CMS (free) |
| **SyntheaTM** | Unlimited synthetic patients | Testing | Open source |

---

## What constitutes competitive results across dimensions

| Dimension | Metric | Competitive | Excellent |
|-----------|--------|-------------|-----------|
| **Token Efficiency** | Compression ratio | >4x | >10x |
| **Latency** | TTFT | <500ms | <200ms |
| **Consistency** | Exact match rate (temp=0) | >80% | >95% |
| **Consistency** | BERTScore F1 | >0.85 | >0.95 |
| **Reliability** | Task completion (AgentBench) | >50% | >75% |
| **Code Quality** | pass@1 (HumanEval) | >80% | >90% |
| **Code Quality** | Cyclomatic complexity | <10 | <5 |
| **Validation** | First-pass rate | >70% | >90% |
| **Cost** | Break-even executions | <100 | <10 |
| **Healthcare** | Auto-adjudication rate | >85% | >95% |
| **Healthcare** | PHI detection F1 | >0.92 | >0.95 |

---

## Conclusion: Key evaluation opportunities for Compiled AI

The "Compiled AI" paradigm offers measurable advantages amenable to rigorous evaluation. **Token efficiency** can be demonstrated through break-even analysis where deterministic code execution provides infinite cost advantage after a small number of executions. **Consistency** benchmarks will likely show significant improvement over runtime inference given temperature=0 non-determinism findings. **Latency** comparisons should demonstrate orders-of-magnitude reduction for execution phase versus repeated inference.

Critical gaps exist in the literature: no standard "prompt-to-code compression ratio" metrics, no RPA-specific benchmarks, and no dedicated EOB processing datasets. These represent opportunities for novel contributions. The proposed **Compilation Efficiency Ratio**, **Token Amortization Factor**, and **Determinism Advantage** metrics can become foundational for evaluating compiled versus runtime approaches.

For the strongest empirical validation, combine AgentBench/GAIA for reliability comparison, SWE-bench/BigCodeBench for code quality, JSONSchemaBench for structured output consistency, and the n2c2/MIMIC datasets for healthcare domain validation—while introducing novel token efficiency metrics that capture the fundamental economic advantage of one-time generation over repeated inference.