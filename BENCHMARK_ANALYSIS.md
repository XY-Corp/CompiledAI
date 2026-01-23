# BFCL Benchmark Analysis: Direct LLM vs Code Factory

**Date**: January 23, 2026
**Dataset**: Berkeley Function Calling Leaderboard (BFCL) - Simple Category
**Model**: Claude Opus 4.5 (`claude-opus-4-5-20251101`)
**Instances**: 100

---

## Executive Summary

| Metric | Direct LLM | Code Factory | Advantage |
|--------|-----------|--------------|-----------|
| **Success Rate** | 95% (95/100) | 99% (99/100) | **Code Factory +4%** |
| **Accuracy** | 5 failures | 1 failure | **Code Factory** |
| **Duration** | 11 minutes | 115 minutes | **Direct LLM 10.4x faster** |
| **Total Tokens** | 53,974 | 2,765,827 | **Direct LLM 51x cheaper** |
| **Avg Latency/Instance** | 4.2s | 66.8s | **Direct LLM 15.8x faster** |

### Key Finding
**Code Factory achieves higher accuracy (99% vs 95%) but at a massive cost in tokens (51x) and time (10x)**. The compilation phase dominates costs, requiring ~36,746 runs to break even.

---

## 1. Success Rate & Accuracy

### Code Factory: 99% Success (99/100)
- **Only 1 failure** (`simple_62` - DNA sequence analysis)
- Failed due to empty sequence extraction in generated code
- Format was correct, but content extraction failed

### Direct LLM: 95% Success (95/100)
- **5 failures** (all format mismatches, score 0.3)
- All had correct function names and parameters
- Failed due to output format variations:
  - Wrapped in `{"name": "...", "parameters": {...}}` structure
  - Included conversational text or XML function calls
  - Missing optional parameters (e.g., gravity default)

### Analysis
Code Factory's **4% accuracy advantage** comes from:
1. **Deterministic code generation**: No format variations once compiled
2. **Validation during compilation**: Workflows tested before execution
3. **Structured output enforcement**: Generated code always returns correct format

Direct LLM failures were **minor format issues** where the model understood the task correctly but didn't match the exact output structure.

---

## 2. Token Efficiency

### Overall Token Comparison

| Metric | Direct LLM | Code Factory | Ratio |
|--------|-----------|--------------|-------|
| **Total Tokens** | 53,974 | 2,765,827 | **51.2x** |
| Input Tokens | 35,173 | 2,276,393 | 64.7x |
| Output Tokens | 18,801 | 489,434 | 26.0x |
| **Tokens/Instance** | 540 | 27,658 | 51.2x |

### Code Factory Token Breakdown

```
Compilation Phase (One-Time):
  Input:  2,232,604 tokens (82.1% of total input)
  Output:   486,590 tokens (99.4% of total output)
  Total:  2,719,194 tokens (98.3% of all tokens)

Execution Phase (Per-Instance):
  Input:     43,789 tokens (1.6% of total input)
  Output:     2,844 tokens (0.6% of total output)
  Total:     46,633 tokens (1.7% of all tokens)
  Avg/Instance: 466 tokens
```

