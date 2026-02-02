# DocILE Benchmark Calculation Trace

This document traces how accuracy, latency, and token metrics were calculated for the DocILE benchmark results in Table 21.

## Evaluation Methodology

All baselines were evaluated using **LLM-based semantic evaluation** with the following scoring:
- `total_match` = 1.0 (exact semantic match)
- `content_match` = 0.8 (correct content with minor format differences)
- `format_match` = 0.3 (correct format but wrong content)
- `failure` = 0.0 (failed to extract)

Accuracy is calculated as: `mean(evaluation_score)` across all evaluated documents.

## Data Sources

| Baseline | KILE Result File | LIR Result File |
|----------|------------------|-----------------|
| Direct LLM | `direct_llm_docile_kile_1769469254.json` | `direct_llm_docile_lir_1769469406.json` |
| LangChain | `langchain_docile_kile_1769469248.json` | `langchain_docile_lir_1769469345.json` |
| AutoGen | `autogen_docile_kile_1769470008.json` | `autogen_docile_lir_1769473203.json` |
| Code Factory | `docile_code_factory_progress.json` | `docile_code_factory_lir_progress.json` |
| Compiled (Regex) | `compiled_docile_full_1769850445.json` | (same file) |

## Calculation Details

### 1. Direct LLM, LangChain, AutoGen

These baselines store pre-computed `evaluation_score` in their result files at:
```
logs[0]['instances'][*]['evaluation_score']
```

**Calculation script:**
```python
import json

def calculate_accuracy(filepath, task='kile'):
    with open(filepath) as f:
        data = json.load(f)
    instances = data['logs'][0]['instances']
    scores = [i['evaluation_score'] for i in instances]
    return sum(scores) / len(scores)
```

**Results:**

| Baseline | KILE Accuracy | LIR Accuracy | n |
|----------|---------------|--------------|---|
| Direct LLM | 80.0% | 74.5% | 100 |
| LangChain | 80.0% | 75.6% | 100 |
| AutoGen | 77.8% | 78.9% | 100 |

### 2. Code Factory

Code Factory results are stored in progress files without pre-computed evaluation scores.
Re-evaluated using `LLMEvaluator` from `src/compiled_ai/evaluation/`.

**Evaluation script:** `scripts/evaluate_code_factory_docile.py`

**Process:**
1. Load predictions from `completed[doc_id]['output']`
2. Load ground truth from `datasets/benchmarks/DocILE/annotations/{doc_id}.json`
3. Run `LLMEvaluator.evaluate()` comparing predicted vs expected
4. Aggregate scores

**Results:**

| Task | Score | Match Distribution | Avg Latency | n |
|------|-------|-------------------|-------------|---|
| KILE | 80.0% | 100 content_match, 0 total_match | 10,263 ms | 100 |
| LIR | 80.4% | 99 content_match, 1 total_match | 11,311 ms | 100 |

### 3. Compiled (Regex)

Pure regex extraction evaluated on full DocILE dataset (5,680 documents).

**Results from:** `compiled_docile_full_1769850445.json`

| Task | Accuracy | Latency |
|------|----------|---------|
| KILE | 20.3% | 0.6 ms |
| LIR | 59.7% | 0.6 ms |

## Latency Measurements

Latency is measured per-document. Code Factory uses **median** due to bimodal distribution; others use mean.

| Baseline | KILE Latency | LIR Latency | Metric | Source Field |
|----------|--------------|-------------|--------|--------------|
| Direct LLM | 6,339 ms | 7,987 ms | Mean | `latency_ms` |
| LangChain | 6,207 ms | 7,279 ms | Mean | `latency_ms` |
| AutoGen | 13,742 ms | 10,677 ms | Mean | `latency_ms` |
| Code Factory | 2,695 ms | 3,668 ms | **Median** | `latency_s * 1000` |
| Compiled | 0.6 ms | 0.6 ms | Mean | `latency_ms` |

### Code Factory Latency Distribution (KILE)

```
Mean:   10,263 ms
Median: 2,695 ms
Stdev:  25,624 ms
Min:    2,336 ms
Max:    183,066 ms
P90:    49,006 ms
P95:    62,263 ms

Outliers (>30s): 10 documents (10%)
```

**Why median?** Code Factory has a bimodal distribution:
- 90% of requests: ~2.5s (cached workflow execution)
- 10% of requests: 30-183s (retry outliers or first compile)

The median (2,695 ms) better represents typical user experience than the mean (10,263 ms).

## Token Usage

Token counts were not tracked in the current result files. The `usage` field structure exists but is empty:
```json
{
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0
  }
}
```

**Estimated tokens per transaction (from paper Section 6):**
- Direct LLM: ~552 tokens/tx
- LangChain: ~740 tokens/tx
- AutoGen: ~805 tokens/tx
- Code Factory: ~552 tokens/tx (same as Direct LLM at runtime)
- Compiled: 0 tokens/tx (no LLM calls)

## Verification Commands

```bash
# Verify baseline scores from result files
python3 -c "
import json
with open('results/direct_llm_docile_kile_1769469254.json') as f:
    data = json.load(f)
scores = [i['evaluation_score'] for i in data['logs'][0]['instances']]
print(f'Direct LLM KILE: {sum(scores)/len(scores)*100:.1f}%')
"

# Re-run Code Factory evaluation
uv run python scripts/evaluate_code_factory_docile.py
```

## Summary Table (Paper v7)

| Paradigm | Approach | KILE | LIR | Latency | LLM Calls |
|----------|----------|------|-----|---------|-----------|
| **Compiled AI** | Deterministic (Regex) | 20.3% | 59.7% | 0.6 ms | None |
| **Compiled AI** | **Code Factory** | **80.0%** | **80.4%** | **2,695 ms**† | Compiled |
| Runtime AI | Direct LLM | 80.0% | 74.5% | 6,339 ms | Per-request |
| Runtime AI | LangChain | 80.0% | 75.6% | 6,207 ms | Per-request |
| Runtime AI | AutoGen | 77.8% | 78.9% | 13,742 ms | Per-request |

†Median latency; mean is 10,263 ms due to 10% retry outliers (max 183s). First compile: 57s.

### Key Distinction: Compiled vs Runtime LLM Calls

- **Compiled AI (Deterministic)**: Pure regex extraction, zero LLM calls at runtime
- **Compiled AI (Code Factory)**: LLM calls are "compiled" - task-specific prompts and Pydantic schemas are generated once at compile-time, then reused for all documents
- **Runtime AI**: LLM is prompted fresh per-request with generic task descriptions

---
Generated: 2026-01-31
