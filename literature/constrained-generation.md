# Literature Search: Constrained LLM Generation and Formal Verification (2023-2026)

## 1. Type-Constrained Code Generation

### **Mündler et al. (2025) - Type-Constrained Code Generation with Language Models**
- **Source**: arXiv:2504.09246, ETH Zurich
- **Key Innovation**: Introduces type-constrained decoding using prefix automata and inhabitable type search
- **Results**: 
  - Reduces compilation errors by **>50%**
  - Significantly increases functional correctness across code synthesis, translation, and repair
  - Works with models >30B parameters
- **Practical Technique**: Formalizes approach on simply-typed lambda calculus, extends to TypeScript
- **Production-Ready**: Yes - demonstrated on HumanEval and MBPP benchmarks

---

## 2. Grammar-Constrained Decoding

### **SynCode (Ugare et al., 2024) - LLM Generation with Grammar Augmentation**
- **Source**: arXiv:2403.01632, UIUC
- **Key Innovation**: Uses offline-constructed DFA mask store derived from language CFG
- **Results**: 
  - **96.07% reduction** in syntax errors for Python and Go
  - 100% elimination of JSON syntax errors
- **Practical Technique**: Converts grammar to DFA, creates efficient token lookup table at decode time
- **Production-Ready**: Yes - GitHub: `uiuc-focal-lab/syncode`

### **XGrammar (Dong et al., 2024) - Flexible and Efficient Structured Generation**
- **Source**: arXiv:2411.15100, MLC-AI
- **Key Innovation**: Divides vocabulary into context-independent (prechecked) vs context-dependent tokens
- **Results**: **Up to 100x speedup** over existing constrained decoding solutions
- **Practical Technique**: Near-zero overhead structured generation in end-to-end LLM serving
- **Production-Ready**: Yes - PyPI package, supports JSON Schema & Python DSL

### **Grammar-Constrained Decoding (Geng et al., 2023)**
- **Source**: arXiv:2305.13971, EMNLP 2023
- **Key Innovation**: Input-dependent grammars for task-specific output structures
- **Results**: GCD-enhanced LLMs outperform unconstrained LLMs and task-specific finetuned models
- **Practical Use Cases**: Information extraction, entity disambiguation, constituency parsing

---

## 3. Guaranteed Safe AI Framework

### **Dalrymple et al. (2024) - Towards Guaranteed Safe AI**
- **Authors**: Dalrymple, Skalse, Bengio, Russell, Tegmark, Seshia, et al.
- **Key Framework Components**:
  1. **World Model**: Mathematical description of how AI affects the outside world
  2. **Safety Specification**: Mathematical description of acceptable effects
  3. **Verifier**: Provides auditable proof certificates
- **Practical Implication**: Does NOT require interpretability to be solved; provides solution to inner alignment problem
- **Limitation**: Requires sufficiently detailed initial conditions about the world

---

## 4. HIPAA-Compliant Agentic Systems

### **Neupane et al. (2025) - HIPAA Compliant Agentic AI System in Healthcare**
- **Source**: arXiv:2504.17669
- **Key Mechanisms**:
  1. **Attribute-Based Access Control (ABAC)** for granular PHI governance
  2. **Hybrid PHI Sanitization Pipeline**: Regex patterns + BERT-based model to minimize leakage
  3. **Immutable Audit Trails** for compliance verification
- **Production Relevance**: Framework for clinical workflows (report generation, clinical summarization)
- **Practical Technique**: Dynamic, context-aware policy enforcement at runtime

---

## 5. LLM Programming Languages for Constraints

### **LMQL (Beurer-Kellner et al., 2023) - ETH Zurich**
- **Source**: arXiv:2212.06094, PLDI 2023
- **Key Innovation**: Query language combining algorithmic logic with LLM calls
- **Features**:
  - Typed variables for guaranteed output format
  - Eager output constraining
  - Length constraints, stop conditions
