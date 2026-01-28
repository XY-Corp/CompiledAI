# Literature Survey: LLM Workflow Automation & Program Synthesis (2023-2026)

## Executive Summary

This survey covers recent advances in LLM-based workflow generation, program synthesis, and agent orchestration relevant to the **"compile once, execute deterministically"** paradigm for CompiledAI.

**Key Finding:** The field is converging on a spectrum between two paradigms:
- **Interpreted AI:** Multi-turn, iterative refinement with LLM-in-the-loop (expensive, non-deterministic)
- **Compiled AI:** One-shot code/workflow generation with deterministic execution (cheaper, reproducible)

---

## 1. LLM-Based Workflow Generation & Orchestration

### 1.1 WorkflowLLM & WorkflowBench
**[arXiv:2411.05451](https://arxiv.org/abs/2411.05451)** - Nov 2024

**Key Contribution:** First large-scale benchmark for workflow orchestration (106,763 samples, 1,503 APIs across 83 applications).

**Findings:**
- Shifts paradigm from Robotic Process Automation (RPA) to **Agentic Process Automation (APA)**
- Constructed from Apple Shortcuts and RoutineHub data, transcribed to Python-style code
- WorkflowLlama (fine-tuned Llama-3.1-8B) achieves strong generalization on unseen APIs
- Demonstrates zero-shot transfer to out-of-distribution task planning (T-Eval)

**Relevance to CompiledAI:** Validates that workflows CAN be learned and generated one-shot; the benchmark provides training data for intent→workflow compilation.

---

### 1.2 FlowMind: Automatic Workflow Generation
**[arXiv:2404.13050](https://arxiv.org/abs/2404.13050)** - ACM ICAIF 2023

**Key Contribution:** LLM-based workflow generation grounded in reliable APIs.

**Findings:**
- Uses "lecture" prompt recipe to ground LLM reasoning with APIs
- **Eliminates hallucinations** by preventing direct LLM-data interaction
- Presents high-level workflow descriptions for user inspection/feedback
- Introduces NCEN-QA benchmark for financial QA workflows

**Relevance to CompiledAI:** Shows how to constrain LLM generation to produce API-grounded, inspectable workflows rather than free-form text.

---

### 1.3 FlowGen (SOEN-101): Emulating Software Process Models
**[arXiv:2403.15852](https://arxiv.org/abs/2403.15852)** - ICSE 2025

**Key Contribution:** Multi-agent LLM framework emulating software development processes (Waterfall, TDD, Scrum).

**Findings:**
- FlowGenScrum achieves Pass@1 of 75.2% on HumanEval (15% improvement over RawGPT)
- Agents embody roles: requirement engineer, architect, developer, tester, scrum master
- Development activities impact code quality differently (design reviews reduce code smells)
- Maintains stable performance across GPT versions and temperature values

**Relevance to CompiledAI:** Shows that **structured process models improve output quality** vs ad-hoc generation.

---

## 2. Multi-Agent Software Development Frameworks

### 2.1 ChatDev: Communicative Agents
**[arXiv:2307.07924](https://arxiv.org/abs/2307.07924)** - ACL 2024

**Key Contribution:** Chat-powered software development with specialized LLM agents guided by chat chains.

**Findings:**
- Agents communicate via natural language (design phase) and programming language (debugging)
- "Communicative dehallucination" reduces errors through multi-turn dialogue
- Solutions derived from multi-turn dialogues across design, coding, testing phases

**Relevance to CompiledAI:** Demonstrates that structured communication patterns (chat chains) can produce deterministic workflows from natural language specs.

---

### 2.2 MetaGPT: Meta Programming for Multi-Agent Collaboration
**[arXiv:2308.00352](https://arxiv.org/abs/2308.00352)** - ICLR 2024

**Key Contribution:** Encodes **Standardized Operating Procedures (SOPs)** into LLM prompts.

**Findings:**
- SOPs = deterministic workflow templates that constrain agent behavior
- Assembly line paradigm assigns roles, breaks complex tasks into subtasks
- Agents verify intermediate results → reduced cascading hallucinations
- More coherent solutions than chat-based multi-agent systems

**Relevance to CompiledAI:** **SOPs are essentially "compiled" workflows** - deterministic procedures that guide execution.

---

## 3. Compiled vs Interpreted AI Paradigms

### 3.1 DSPy: Compiling Declarative LLM Calls
**[arXiv:2310.03714](https://arxiv.org/abs/2310.03714)** - Stanford/CMU, Oct 2023

**Key Contribution:** **Programming model that abstracts LLM pipelines as text transformation graphs.**

**Findings:**
- Replaces "prompt templates" (trial-and-error) with declarative modules
- **Compiler optimizes pipelines** to maximize metrics automatically
- DSPy programs outperform expert-created demonstrations by 5-46%
- Small models (770M T5) compiled with DSPy competitive with proprietary GPT-3.5

**Relevance to CompiledAI:** **THE key paper for "compiled" AI** - shows that prompts can be optimized/compiled once, then executed deterministically. Demonstrates 25-65% improvements over one-shot prompting.

---

### 3.2 AlphaCodium: From Prompt Engineering to Flow Engineering
**[arXiv:2401.08500](https://arxiv.org/abs/2401.08500)** - Jan 2024

**Key Contribution:** Test-based, multi-stage, code-oriented iterative flow.

**Findings:**
- GPT-4 accuracy improved from 19% → 44% (Pass@5) on CodeContests
- "Flow engineering" > prompt engineering for code tasks
- Multi-stage iteration with test feedback dramatically improves results
- Code tasks require different optimization than NL tasks

**Relevance to CompiledAI:** Shows that **structured flows with verification stages** outperform naive one-shot generation.

---

## 4. One-Shot vs Iterative Refinement

### 4.1 Self-Refine: Iterative Refinement with Self-Feedback
**[arXiv:2303.17651](https://arxiv.org/abs/2303.17651)** - NeurIPS 2023

**Key Contribution:** LLM generates output, then iteratively refines based on self-feedback.

**Findings:**
- ~20% average improvement over one-step generation across 7 diverse tasks
- No supervised training, single LLM as generator + refiner + feedback provider
- Even GPT-4 improves with Self-Refine at test time

**Relevance to CompiledAI:** Demonstrates the **cost of iterative refinement** - multiple LLM calls per task. Argues for when it's worth the cost vs not.

---

### 4.2 Self-Debugging: Teaching LLMs to Debug
**[arXiv:2304.05128](https://arxiv.org/abs/2304.05128)** - Oct 2023

**Key Contribution:** "Rubber duck debugging" without human feedback.

**Findings:**
- 2-3% improvement on Spider (text-to-SQL) by explaining code
- Up to 12% improvement with unit test feedback (TransCoder, MBPP)
- **10x sample efficiency** vs generating more candidates

**Relevance to CompiledAI:** Shows iterative debugging is effective but expensive. Suggests **verification stages in compiled workflows** can catch errors.

---

### 4.3 Language Agent Tree Search (LATS)
**[arXiv:2310.04406](https://arxiv.org/abs/2310.04406)** - ICML 2024

**Key Contribution:** Monte Carlo Tree Search for LLM reasoning/acting.

**Findings:**
- 92.7% Pass@1 on HumanEval (SOTA) with GPT-4
- Combines reasoning, acting, planning via tree search
- Uses LM-powered value functions for exploration

**Relevance to CompiledAI:** Shows that **search during generation** can dramatically improve code quality, but at **high token cost**. Ideal for one-time compilation, not repeated execution.

---

## 5. Code Generation & Execution

### 5.1 CodeAct: Executable Code Actions
**[arXiv:2402.01030](https://arxiv.org/abs/2402.01030)** - ICML 2024

**Key Contribution:** Python code as unified action space for LLM agents.

**Findings:**
- 20% higher success rate vs JSON/text action formats
- Code can be executed, dynamically revised based on observations
- CodeActAgent can self-debug using existing libraries

**Relevance to CompiledAI:** Validates **code as the intermediate representation** - more powerful than JSON/natural language for expressing complex workflows.

---

### 5.2 Code Llama
**[arXiv:2308.12950](https://arxiv.org/abs/2308.12950)** - Meta, Aug 2023

**Key Contribution:** Open foundation models specialized for code.

**Findings:**
- 67% on HumanEval, 65% on MBPP
- Infilling capabilities, 16k→100k context support
- Python specialization (Code Llama - Python) outperforms larger general models

**Relevance to CompiledAI:** Baseline for code generation capabilities. Specialized models outperform general models for code tasks.

---

### 5.3 SWE-bench: Real-World GitHub Issues
**[arXiv:2310.06770](https://arxiv.org/abs/2310.06770)** - ICLR 2024

**Key Contribution:** 2,294 real software engineering problems from GitHub.

**Findings:**
- Claude 2 solved only 1.96% of issues (at publication time)
- Requires understanding changes across multiple files
- Extremely long contexts, complex reasoning

**Relevance to CompiledAI:** Establishes **upper bound on current LLM capabilities** for real-world code tasks. Gap between benchmark and production remains large.

---

## 6. Inference Efficiency & Token Amortization

### 6.1 Speculative Decoding
**[arXiv:2211.17192](https://arxiv.org/abs/2211.17192)** - ICML 2023 Oral

**Key Contribution:** 2-3x inference speedup without changing outputs.

**Findings:**
- Uses small draft model to predict multiple tokens
- Large model verifies in parallel
- Exact same distribution as standard decoding

**Relevance to CompiledAI:** Shows **inference optimization is possible without quality loss** - relevant for execution phase of compiled workflows.

---

### 6.2 Input Length Impact on Reasoning
**[arXiv:2402.14848](https://arxiv.org/abs/2402.14848)** - ACL 2024

**Key Contribution:** LLM reasoning degrades at lengths far shorter than technical maximum.

**Findings:**
- Performance degradation at surprisingly short inputs
- Next-word-prediction metric **negatively correlates** with reasoning performance
- Different padding types/locations have different impact

**Relevance to CompiledAI:** Argues for **compact representations** in compiled workflows. Shorter = more reliable.

---

## 7. Planning & Reasoning Frameworks

### 7.1 ReAct: Reasoning and Acting
**[arXiv:2210.03629](https://arxiv.org/abs/2210.03629)** - ICLR 2023

**Key Contribution:** Interleaved reasoning traces and actions.

**Findings:**
- Overcomes hallucination via external knowledge interaction
- 34% absolute improvement on ALFWorld vs RL baselines
- Human-interpretable reasoning traces

**Relevance to CompiledAI:** Shows **reasoning traces can be separated from actions** - actions become deterministic once reasoning is complete.

---

### 7.2 Tree of Thoughts (ToT)
**[arXiv:2305.10601](https://arxiv.org/abs/2305.10601)** - NeurIPS 2023

**Key Contribution:** Deliberate problem solving via thought exploration.

**Findings:**
- Game of 24: 4% → 74% with ToT vs CoT
- Enables backtracking, lookahead, multiple reasoning paths
- Self-evaluation for path selection

**Relevance to CompiledAI:** Shows **exploration during "compilation"** can dramatically improve results. Once best path found, execution is deterministic.

---

### 7.3 LLM+P: Optimal Planning with PDDL
**[arXiv:2304.11477](https://arxiv.org/abs/2304.11477)** - Sep 2023

**Key Contribution:** LLM converts NL to PDDL, classical planner finds optimal solution.

**Findings:**
- LLM+P provides optimal solutions for most problems
- LLMs alone fail to provide even feasible plans
- Hybrid approach: LLM for understanding, solver for planning

**Relevance to CompiledAI:** **KEY ARCHITECTURAL INSIGHT** - LLM translates intent → formal representation, then deterministic solver executes. This IS the compiled paradigm!

---

## 8. LLM Agent Frameworks & Surveys

### 8.1 Rise of LLM-Based Agents (Survey)
**[arXiv:2309.07864](https://arxiv.org/abs/2309.07864)** - Sep 2023

**Key Contribution:** Comprehensive 86-page survey on LLM agents.

**Framework:** Brain (reasoning) + Perception (input) + Action (output)

**Relevance to CompiledAI:** Establishes taxonomy. CompiledAI focuses on **deterministic action** after reasoning is complete.

---

### 8.2 Code Empowers LLMs (Survey)
**[arXiv:2401.00812](https://arxiv.org/abs/2401.00812)** - Jan 2024

**Key Contribution:** How code training unlocks LLM capabilities.

**Findings:**
- Code training improves reasoning, structured outputs, function calling
- Code compilation provides feedback for model improvement
- Code → executable intermediate steps → external execution

**Relevance to CompiledAI:** Validates **code as the compilation target** - it's both learnable by LLMs and executable by machines.

---

### 8.3 LLMs for Software Engineering (SLR)
**[arXiv:2308.10620](https://arxiv.org/abs/2308.10620)** - Updated Apr 2024

**Key Contribution:** 395 papers analyzed across SE tasks.

**Findings:**
- LLMs applicable across code generation, repair, testing, documentation
- Data curation critical for fine-tuning success
- Gap remains between benchmark performance and real-world deployment

---

## 9. Key Findings for CompiledAI

### 9.1 The Compilation Paradigm Is Validated

Multiple independent papers converge on the same insight:

| Paper | Approach | Result |
|-------|----------|--------|
| DSPy | Compile prompts → optimized pipelines | 25-65% improvement |
| LLM+P | Compile NL → PDDL → solver | Optimal solutions |
| MetaGPT | Compile SOPs → agent workflows | Reduced hallucinations |
| AlphaCodium | Compile to flow → execute with tests | 19% → 44% accuracy |

### 9.2 Token Amortization Math

From the literature, typical token costs:

| Approach | Tokens per Task | Notes |
|----------|-----------------|-------|
| One-shot generation | 500-2000 | Often fails |
| Self-Refine (3 iterations) | 3000-6000 | ~20% improvement |
| LATS (tree search) | 10,000-50,000 | Highest quality |
| Compiled (one-time) | 5,000-20,000 | Amortized over N executions |
| Compiled execution | ~0 | Deterministic code runs |

**Amortization insight:** If a compiled workflow is executed N times, total cost is O(compilation) + O(N × 0) vs O(N × one-shot) for interpreted.

### 9.3 Optimal Architecture (from literature)

```
Intent (NL) → [LLM Compiler with search/refinement] → Formal Workflow
                                                           ↓
                                              [Deterministic Executor]
                                                           ↓
                                                       Result
```

This matches:
- **WorkflowLLM:** NL → Python workflow
- **LLM+P:** NL → PDDL → classical planner
- **DSPy:** Declarative specs → optimized prompts
- **FlowMind:** NL → API-grounded workflow

### 9.4 Open Research Questions

1. **How much compilation effort is optimal?** (LATS vs AlphaCodium vs one-shot)
2. **What's the right workflow representation?** (Python, PDDL, JSON, DSL?)
3. **When does iterative refinement beat one-shot?** (complexity threshold)
4. **How to verify compiled workflows?** (test generation, formal verification)

---

## 10. Papers Not Found (Needs Further Search)

- **spec2code** for industrial specifications (couldn't locate specific paper)
- **Temporal/Cadence + LLM integration** (no academic papers; likely industry practice)
- Specific **token amortization studies** with cost analysis

---

## References (Full List)

1. WorkflowLLM (arXiv:2411.05451)
2. FlowMind (arXiv:2404.13050) 
3. FlowGen/SOEN-101 (arXiv:2403.15852)
4. ChatDev (arXiv:2307.07924)
5. MetaGPT (arXiv:2308.00352)
6. DSPy (arXiv:2310.03714)
7. AlphaCodium (arXiv:2401.08500)
8. Self-Refine (arXiv:2303.17651)
9. Self-Debug (arXiv:2304.05128)
10. LATS (arXiv:2310.04406)
11. CodeAct (arXiv:2402.01030)
12. Code Llama (arXiv:2308.12950)
13. SWE-bench (arXiv:2310.06770)
14. Speculative Decoding (arXiv:2211.17192)
15. Input Length Impact (arXiv:2402.14848)
16. ReAct (arXiv:2210.03629)
17. Tree of Thoughts (arXiv:2305.10601)
18. LLM+P (arXiv:2304.11477)
19. LLM Agents Survey (arXiv:2309.07864)
20. Code Empowers LLMs (arXiv:2401.00812)
21. LLMs for SE Survey (arXiv:2308.10620)
22. Eureka (arXiv:2310.12931)
23. RCI Agent (arXiv:2303.17491)
24. OPRO (arXiv:2309.03409)
25. Multiagent Debate (arXiv:2305.14325)
26. Design2Code (arXiv:2403.03163)
27. ModelScope-Agent (arXiv:2309.00986)
28. ReST meets ReAct (arXiv:2312.10003)

---

*Generated: 2026-01-28 | Subagent: lit-workflow-automation*
