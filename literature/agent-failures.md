# Multi-Agent LLM System Failures: Literature Review (2023-2026)

## Failure Mode Taxonomy (MAST Framework)

Based primarily on **Cemri et al. (2025)** who analyzed 1600+ annotated traces across 7 MAS frameworks (MetaGPT, ChatDev, HyperAgent, AppWorld, AG2/AutoGen, and others), the **Multi-Agent System Failure Taxonomy (MAST)** identifies **14 unique failure modes** clustered into **3 categories**:

### Category 1: Specification & System Design Failures (41.77%)
The largest failure category — nearly half of all failures stem from how agents are specified, not technical implementation.

| Failure Mode | Description |
|-------------|-------------|
| Role Ambiguity | Unclear agent responsibilities causing overlap or gaps |
| Unclear Task Definition | Vague objectives leading to misinterpretation |
| Missing Constraints | Unspecified boundaries/guardrails for agent behavior |
| Incomplete Context | Insufficient information passed to agents |

### Category 2: Inter-Agent Coordination Failures (36.94%)
Communication and synchronization breakdowns between collaborating agents.

| Failure Mode | Description |
|-------------|-------------|
| Communication Breakdown | Agents fail to convey critical information |
| State Synchronization Issues | Inconsistent shared state across agents |
| Conflicting Objectives | Agents working at cross-purposes |
| Context Loss at Handoffs | Information lost when transferring between agents |

### Category 3: Task Verification & Termination (21.30%)
Failures in validating work and knowing when to stop.

| Failure Mode | Description |
|-------------|-------------|
| Premature Termination | Stopping before task completion |
| Infinite Loops | Agents cycling without progress |
| Inadequate Testing | Insufficient output validation |
| Missing Validation Mechanisms | No verification of correctness |

**Key insight:** **~79% of failures are specification + coordination issues**, not infrastructure problems (~16%).

---

## Key Statistics

### Production Success Rates

| Study/Benchmark | Finding |
|----------------|---------|
| **Salesforce CRMArena-Pro (2025)** | 58% single-turn success → **35% multi-turn success** (65% failure rate) |
| **ChatDev with GPT-4o** | As low as **25% correctness** on coding tasks |
| **SWE-bench agents** | Early systems: 12-14% resolution; Current SOTA: ~40-43% |
| **Production survey (Pan et al., 2025)** | 68% of agents execute ≤10 steps before human intervention |

### Non-Determinism at Temperature=0

| Study | Finding |
|-------|---------|
| **Ouyang et al. (2023)** | 18-75% of code tasks show non-equal outputs even at temp=0 |
| **GPT-4 architecture analysis** | Non-determinism caused by Sparse MoE (Mixture of Experts) routing |
| **OpenAI documentation** | "Chat Completions are non-deterministic by default" |

### Framework-Specific Failure Rates

| Framework | Failure Rate Range |
|-----------|-------------------|
| Multi-Agent Systems (general) | **41-86.7%** in production |
| Enterprise AI agents overall | **~70% project failure rate** (TechAhead) |

---

## Detailed Failure Taxonomies from Other Studies

### AgentErrorTaxonomy (Zhu et al., 2025)
Five-module classification:
- **Memory:** False memory, oversimplification
- **Reflection:** Causal misattribution, outcome misinterpretation  
- **Planning:** Constraint ignorance, inefficient planning
- **Action:** Parameter errors, format errors
- **System:** Tool execution failures, environment errors

### AgentAsk Edge-Level Taxonomy (2026)
Four dominant inter-agent error types:
- **Data Gap:** Missing information transfer
- **Signal Corruption:** Distorted messages between agents
- **Referential Drift:** Losing track of what's being discussed
- **Capability Gap:** Agent lacks skills for assigned task

---

## Production Deployment Insights

From **Pan et al. (2025) "Measuring Agents in Production"** — survey of 306 practitioners + 20 case studies:

- **70%** rely on prompting off-the-shelf models (no fine-tuning)
- **74%** depend primarily on human evaluation (not automated)
- **68%** limit agents to ≤10 steps before human intervention
- **#1 challenge:** Reliability — ensuring and evaluating agent correctness

---

## Paper References with Links

### Core Failure Studies

1. **Cemri et al. (2025)** - "Why Do Multi-Agent LLM Systems Fail?"
   - 🔗 [arXiv:2503.13657](https://arxiv.org/abs/2503.13657)
   - DOI: 10.48550/arXiv.2503.13657
   - *First comprehensive MAS failure taxonomy (MAST), 1600+ annotated traces, 7 frameworks*

2. **Zhu et al. (2025)** - "Where LLM Agents Fail and How They Can Learn From Failures"
   - 🔗 [arXiv:2509.25370](https://arxiv.org/abs/2509.25370)
   - DOI: 10.48550/arXiv.2509.25370
   - *AgentErrorTaxonomy, AgentErrorBench, AgentDebug framework*

3. **Zhang et al. (2025)** - "Which Agent Causes Task Failures and When?"
   - 🔗 [arXiv:2505.00212](https://arxiv.org/abs/2505.00212)
   - DOI: 10.48550/arXiv.2505.00212
   - *Who&When dataset: 127 MAS systems with failure attribution annotations*

### Enterprise/Production Studies

4. **Huang et al. (2025)** - "CRMArena-Pro: Holistic Assessment of LLM Agents"
   - 🔗 [arXiv:2505.18878](https://arxiv.org/abs/2505.18878)
   - DOI: 10.48550/arXiv.2505.18878
   - *Salesforce benchmark: 58%→35% success rate degradation in multi-turn*

5. **Pan et al. (2025)** - "Measuring Agents in Production"
   - 🔗 [arXiv:2512.04123](https://arxiv.org/abs/2512.04123)
   - DOI: 10.48550/arXiv.2512.04123
   - *First large-scale study: 306 practitioners, 26 domains*

### Non-Determinism Studies

6. **Ouyang et al. (2023/2024)** - "An Empirical Study of the Non-determinism of ChatGPT in Code Generation"
   - 🔗 [arXiv:2308.02828](https://arxiv.org/abs/2308.02828)
   - DOI: 10.1145/3697010 (ACM published)
   - *Demonstrates 18-75% non-determinism even at temperature=0*

### Resilience & Byzantine Fault Tolerance

7. **Huang et al. (2024/2025)** - "On the Resilience of LLM-Based Multi-Agent Collaboration with Faulty Agents"
   - 🔗 [arXiv:2408.00989](https://arxiv.org/abs/2408.00989)
   - *Studies collaboration degradation with faulty agents*

8. **(2025)** - "Rethinking the Reliability of Multi-agent System: A Perspective from Byzantine Fault Tolerance"
   - 🔗 [arXiv:2511.10400](https://arxiv.org/abs/2511.10400)
   - *CP-WBFT achieves 85.7% fault rate tolerance*

---

## Key Takeaways

1. **Specification > Infrastructure**: Nearly 80% of failures come from unclear specifications and coordination issues, not technical problems

2. **Multi-turn is hard**: Performance degrades 40-65% when moving from single-turn to multi-turn interactions

3. **Non-determinism is inherent**: Even at temperature=0, LLMs are non-deterministic due to architecture (MoE routing, floating-point variance)

4. **Human oversight required**: Production deployments limit agent autonomy to ~10 steps and rely heavily on human evaluation

5. **Cascading failures dominate**: A single root-cause error propagates through subsequent decisions, compounding impact