- **Practical Technique**: Compiles constraints into efficient inference procedure
- **Production-Ready**: Yes - `lmql.ai`, active development

---

## 6. Structured Generation Tools Landscape

| Tool | Constraint Types | Key Feature |
|------|-----------------|-------------|
| **Outlines** | CFG, Regex, JSON Schema | FSM-based, HuggingFace/VLLM support |
| **Guidance** | CFG, Regex, JSON Schema, Token Forcing | Transformers, LLAMA-CPP compatible |
| **XGrammar** | CFG, JSON Schema | 100x faster, production optimized |
| **SynCode** | CFG (Python, Go, JSON) | 96% syntax error reduction |
| **LMQL** | Regex, programmatic constraints | Full programming language |
| **Instructor** | JSON Schema | Try-Reject-Repeat validation |

---

## 7. Security Analysis of LLM-Generated Code

### **Key Findings (2024-2025 Studies)**
- **12-65%** of generated code snippets violate secure coding standards
- Most common vulnerabilities (CWE-classified):
  - **CWE-20**: Missing input validation (most common)
  - **CWE-89**: SQL injection
  - **CWE-78**: OS command injection
  - **CWE-798**: Hard-coded credentials
  - **CWE-120/787**: Buffer overflows
  - **CWE-22**: Path traversal

### **Novel AI-Native Risks**
1. **Hallucinated dependencies** ("slopsquatting" attack vector)
2. **Dependency explosion** from simple prompts
3. **Architectural drift** - subtle security invariant violations
4. **Stale library suggestions** with known CVEs

---

## 8. Formal Verification Pipelines

### **Astrogator (Councilman et al., 2025) - Formal Verification of LLM-Generated Code**
- **Source**: arXiv:2507.13290
- **Key Innovation**: Formal Query Language for user intent specification
- **Results**: 
  - Verifies correct code in **83%** of cases
  - Identifies incorrect code in **92%** of cases
- **Practical Technique**: Knowledge Base captures system-specific dependencies
- **Domain**: Ansible (system administration, critical systems)

---

## 9. Hallucination Reduction Through Structural Constraints

### **Key Approaches (2024-2025)**
1. **Template-based prompts**: Predefined structures with placeholders - reduces hallucination
2. **Structured Output Generation**: Significantly lower hallucination rates vs baseline
3. **RAG + Intermediate-layer integration**: Cross-attention/adapter fusion with retrieved docs
4. **Constrained decoding**: Eliminates ill-typed/syntactically invalid outputs

### **Fundamental Limitation**
- Paper: "LLMs Will Always Hallucinate" (arXiv:2409.05746)
- **Finding**: Structural hallucinations cannot be eliminated by larger training sets
- **Implication**: Constrained decoding is complementary, not a complete solution

---

## 10. Production-Ready Recommendations

### For **Template-Based Generation**:
→ Use **Outlines** or **XGrammar** for JSON Schema enforcement

### For **Validation Pipelines**:
1. Grammar-constrained decoding (SynCode/XGrammar) for syntax
2. Type-constrained decoding (Mündler et al.) for type safety
3. Static analysis for security (CWE detection)
4. Formal verification (Astrogator-style) for critical paths

### For **Security**:
1. SAST tools on generated code
2. Dependency scanning (hallucinated packages)
3. Secure-by-default prompts

### For **Compliance** (HIPAA/GDPR):
→ Neupane et al. framework: ABAC + PHI sanitization + audit trails

---

## Key Takeaways for Production LLM Code Generation

1. **Constrained decoding eliminates 96%+ syntax errors** - mature technology
2. **Type constraints reduce 50%+ compilation errors** - emerging but practical
3. **Security vulnerabilities remain prevalent** (12-65%) - requires post-generation analysis
4. **Formal verification achieves 83-92% accuracy** - viable for critical systems
5. **Hallucination is fundamental** - structural constraints mitigate but don't eliminate