### Key Insight
**98.3% of Code Factory tokens go to compilation**, not execution. The execution phase uses only **466 tokens/instance** (86% cheaper than Direct LLM's 540 tokens).

---

## 3. Latency Analysis

### Duration Breakdown

| Phase | Direct LLM | Code Factory | Ratio |
|-------|-----------|--------------|-------|
| **Total Duration** | 662.5s (11m) | 6,875.2s (115m) | **10.4x** |
| **Avg Latency/Instance** | 4,224ms | 66,768ms | **15.8x** |

### Code Factory Latency Breakdown

```
Per Instance Average:
  Compilation:  64,783ms (97.0% of latency)
  Execution:     1,983ms (3.0% of latency)
  Total:        66,768ms
```

### Analysis
- Direct LLM: Single API call per instance (~4s)
- Code Factory: Multi-agent compilation (Planner → Coder → Validation) takes ~65s per workflow
- **Execution is fast** (2s), but compilation overhead dominates

---

## 4. Amortization Analysis

### When Does Code Factory Break Even?

Given:
- **Compilation cost**: 2,719,194 tokens (one-time)
- **Execution cost**: 466 tokens/run
- **Direct LLM cost**: 540 tokens/run
- **Savings per run**: 74 tokens

```
Break-even point: 2,719,194 / (540 - 466) = 36,746 runs
```

### Cost at Different Scales

| Runs | Code Factory | Direct LLM | Savings | Break-even? |
|------|-------------|-----------|---------|-------------|
| 1 | 2,719,660 | 540 | -2,719,120 | ❌ |
| 10 | 2,723,854 | 5,400 | -2,718,454 | ❌ |
| 100 | 2,765,794 | 54,000 | -2,711,794 | ❌ |
| 1,000 | 3,185,194 | 540,000 | -2,645,194 | ❌ |
| 5,000 | 5,049,194 | 2,700,000 | -2,349,194 | ❌ |
| 10,000 | 7,379,194 | 5,400,000 | -1,979,194 | ❌ |
| **36,746** | **19,839,550** | **19,842,840** | **+3,290** | ✅ |
| 50,000 | 22,019,194 | 27,000,000 | +4,980,806 | ✅ |
| 100,000 | 30,319,194 | 54,000,000 | +23,680,806 | ✅ |

### Key Insight
Code Factory requires **~37,000 runs on the same task** before becoming cost-effective. The massive compilation overhead makes it unsuitable for one-off tasks or small-scale usage.

---

## 5. Failure Analysis

### Code Factory Failure (1 instance)

**Instance**: `simple_62` - DNA sequence analysis
**Issue**: Generated activity extracted empty strings for DNA sequences
**Root Cause**: Regex pattern matching failed to extract sequences from prompt
**Score**: 0.3 (format correct, content wrong)

```python
# Generated code returned:
{"analyze_dna_sequence": {"sequence": "", "reference_sequence": "", "mutation_type": "substitution"}}

# Expected:
{"analyze_dna_sequence": {"sequence": "AGTCGATCGAACGTACGTACG", "reference_sequence": "AGTCCATCGAACGTACGTACG", "mutation_type": "substitution"}}
```

**Impact**: The validation phase passed because the format was correct, but the execution extracted empty strings instead of DNA sequences.

### Direct LLM Failures (5 instances)

All 5 failures were **format mismatches** (score 0.3) with correct content:

1. **simple_20**: Math HCF - wrapped in `{"name": "math.hcf", "parameters": {...}}`
2. **simple_27**: Final velocity - included calculation explanation
3. **simple_32**: Final speed - used XML function call format, missing optional gravity parameter
4. **simple_53**: DNA fetch - included conversational text around function call
5. **simple_66**: Precipitation - used XML format instead of JSON

**Pattern**: Direct LLM often adds helpful context (calculations, explanations) or uses alternative valid formats (XML function calls) that don't match the exact expected structure.

---

## 6. Cost Analysis (Anthropic Pricing)

Using Claude Opus 4.5 pricing (estimated: $15/1M input, $75/1M output):

### Single Run (100 instances)

**Direct LLM**:
- Input: 35,173 tokens × $15/1M = $0.53
- Output: 18,801 tokens × $75/1M = $1.41
- **Total: $1.94** for 100 instances

**Code Factory**:
- Input: 2,276,393 tokens × $15/1M = $34.15
- Output: 489,434 tokens × $75/1M = $36.71
- **Total: $70.86** for 100 instances

**Cost Ratio**: Code Factory is **36.5x more expensive** per run.

### At Scale (1000 runs on same 100 tasks)

**Direct LLM**: $1.94 × 1000 = **$1,940**

**Code Factory**:
- Compilation: $70.86 (one-time)
- Execution: 46,633 tokens × 1000 runs = 46.6M tokens
  - Input: 43,789 × 1000 × $15/1M = $656.84
  - Output: 2,844 × 1000 × $75/1M = $213.30
  - Execution total: $870.14
- **Total: $940.99** (saves $999)

**Break-even**: ~2,060 runs (not 36,746 because output tokens cost 5x more than input)

---

## 7. Workflow Analysis

### Generated Workflows

Code Factory generated **100 unique workflows** for the 100 BFCL instances:
- No cache hits (0% reuse)
- Each task signature was unique enough to trigger new compilation
- Activities were highly specialized to each function calling task

### Example Workflow: GCD Calculation

```yaml
workflow:
  name: "GCD Function Parameter Extractor"
  description: "Extract GCD function parameters from user query"
  variables:
    - prompt

  root:
    sequence:
      elements:
        - activity:
            name: extract_gcd_parameters
            parameters:
              prompt: ${{ prompt }}
            result: gcd_function_call
```

### Activity Registry

- **100 activities registered** in semantic search index
- Each activity tailored to specific function signature
- Potential for reuse in future similar tasks (e.g., other math functions)

---

## 8. Quality of Generated Code

### Strengths

1. **Deterministic output**: No format variations across runs
2. **Robust parameter extraction**: Uses regex patterns with fallbacks
3. **Type safety**: Generated code handles JSON parsing errors
4. **Documentation**: Activities include clear descriptions and examples

### Weaknesses

1. **Over-specialized**: Generated workflows very specific to each task
2. **Limited reuse**: 0% cache hit rate despite similar function calling patterns
3. **Extraction failures**: Regex-based extraction can fail on edge cases (e.g., DNA sequences)
4. **Code bloat**: Generated activities include extensive error handling and fallbacks

### Example Generated Activity Quality

```python
# Code Factory generated this for simple_24 (GCD):
def extract_gcd_parameters(prompt: str) -> dict:
    """Extract GCD function parameters with multiple regex patterns."""
    patterns = [
        r'(?:gcd|greatest common divisor).*?(?:of|between)\s+(\d+)\s+and\s+(\d+)',
        r'(\d+)\s+and\s+(\d+)',
        r'(\d+)\s*,\s*(\d+)',
        # ... 5 more patterns
    ]
    for pattern in patterns:
        match = re.search(pattern, user_prompt, re.IGNORECASE)
        if match:
            return {"math.gcd": {"num1": int(match.group(1)), "num2": int(match.group(2))}}
    # Fallback to default values
    return {"math.gcd": {"num1": 12, "num2": 15}}
```

**Quality Assessment**: Thorough and defensive, but overly complex for simple extraction.

---

## 9. Key Takeaways

### When to Use Code Factory ✅

1. **High-volume, repetitive tasks** (>10,000 runs)
2. **Production systems** requiring 99%+ accuracy
3. **Deterministic behavior** is critical
4. **Long-running services** where compilation cost is amortized
5. **Regulatory/compliance** requirements for deterministic outputs

### When to Use Direct LLM ✅

1. **One-off or low-volume tasks** (<1,000 runs)
2. **Rapid prototyping** and experimentation
3. **Cost-sensitive applications**
4. **Time-sensitive tasks** (need results in seconds, not minutes)
5. **Tasks with high variability** (not worth compiling)

### Current Limitations of Code Factory

1. **Poor cache reuse**: 0% hit rate on similar function calling tasks
2. **Massive compilation overhead**: 98% of tokens spent on compilation
3. **Break-even too high**: Requires ~37K runs to be cost-effective
4. **Slow compilation**: 65s per workflow vs 4s for direct call
5. **Edge case failures**: Regex extraction can fail on complex inputs

---

## 10. Recommendations

### For Code Factory Improvements

1. **Improve task signature matching** to increase cache hits
   - Currently: 0% cache hit rate
   - Goal: Reuse workflows for similar function calling patterns
   - Example: All "extract 2 numbers" tasks could share a workflow

2. **Reduce compilation cost**
   - Use smaller model (Haiku) for Planner phase
   - Implement incremental compilation (reuse validated activities)
   - Skip validation on cached workflows

3. **Optimize for function calling**
   - Create generic "function parameter extractor" template
   - Pre-compile common patterns (math operations, data extraction)
   - Add function calling-specific optimizations

4. **Better extraction logic**
   - Use LLM-based extraction instead of regex for complex cases
   - Add validation during execution (not just compilation)
   - Implement fallback to LLM if extraction fails

### For Benchmark Improvements

1. **Test at scale**: Run 1,000+ instances to see amortization benefits
2. **Test cache effectiveness**: Run duplicate tasks to measure reuse
3. **Measure inference cost**: Compare actual API costs, not just tokens
4. **Test other categories**: Beyond simple function calling (parallel, multiple, etc.)

---

## 11. Conclusion

Code Factory demonstrates **higher accuracy** (99% vs 95%) through deterministic code generation and validation, but comes at a **massive cost** in tokens (51x) and time (10x). The break-even point of ~37,000 runs makes it impractical for most use cases.

**The current implementation favors quality over efficiency**, which is appropriate for proof-of-concept but needs optimization for production use.

### Success Metrics

| Metric | Target | Achieved | Status |
|--------|--------|----------|--------|
| Accuracy | >95% | 99% | ✅ Exceeded |
| Token efficiency | <5x Direct LLM | 51x Direct LLM | ❌ Far from target |
| Cache hit rate | >50% | 0% | ❌ Not achieved |
| Break-even point | <1,000 runs | 36,746 runs | ❌ Far from target |

**Next Steps**: Focus on improving cache reuse and reducing compilation overhead to make Code Factory practical for real-world applications.
