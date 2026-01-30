# PR Decision Matrix - Quick Reference

## At a Glance

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SEMIFINAL MERGE STRATEGY                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ✅ MERGE NOW          ⚠️ REVIEW FIRST        🔴 BLOCKED               │
│   ───────────          ─────────────          ─────────                 │
│   #17 Table 15         #18 Paper v3           #15 External              │
│   #19 Paper v4         + Datasets             Benchmarks                │
│                        (51K lines)            (arch issues)             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Merge Order

```
Step 1: gh pr merge 17 --merge --repo XY-Corp/CompiledAI
        └── Adds Table 15 tooling (code quality metrics)

Step 2: gh pr merge 19 --merge --repo XY-Corp/CompiledAI  
        └── Adds Paper v4 with literature review

Step 3: (After rebasing #18 onto main)
        Review flagged issues, then:
        gh pr merge 18 --merge --repo XY-Corp/CompiledAI
        └── Adds datasets + paper v3 feedback

Step 4: (After mxvp refactors)
        gh pr merge 15 --merge --repo XY-Corp/CompiledAI
        └── Adds external benchmark baselines
```

## What Each PR Contributes to Semifinal

### Paper Content
| Component | PR #17 | PR #18 | PR #19 | PR #15 |
|-----------|--------|--------|--------|--------|
| Paper v3 (Walter feedback) | | ✅ | | |
| Paper v4 (benchmarks) | | | ✅ | |
| Literature review | | | ✅ | |
| Table 15 data | ✅ | | | |

### Code/Infrastructure
| Component | PR #17 | PR #18 | PR #19 | PR #15 |
|-----------|--------|--------|--------|--------|
| Code quality scanner | ✅ | | | |
| SAST validation | ✅ | | | |
| Dataset converters | | ✅ | | |
| Baseline improvements | | | | ✅ |
| LangChain tool calling | | | | ✅ |
| AutoGen rate limiting | | | | ✅ |

### Datasets
| Dataset | PR #17 | PR #18 | PR #19 | PR #15 |
|---------|--------|--------|--------|--------|
| BFCL v4 | | ✅ | | |
| SWE-bench lite | | ✅ | | |
| WebArena | | ✅ | | |
| Spider2v | | ✅ | | |
| Mind2Web | | ✅ | | |
| GAIA | | ✅ | | |
| XY benchmark (restructured) | | ✅ | | |
| DocILE adapter | | | | ✅ |

## Risk Assessment

| PR | Size | Conflicts | Tested | Reviewed | Risk |
|----|------|-----------|--------|----------|------|
| #17 | 2K | Low | ✅ | ✅ Gemini | 🟢 Low |
| #19 | 2K | Low | ✅ | ✅ Gemini | 🟢 Low |
| #18 | 52K | Medium | ⚠️ | ⚠️ Flagged | 🟡 Medium |
| #15 | 2K | Low | ✅ | 🔴 Changes | 🔴 Blocked |

## Potential Paper Narrative

With merged PRs, the paper can claim:

**From #17 (Table 15):**
- 100% type coverage (vs 35% human baseline)
- Zero security vulnerabilities
- 96% test pass rate

**From #19 (Literature):**
- 79% of MAS failures are specification issues (MAST framework)
- 45% of AI-generated code has security vulnerabilities (Veracode 2025)
- Support for "Compiled AI" thesis: determinism > runtime flexibility

**From #18 (Benchmarks):**
- Evaluation on BFCL v4, SWE-bench, WebArena
- Comprehensive external benchmark comparison

**From #15 (Baselines):**
- Fair comparison: LangChain, AutoGen, Direct LLM
- Semantic evaluation with LLM judge

## Commands for Today

```bash
# 1. Merge the safe ones
gh pr merge 17 --merge --repo XY-Corp/CompiledAI
gh pr merge 19 --merge --repo XY-Corp/CompiledAI

# 2. Update local and check status
cd ~/dev/xy/CompiledAI
git pull origin main
git status

# 3. Rebase #18 if needed
gh pr checkout 18
git rebase origin/main
git push --force-with-lease

# 4. Review #18's flagged issues before merging
```
