# Related Work

## 2.1 The Reliability Crisis in LLM Agents

Recent empirical studies reveal a fundamental reliability problem in multi-agent LLM systems. Cemri et al. (2025) analyzed 1,600+ annotated traces across seven major frameworks (MetaGPT, ChatDev, AutoGen), finding that **79% of failures stem from specification and coordination issues**—not infrastructure limitations. This taxonomy identifies specification failures (41.8%) and coordination failures (36.9%) as dominant, with infrastructure accounting for only 16% of issues.

Production deployments confirm this pattern. Salesforce's CRMArena-Pro benchmark shows success rates degrading from 58% (single-turn) to **35% in multi-turn interactions** (Huang et al., 2025). Pan et al. (2025) surveyed 306 practitioners and found that 68% limit agents to ≤10 autonomous steps before requiring human intervention, with reliability cited as the primary challenge.

Critically, non-determinism persists even with temperature=0. Ouyang et al. (2023) demonstrated 18-75% output variance in code generation tasks due to architectural factors (MoE routing, floating-point variance), fundamentally undermining reproducibility in interpreted AI approaches.

## 2.2 Benchmark Saturation and Contamination

The apparent progress on code generation benchmarks masks significant methodological concerns. HumanEval is now saturated (>95% for frontier models), with Stanford's AI Index 2025 formally retiring it for frontier evaluation. More troubling, contamination studies reveal 8-18% of HumanEval appearing in pre-training data (arXiv:2311.04850), with average 39.4% performance drops after decontamination (arXiv:2406.04244).

"The SWE-Bench Illusion" (arXiv:2506.12286) provides striking evidence that models achieve 76% accuracy on path identification from issue text alone, with performance dropping to **53% on repositories outside SWE-Bench**—suggesting memorization rather than generalization. When SWE-Bench Pro introduced contamination-resistant benchmarks, top model performance collapsed from 70%+ to **23%** (GPT-5, Claude Opus 4.1).

The synthetic-to-real gap is even more severe: models achieving 84-89% on synthetic benchmarks attain only **25-34% on real-world class-level tasks** (arXiv:2510.26130). The METR study found developers perceived 20% productivity gains while objective measurements showed **19% slower completion**—directly contradicting adoption narratives.

## 2.3 Constrained Generation and Formal Verification

Structured generation techniques offer a path to reliable outputs. SynCode (Ugare et al., 2024) achieves **96% reduction in syntax errors** through grammar-constrained decoding, while type-constrained decoding (Mündler et al., 2025) reduces compilation errors by >50%. XGrammar (Dong et al., 2024) demonstrates production-viable performance with up to 100x speedup over existing constrained decoding.

Formal verification pipelines show promise for critical systems. Astrogator (Councilman et al., 2025) verifies correct code in 83% of cases and identifies incorrect code in 92% using a Formal Query Language for intent specification. The Guaranteed Safe AI framework (Dalrymple et al., 2024) provides theoretical foundations for verification without requiring interpretability.

However, fundamental limitations remain: "LLMs Will Always Hallucinate" (arXiv:2409.05746) demonstrates that structural hallucinations cannot be eliminated by larger training sets alone, positioning constrained decoding as complementary rather than complete.

## 2.4 The Bitter Lesson Debate

Sutton's "Bitter Lesson" (2019) argues that scale with general methods ultimately wins over hand-crafted approaches. Code Llama's results support this—a 7B code-specialized model outperforms Llama 2 70B on HumanEval/MBPP (Rozière et al., 2023). However, recent work questions whether scale alone is sufficient.

The critical constraint is data, not compute. Scaling laws show C ~ D² (compute scales quadratically with data), but high-quality training data is finite—approximately 10T curated tokens, "and there is no second Internet" (Chakrabarti, 2025). Stockfish demonstrates that purpose-built systems can outperform neural approaches: HRM (27M parameters) beats o3-mini-high on ARC-AGI-1.

Karpathy's "Software 2.0" thesis (2017) correctly predicted neural network dominance in perception tasks, but verification tasks may require hybrid approaches. The METR productivity study and code smell analyses suggest that **scale produces syntactically correct but semantically problematic code**—the gap CompiledAI aims to address.

## 2.5 Compiled vs. Interpreted AI

The most directly relevant work validates the compilation paradigm. DSPy (Khattab et al., 2023) **compiles declarative LLM calls into optimized pipelines**, achieving 25-65% improvements over prompt engineering—small 770M models compiled with DSPy compete with GPT-3.5. This demonstrates that optimization can be amortized: compile once, execute deterministically.

LLM+P (Liu et al., 2023) embodies the paradigm precisely: **LLM translates natural language to PDDL, then a classical planner produces optimal solutions**. LLMs alone fail to produce even feasible plans, but the hybrid approach succeeds—the LLM handles understanding, the solver handles reasoning.

Token economics favor compilation. LATS achieves SOTA results but costs 10-50x one-shot tokens. For repeated execution, compiled workflows amortize: O(compilation) + O(N × 0) versus O(N × one-shot). MetaGPT's SOPs are essentially compiled workflows—deterministic procedures that reduce cascading hallucinations.

AlphaCodium (2024) demonstrates "flow engineering" over prompt engineering: structured multi-stage flows with verification stages improve GPT-4 accuracy from 19% to 44%. WorkflowLLM validates that workflows can be learned one-shot with zero-shot transfer to unseen APIs.

---

## Summary

| Problem | Evidence | CompiledAI Response |
|---------|----------|---------------------|
| Agent unreliability | 79% failures = spec/coordination (Cemri et al.) | Compile intent → deterministic workflows |
| Benchmark contamination | 70% → 23% on clean benchmarks | Evaluate on execution correctness, not generation |
| Non-determinism at t=0 | 18-75% variance (Ouyang et al.) | Remove LLM from execution loop |
| Data wall for scale | C ~ D², no second internet | Leverage formal methods, not just scale |
| Syntax errors | 96% reducible (SynCode) | Constrained generation → verified workflows |

The literature converges on a clear insight: **LLMs excel at understanding intent but fail at reliable execution**. CompiledAI operationalizes this by treating the LLM as a compiler—translating natural language to formal, verifiable workflows that execute without the LLM in the loop.
