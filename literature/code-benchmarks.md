# LLM Code Generation Benchmarks: Literature Summary (2024-2026)

## Summary Table of Major Benchmarks

| Benchmark | Tasks | Focus | Latest Top Results | Key Limitation |
|-----------|-------|-------|-------------------|----------------|
| **HumanEval** | 164 | Function-level code completion | ~95%+ (saturated) | Ceiling effects, high contamination (8-18% in training data) |
| **SWE-Bench Verified** | 500 | Real GitHub issue resolution | ~72-76% (Claude Opus 4 + tools) | Evidence of memorization, not reasoning |
| **SWE-Bench Pro** | 731 (public) | Contamination-resistant SE tasks | ~23% (GPT-5, Claude Opus 4.1) | New benchmark - needs adoption |
| **BigCodeBench** | 1,140 | Multi-library function calls | ~60% top models | 149 tasks still unsolved by all models |
| **LiveCodeBench** | 500+ (rolling) | Contamination-free (LeetCode/AtCoder/Codeforces) | Dynamic leaderboard | Competition-style ≠ real-world dev |
| **τ-bench** | Retail + Airline domains | Agentic tool-user interaction | <50% (GPT-4o), pass^8 <25% | LLM user simulator may hallucinate |
| **τ²-bench** | 3 domains | Dual-control agentic tasks | New (2025) | Extension of τ-bench |

---

## Key Findings

### 1. Benchmark Saturation (HumanEval Ceiling)
- Stanford AI Index 2025 confirms **HumanEval, GSM8K, MMLU are saturated**
- Top models achieve 95%+ on HumanEval
- HumanEval-T variants show **5-14% drop** in pass@1, indicating data leakage in models

### 2. SWE-Bench Contamination Concerns
- **"The SWE-Bench Illusion"** paper finds models achieve 76% on path identification from issue text alone
- Performance drops to **53% on repos NOT in SWE-Bench** (memorization, not generalization)
- 35% consecutive 5-gram accuracy on SWE-Bench vs 18% on other benchmarks

### 3. Synthetic vs Real-World Gap  
**Critical finding from arXiv:2510.26130:**
> "While LLMs achieve 84-89% correctness on synthetic benchmarks, they attain only **25-34% on real-world class tasks**"

### 4. SWE-Bench Pro Reality Check
- New contamination-resistant benchmark shows **70%+ → 23%** performance drop
- Private codebase subset even harder (~17-18%)
- GPL licensing reduces contamination risk

---

## Key Papers with arXiv Links

### Benchmark Papers
| Paper | arXiv | Year | Key Contribution |
|-------|-------|------|------------------|
| LiveCodeBench: Holistic and Contamination Free Evaluation | [arXiv:2403.07974](https://arxiv.org/abs/2403.07974) | 2024 | Rolling contamination-free benchmark |
| BigCodeBench: Benchmarking Code Generation with Diverse Function Calls | [arXiv:2406.15877](https://arxiv.org/abs/2406.15877) | 2024 | ICLR'25 Oral, 1140 tasks, 139 libraries |
| τ-bench: A Benchmark for Tool-Agent-User Interaction | [arXiv:2406.12045](https://arxiv.org/abs/2406.12045) | 2024 | Agentic benchmark with policy compliance |

### Critique Papers
| Paper | arXiv | Year | Key Finding |
|-------|-------|------|-------------|
| **The SWE-Bench Illusion: When LLMs Remember Instead of Reason** | [arXiv:2506.12286](https://arxiv.org/abs/2506.12286) | 2025 | Evidence of memorization over reasoning |
| Beyond Synthetic Benchmarks: Evaluating LLM Performance on Real-World Class-Level Code | [arXiv:2510.26130](https://arxiv.org/abs/2510.26130) | 2025 | 84-89% synthetic → 25-34% real-world |
| Addressing Data Leakage in HumanEval Using Combinatorial Test Design | [arXiv:2412.01526](https://arxiv.org/abs/2412.01526) | 2024 | HumanEval-T variants reveal contamination |
| On Leakage of Code Generation Evaluation Datasets | [arXiv:2407.07565](https://arxiv.org/abs/2407.07565) | 2024 | Contamination unavoidable at LLM scale |
| Rethinking Benchmark and Contamination for Language Models | [arXiv:2311.04850](https://arxiv.org/abs/2311.04850) | 2023 | 8-18% HumanEval overlap in pre-training |
| Benchmark Data Contamination of LLMs: A Survey | [arXiv:2406.04244](https://arxiv.org/abs/2406.04244) | 2024 | 39.4% average performance drop after decontamination |

### Analysis Papers
| Paper | arXiv | Year | Focus |
|-------|-------|------|-------|
| Where Do LLMs Still Struggle? In-Depth Analysis of Code Generation Benchmarks | [arXiv:2511.04355](https://arxiv.org/abs/2511.04355) | 2025 | BCB-Hard subset analysis |
| AutoCodeBench: LLMs are Automatic Code Benchmark Generators | [arXiv:2508.09101](https://arxiv.org/abs/2508.09101) | 2025 | Multilingual sandbox, reverse synthesis |
| τ²-Bench: Evaluating Conversational Agents in Dual-Control Environment | [arXiv:2506.07982](https://arxiv.org/abs/2506.07982) | 2025 | Extended τ-bench |

---

## Latest Model Results (Jan 2026)

**SWE-Bench Pro Public (contamination-resistant):**
- GPT-5 (Medium): 23.26%
- Claude Opus 4.1: 22.71%
- Claude 4 Sonnet: 17.65%
- Gemini 2.5 Pro: 13.54%
- GPT-4o: 4.92%

**SWE-Bench Verified (with agentic scaffolds):**
- Claude Opus 4 + Tools: ~72-76%
- But concerns about memorization raised

---

## Conclusions

1. **HumanEval is obsolete** for frontier model evaluation due to saturation and contamination
2. **SWE-Bench results may be inflated** by memorization effects (The SWE-Bench Illusion paper)
3. **New contamination-resistant benchmarks** (SWE-Bench Pro, LiveCodeBench) show much lower real performance
4. **Synthetic → real-world gap** is massive: 84-89% vs 25-34%
5. **Agentic benchmarks** (τ-bench) reveal inconsistency issues even in top models
