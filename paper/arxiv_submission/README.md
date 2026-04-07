# arXiv Submission — Compiled AI

## Metadata

| Field              | Value |
|--------------------|-------|
| **Title**          | Compiled AI: Deterministic Code Generation for LLM-Based Workflow Automation |
| **Authors**        | Geert Trooskens, Aaron Karlsberg, Anmol Sharma, Lamara De Brouwer, Max Van Puyvelde, Walter A. De Brouwer |
| **Primary category** | cs.SE (Software Engineering) |
| **Secondary category** | cs.AI (Artificial Intelligence) |
| **Comments**       | 13 pages, 2 figures, 3 tables |
| **License**        | CC BY 4.0 |
| **Code**           | https://github.com/XY-Corp/CompiledAI |

## Abstract

We study compiled AI, a paradigm in which large language models generate executable code artifacts during a compilation phase, after which workflows execute deterministically without further model invocation. This paradigm has antecedents in prior work on declarative pipeline optimization (DSPy) and hybrid neural-symbolic planning (LLM+P); our contribution is a systems-oriented study of its application to high-stakes enterprise workflows, with particular emphasis on healthcare settings where reliability and auditability are paramount.

By constraining generation to narrow business-logic functions embedded in validated templates, compiled AI trades runtime flexibility for predictability, auditability, cost efficiency, and reduced security exposure. We introduce (i) a system architecture for constrained LLM-based code generation, (ii) a four-stage generation-and-validation pipeline that converts probabilistic model output into production-ready code artifacts, and (iii) an evaluation framework measuring operational metrics including token amortization, determinism, reliability, security, and cost.

We evaluate on two task types: function-calling (BFCL, n=400) and document intelligence (DocILE, n=5,680 invoices). On function-calling, compiled AI achieves 96% task completion with zero execution tokens, breaking even with runtime inference at approximately 17 transactions and reducing token consumption by 57x at 1,000 transactions. On document intelligence, our Code Factory variant matches Direct LLM on key field extraction (KILE: 80.0%) while achieving the highest line item recognition accuracy (LIR: 80.4%). Security evaluation across 135 test cases demonstrates 96.7% accuracy on prompt injection detection and 87.5% on static code safety analysis with zero false positives.

## Files

- `compiled_ai.tex` — LaTeX source (submit this to arXiv)
- `compiled_ai.pdf` — Compiled PDF (for reference, do not upload to arXiv)
- `README.md` — This file

## Submission Instructions

1. Go to https://arxiv.org/submit
2. Upload `compiled_ai.tex` only (arXiv compiles from source)
3. Fill in the metadata from the table above
4. Copy the abstract text as-is (1,798 characters, within the 1,920 limit)
5. Submit
